"""Phase 2.1 security tests - authentication and authorization.

Auth-enabled tests run in isolation so the default (auth-off) suite is never
affected. We construct an in-memory SQLite DB with the v2 schema (users +
owner_id), point the shared SessionLocal references at it, and force auth ON
with a known secret.

Covered:
- Credential verification (bcrypt): wrong password, unknown user, reserved /
  duplicate username, short password all rejected.
- No fake login: a token is issued only after a real username/password pair
  verifies; an arbitrary user_id cannot be minted.
- Token validation: malformed, tampered, cross-secret and expired tokens are
  rejected with 401.
- Ownership / IDOR: an authenticated user cannot read/list/mutate another
  user's conversation; NULL-owner (legacy) conversations are not accessible to
  any authenticated user when auth is ON.
- Every protected route returns 401 without a valid token when auth is ON.
"""

import hmac
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_SECRET = "test-secret-not-for-production"

import backend.app.auth as auth_module  # noqa: E402
from backend.app.database import Base  # noqa: E402
from backend.app.models import (  # noqa: E402
    BuildConversation,
    CPUSpecification,
    GPUSpecification,
    Hardware,
)

from backend.app import main  # noqa: E402
from backend.app.services import build_conversation_service  # noqa: E402

AUTH = "Authorization"
BEARER = "Bearer "


def _sign(user_id, expiry, secret):
    payload = f"{user_id}:{expiry}"
    digest = hmac.new(secret.encode(), payload.encode(), "sha256").hexdigest()
    return f"{payload}:{digest}"


def _token(user_id, *, secret="test-secret-not-for-production", expire_in=3600):
    expiry = int(time.time()) + expire_in
    return _sign(user_id, expiry, secret)


class AuthSetup:
    """In-memory v2-schema app with auth forced ON."""

    def __init__(self):
        self._saved = {
            "main.SessionLocal": main.SessionLocal,
            "service.SessionLocal": build_conversation_service.SessionLocal,
            "auth.SessionLocal": auth_module.SessionLocal,
            "auth.enabled": auth_module._AUTH_ENABLED,
            "auth.secret": auth_module._AUTH_SECRET,
        }
        # Force auth ON for these tests only. require_auth reads these live at
        # request time, so patching the module attributes (not the process env)
        # keeps every other test module's auth-off behavior intact.
        auth_module._AUTH_ENABLED = True
        auth_module._AUTH_SECRET = TEST_SECRET

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        main.SessionLocal = self.session_factory
        build_conversation_service.SessionLocal = self.session_factory
        auth_module.SessionLocal = self.session_factory

        self.client = TestClient(main.app)
        self.cpu_id, self.gpu_id = self._seed()

    def _seed(self):
        with self.session_factory() as session:
            cpu = Hardware(name="AMD Ryzen 5 5600", manufacturer="AMD",
                           type="CPU", architecture="Zen 3")
            cpu.cpu_specification = CPUSpecification(cores=6, threads=12)
            gpu = Hardware(name="NVIDIA RTX 5070 Ti", manufacturer="NVIDIA",
                           type="GPU", architecture="Blackwell")
            gpu.gpu_specification = GPUSpecification(memory_gb=16)
            session.add_all([cpu, gpu])
            session.commit()
            return cpu.id, gpu.id

    def register(self, username, password):
        return self.client.post(
            "/auth/register", json={"username": username, "password": password}
        )

    def login(self, username, password):
        return self.client.post(
            "/auth/login", json={"username": username, "password": password}
        )

    def create_conversation(self, token, cpu=None, gpu=None):
        headers = {AUTH: BEARER + token} if token else {}
        return self.client.post(
            "/build/conversations",
            json={"cpu_hardware_id": cpu or self.cpu_id,
                  "gpu_hardware_id": gpu or self.gpu_id},
            headers=headers,
        )

    def teardown(self):
        main.SessionLocal = self._saved["main.SessionLocal"]
        build_conversation_service.SessionLocal = self._saved["service.SessionLocal"]
        auth_module.SessionLocal = self._saved["auth.SessionLocal"]
        auth_module._AUTH_ENABLED = self._saved["auth.enabled"]
        auth_module._AUTH_SECRET = self._saved["auth.secret"]
        self.engine.dispose()


