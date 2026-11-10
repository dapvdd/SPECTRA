"""Admin bootstrap / recovery CLI for SPECTRA.

Why this exists
---------------
When ``SPECTRA_AUTH_ENABLED=1`` and the ``users`` table is empty, no one can
log in: tokens are issued only by /auth/login and /auth/register, and both
require a working HTTP surface plus a client. There is no default admin
account (that would be a permanent backdoor). This CLI is the safe recovery
path: an operator with shell access to the container creates the first user —
or a replacement admin — directly against the database.

Safety properties
-----------------
- The password is read from stdin (getpass when interactive). It is never
  accepted as a CLI argument or environment variable, so it cannot leak into
  shell history, process listings, or compose files.
- Usernames follow the same rules as /auth/register (normalisation, reserved
  names, minimum length), enforced by the shared ``create_user`` helper, so a
  bootstrapped account is exactly like a registered one.
- When users already exist the script REFUSES to run unless
  ``--allow-existing-users`` is passed. This prevents accidentally adding an
  account during a routine operation; recovery is a deliberate act.
- The script never prints the password and never logs it. On success it prints
  only the username and the count of remaining accounts.

Usage (inside the backend container)::

    docker exec -i spectra-backend python -m backend.app.scripts.bootstrap_admin \
        --username <name>

Enter the password at the prompt (or pipe it in: ``printf '%s\n' "$PW" | docker exec -i …``).

Recovery after an operator lockout follows the same command: pass
``--allow-existing-users`` to add a fresh account when you can no longer log
in with any existing one. The lockout is never caused by the application.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from backend.app.database import SessionLocal
from backend.app.auth import User, create_user


def _count_users(session) -> int:
    return session.query(User).count()


def bootstrap_admin(
    username: str,
    password: str,
    *,
    allow_existing_users: bool = False,
) -> dict:
    """Create a user directly in the database. Returns a result dict.

    Raises ``ValueError`` on invalid credentials, a duplicate username, or when
    users already exist and ``allow_existing_users`` is False.
    """
    with SessionLocal() as session:
        existing = _count_users(session)
        if existing > 0 and not allow_existing_users:
            raise ValueError(
                f"Users table already has {existing} account(s). Refusing to "
                "bootstrap implicitly. Pass --allow-existing-users if this is "
                "a deliberate recovery operation."
            )

        user = create_user(username, password, session=session)

        return {
            "username": user.username,
            "user_id": user.id,
            "total_users": _count_users(session),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create the first (or a recovery) SPECTRA user directly in the "
            "database. The password is read from stdin and never echoed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Username for the new account (normalised to lowercase).",
    )
    parser.add_argument(
        "--allow-existing-users",
        action="store_true",
        help=(
            "Permit creating an account when users already exist (recovery "
            "scenario). Without this flag the script refuses when any user is "
            "present, to prevent accidental account creation."
        ),
    )
    parser.add_argument(
        "--stdin-password",
        action="store_true",
        help=(
            "Read the password from the first line of stdin instead of an "
            "interactive prompt. Use when piping a secret in."
        ),
    )
    args = parser.parse_args(argv)

    if args.stdin_password:
        raw = sys.stdin.readline()
        password = raw.rstrip("\r\n")
        if not password:
            print("ERROR: empty password on stdin.", file=sys.stderr)
            return 2
    else:
        password = getpass.getpass(f"Password for {args.username}: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("ERROR: passwords do not match.", file=sys.stderr)
            return 2

    try:
        result = bootstrap_admin(
            args.username,
            password,
            allow_existing_users=args.allow_existing_users,
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        f"Created user {result['username']!r} (id={result['user_id']}). "
        f"Total users: {result['total_users']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
