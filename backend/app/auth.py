"""SPECTRA authentication and authorization (Phase 2.1, security-corrected).

Feature-flagged OFF by default so V1 unauthenticated behaviour is the baseline
and every existing test remains valid. Enable with ``SPECTRA_AUTH_ENABLED=1``
plus a server-side ``SPECTRA_AUTH_SECRET``.

Security model
--------------
- Credentials are stored as bcrypt hashes in the ``users`` table. bcrypt is an
  established password-hashing scheme (adaptive, salted, CPU-hard). No plaintext
  is ever persisted and the hash never reaches a response.
- Identity issuance is trustworthy: a token is issued ONLY by ``/auth/login``
  or ``/auth/register`` after the submitted credentials verify. There is no
  endpoint that mints a token for an arbitrary user_id.
- Tokens are HMAC-SHA256 signatures over ``<user_id>:<expiry>`` keyed by the
  server-side secret. Validation is constant-time (``hmac.compare_digest``).
  Malformed, expired, or invalid-signature tokens are all rejected with 401.
- The FastAPI dependency raises ``HTTPException(401)`` directly; it never
  returns a JSONResponse as a dependency value (which would be swallowed).
- Ownership is enforced server-side on every protected operation. When auth is
  ON, an authenticated user may read/write only conversations whose
  ``owner_id`` equals their user id. NULL-owner rows (legacy, created before the
  feature) are NOT accessible to any authenticated user when auth is ON — there
  is no fallback path that bypasses the scoping check. When auth is OFF nothing
  is protected and NULL-owner rows behave exactly as before.

Strategy for the users table / owner_id
---------------------------------------
The schema additions are registered as migration v2 in the runner and applied
to disposable copies only. Production activation is blocked pending explicit
approval — this code being merged does not touch any live database.
"""

from __future__ import annotations

import hmac
import os
import time

import bcrypt
from fastapi import Header, HTTPException

from backend.app.database import Base, SessionLocal
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_AUTH_ENABLED: bool = (
    os.getenv("SPECTRA_AUTH_ENABLED", "0").strip().lower()
    in {"1", "true", "yes", "on"}
)
_AUTH_SECRET: str | None = os.getenv("SPECTRA_AUTH_SECRET", "").strip() or None
_TOKEN_TTL_SECONDS: int = int(os.getenv("SPECTRA_AUTH_TOKEN_TTL_SECONDS", "86400"))
_MIN_PASSWORD_LENGTH: int = 12
_BCRYPT_ROUNDS: int = 12

# Usernames are case-insensitive; "root" is a single reserved name.
_RESERVED_USERNAMES = frozenset({"root", "admin"})


def is_auth_enabled() -> bool:
    """True when authentication is active (SPECTRA_AUTH_ENABLED=1)."""
    return _AUTH_ENABLED


def _require_secret() -> str:
    if not _AUTH_SECRET:
        raise RuntimeError(
            "SPECTRA_AUTH_SECRET is not set. Set it to a random string "
            "(e.g. `openssl rand -hex 32`) and restart when SPECTRA_AUTH_ENABLED=1."
        )
    return _AUTH_SECRET


# ---------------------------------------------------------------------------
# SQLAlchemy user model
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)


def create_user(
    username: str,
    password: str,
    *,
    session=None,
) -> User:
    """Create a user with a bcrypt-hashed password. Raises ValueError on
    invalid credentials or a duplicate username, and returns the User row."""
    normalized = username.strip().lower()
    if not normalized:
        raise ValueError("Username cannot be empty.")
    if normalized in _RESERVED_USERNAMES:
        raise ValueError(f"Username {normalized!r} is reserved.")
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {_MIN_PASSWORD_LENGTH} characters."
        )

    hashed = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    ).decode("utf-8")

    owns_session = session is None
    explicit = session or SessionLocal()
    try:
        existing = explicit.query(User).filter(
            User.username == normalized
        ).one_or_none()
        if existing is not None:
            raise ValueError(f"Username {normalized!r} is already registered.")

        user = User(username=normalized, password_hash=hashed)
        explicit.add(user)
        explicit.commit()
        explicit.refresh(user)
        return user
    finally:
        if owns_session:
            explicit.close()