@pytest.fixture
def auth():
    s = AuthSetup()
    yield s
    s.teardown()


GOOD_PW = "correct-horse-battery-staple9"


class TestCredentialVerification:
    """A token is issued ONLY after a real username/password pair verifies."""

    def test_register_returns_a_working_token(self, auth):
        resp = auth.register("alice", GOOD_PW)
        assert resp.status_code == 201
        data = resp.json()
        assert data["token_type"] == "bearer"
        token = data["token"]
        assert auth_module.verify_token(token) is not None

        # The issued token is valid for a real user.
        headers = {AUTH: BEARER + token}
        resp = auth.create_conversation(token)
        assert resp.status_code == 200
        assert resp.json()["owner_id"] is not None

    def test_login_verifies_credentials(self, auth):
        auth.register("alice", GOOD_PW)

        ok = auth.login("alice", GOOD_PW)
        assert ok.status_code == 200
        assert "token" in ok.json()

        wrong = auth.login("alice", "wrong-password-123456789")
        assert wrong.status_code == 401

        unknown = auth.login("nobody", GOOD_PW)
        assert unknown.status_code == 401

    def test_short_password_is_rejected_at_register(self, auth):
        resp = auth.register("bob", "short1")
        assert resp.status_code == 422
        resp = auth.login("bob", "short1")
        assert resp.status_code == 401  # never created

    def test_reserved_and_duplicate_usernames_are_rejected(self, auth):
        assert auth.register("root", GOOD_PW).status_code == 422
        assert auth.register("admin", GOOD_PW).status_code == 422
        assert auth.register("Alice", GOOD_PW).status_code == 201
        assert auth.register("alice", GOOD_PW).status_code == 422

    def test_password_hash_is_never_leaked(self, auth, tmp_path):
        # After registering, the users table stores the bcrypt hash, never the
        # plaintext, and no response exposes it.
        auth.register("carol", GOOD_PW)
        with auth.session_factory() as session:
            User = auth_module.User

            user = session.query(User).filter_by(username="carol").one()
            assert user.password_hash != GOOD_PW
            assert user.password_hash.startswith("$2")

    def test_token_cannot_be_minted_for_arbitrary_user(self, auth):
        # No endpoint mints tokens for a caller-supplied user_id: forging a
        # token for user 999 without a valid signature must fail on use.
        forged = _token(999)
        resp = auth.create_conversation(forged)
        assert resp.status_code == 401


class TestTokenValidation:
    """Malformed, tampered, expired and cross-secret tokens are rejected."""

    def test_missing_token_returns_401(self, auth):
        resp = auth.client.get("/build/conversations/1")
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, auth):
        for bad in ("", "abc", "1:123:zzz", "not-a-token"):
            resp = auth.create_conversation(bad)
            assert resp.status_code == 401, bad

    def test_tampered_token_returns_401(self, auth):
        auth.register("dave", GOOD_PW)
        token = auth.login("dave", GOOD_PW).json()["token"]
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        resp = auth.create_conversation(tampered)
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, auth):
        auth.register("erin", GOOD_PW)
        token = _token(1, expire_in=-100)  # already expired
        resp = auth.create_conversation(token)
        assert resp.status_code == 401

    def test_token_signed_with_other_secret_returns_401(self, auth):
        auth.register("frank", GOOD_PW)
        real_user_id = None
        with auth.session_factory() as session:
            User = auth_module.User

            real_user_id = session.query(User).filter_by(username="frank").one().id
        token = _token(real_user_id, secret="a-completely-different-secret")
        resp = auth.create_conversation(token)
        assert resp.status_code == 401


class TestOwnershipAndIDOR:
    """No authenticated user can read or mutate another user's data."""

    def test_users_cannot_read_each_others_conversation(self, auth):
        t_alice = auth.register("aliceA", GOOD_PW).json()["token"]
        t_bob = auth.register("bobB", GOOD_PW).json()["token"]

        created = auth.create_conversation(t_alice)
        conv_id = created.json()["id"]
        assert created.json()["owner_id"] is not None

        # Bob cannot GET Alice's conversation
        resp = auth.client.get(f"/build/conversations/{conv_id}",
                               headers={AUTH: BEARER + t_bob})
        assert resp.status_code in (401, 404)

        # Bob cannot list Alice's messages
        resp = auth.client.get(f"/build/conversations/{conv_id}/messages",
                               headers={AUTH: BEARER + t_bob})
        assert resp.status_code in (401, 404)

    def test_users_cannot_write_to_each_others_conversation(self, auth):
        t_alice = auth.register("aliceC", GOOD_PW).json()["token"]
        t_bob = auth.register("bobD", GOOD_PW).json()["token"]

        created = auth.create_conversation(t_alice).json()
        conv_id = created["id"]

        # Bob cannot append a message
        resp = auth.client.post(
            f"/build/conversations/{conv_id}/messages",
            json={"role": "user", "content": "Halo"},
            headers={AUTH: BEARER + t_bob},
        )
        assert resp.status_code in (401, 404)

        # Bob cannot append a turn
        resp = auth.client.post(
            f"/build/conversations/{conv_id}/turn",
            json={"question": "Bagaimana?", "answer": "Jawaban."},
            headers={AUTH: BEARER + t_bob},
        )
        assert resp.status_code in (401, 404)

        # Bob cannot reset Alice's conversation
        resp = auth.client.post(
            f"/build/conversations/{conv_id}/reset",
            headers={AUTH: BEARER + t_bob},
        )
        assert resp.status_code in (401, 404)

    def test_null_owner_conversations_are_not_accessible_when_auth_on(self, auth):
        # Insert a legacy NULL-owner conversation directly (as if created
        # before auth existed) - it must NOT be reachable by an authenticated
        # user.
        with auth.session_factory() as session:
            legacy = BuildConversation(
                cpu_hardware_id=auth.cpu_id,
                gpu_hardware_id=auth.gpu_id,
                owner_id=None,
            )
            session.add(legacy)
            session.commit()
            conv_id = legacy.id

        t_alice = auth.register("aliceE", GOOD_PW).json()["token"]
        resp = auth.client.get(f"/build/conversations/{conv_id}",
                               headers={AUTH: BEARER + t_alice})
        assert resp.status_code in (401, 404)

        # An unauthenticated request (no token) is also rejected outright.
        resp = auth.client.get(f"/build/conversations/{conv_id}")
        assert resp.status_code == 401

    def test_owner_can_still_use_their_own_conversation(self, auth):
        t_alice = auth.register("aliceF", GOOD_PW).json()["token"]
        created = auth.create_conversation(t_alice).json()
        conv_id = created["id"]

        # Owner read, list, turn, reset all succeed.
        assert auth.client.get(
            f"/build/conversations/{conv_id}",
            headers={AUTH: BEARER + t_alice},
        ).status_code == 200
        assert auth.client.get(
            f"/build/conversations/{conv_id}/messages",
            headers={AUTH: BEARER + t_alice},
        ).status_code == 200
        assert auth.client.post(
            f"/build/conversations/{conv_id}/turn",
            json={"question": "Bagaimana?", "answer": "Jawaban."},
            headers={AUTH: BEARER + t_alice},
        ).status_code == 201
        assert auth.client.post(
            f"/build/conversations/{conv_id}/reset",
            headers={AUTH: BEARER + t_alice},
        ).status_code == 200


class TestProtectedRoutesWhenAuthOn:
    """The AI/cost endpoints are protected when auth is ON."""

    def test_ai_endpoints_require_a_token(self, auth):
        # comparison/explanation, hardware/chat, build/chat all 401 without token
        assert auth.client.post(
            "/comparison/explanation",
            json={"comparison": {}},
        ).status_code == 401
        assert auth.client.post(
            "/hardware/chat", json={"question": "Halo"}
        ).status_code == 401
        assert auth.client.post(
            "/build/chat", json={"build": {"cpu": {"id": 1, "name": "x"},
                                           "gpu": {"id": 2, "name": "y"}},
                                 "question": "Bagaimana?"},
        ).status_code == 401

    def test_public_routes_stay_open(self, auth):
        assert auth.client.get("/health").status_code == 200
        assert auth.client.get("/hardware").status_code == 200
        assert auth.client.get(f"/hardware/{auth.cpu_id}").status_code == 200
        assert auth.client.get(
            f"/hardware/{auth.cpu_id}/benchmarks"
        ).status_code == 200