def verify_user(username: str, password: str) -> User | None:
    """Return the User row when the username+password pair verifies, else None."""
    normalized = username.strip().lower()
    if not normalized:
        return None

    with SessionLocal() as session:
        user = session.query(User).filter(User.username == normalized).one_or_none()
        if user is None:
            return None

        # Constant-ish comparison: bcrypt handles verification internally.
        try:
            ok = bcrypt.checkpw(
                password.encode("utf-8"), user.password_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            return None

        return user if ok else None


def authenticate_user(username: str, password: str) -> str:
    """Verify credentials and issue a signed bearer token.

    Returns a token string, or raises :class:`InvalidCredentialsError` when the
    supplied credentials do not verify. This is the ONLY way (besides
    register) that a token is issued — the caller must have presented a
    username/password pair that actually verifies.
    """
    user = verify_user(username, password)
    if user is None:
        raise InvalidCredentialsError()
    return issue_token(user.id)


def login_response(username: str, password: str) -> dict:
    user = verify_user(username, password)
    if user is None:
        raise InvalidCredentialsError()
    token = issue_token(user.id)
    return {"username": user.username, "token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Token issuance / verification
# ---------------------------------------------------------------------------

_TOKEN_SEP = ":"


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), "sha256").hexdigest()


def issue_token(user_id: int, *, secret: str | None = None) -> str:
    """Issue a signed bearer token for user_id. Signed by the server secret.

    The token is NOT proof of identity by itself; it is the bearer credential
    minted only after normal credential verification (see authenticate_user /
    login_response). Expiry is embedded and signed so it cannot be tampered.
    """
    secret = secret or _require_secret()
    expiry = int(time.time()) + _TOKEN_TTL_SECONDS
    payload = f"{user_id}{_TOKEN_SEP}{expiry}"
    digest = _sign(payload, secret)
    return f"{payload}{_TOKEN_SEP}{digest}"


def verify_token(raw: str) -> int | None:
    """Return the user_id from a valid token, else None."""
    if not raw or _TOKEN_SEP not in raw:
        return None

    try:
        user_id_raw, expiry_raw, digest = raw.rsplit(_TOKEN_SEP, 2)
        user_id = int(user_id_raw)
        expiry = int(expiry_raw)
    except (ValueError, TypeError):
        return None

    if expiry < int(time.time()):
        return None

    secret = _AUTH_SECRET
    if not secret:
        return None

    expected_digest = _sign(f"{user_id}{_TOKEN_SEP}{expiry}", secret)
    if not hmac.compare_digest(digest, expected_digest):
        return None

    return user_id


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

_BEARER_PREFIX = "Bearer "


def require_auth(
    authorization: str | None = Header(default=None),
) -> int | None:
    """FastAPI dependency returning the authenticated user_id.

    Raises HTTPException(401) when:
      - auth is ON and the Authorization header is absent or not a Bearer token;
      - the token has an invalid signature, is malformed, or is expired.

    When auth is OFF it always passes and returns None (guest), so V1
    unauthenticated behaviour — including access to existing conversation
    data — is unchanged.

    The dependency raises (never returns an error value) so FastAPI treats the
    401 as a true rejection without the middleware swallowing it.
    """
    if not is_auth_enabled():
        # Auth disabled: guest flow, no owner constraint applied.
        return None

    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len(_BEARER_PREFIX):].strip()
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Defense-in-depth: the token's signature is valid, but the underlying
    # account must still exist. A token minted for a deleted/non-existent user
    # is not proof of a live, authenticated account, so it is rejected.
    with SessionLocal() as session:
        exists = session.query(User.id).filter(User.id == user_id).scalar()
    if exists is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


# ---------------------------------------------------------------------------
# Shared exception
# ---------------------------------------------------------------------------


class InvalidCredentialsError(Exception):
    """Raised when a username/password pair fails to verify."""
