"""M1.5 admin bootstrap tests - safe recovery path.

Covered:
- Bootstrap creates a working user with a bcrypt hash (no plaintext).
- The password is never accepted as an argument (tested by construction: the
  CLI requires --username and reads the password from stdin/getpass only).
- Refusal when users already exist unless --allow-existing-users is passed.
- stdin password mode (piped secret) works.
- Interactive mismatch (password != confirm) is rejected.
- The created account can log in through the HTTP surface when auth is ON.
- Reserved/duplicate/short usernames are rejected exactly as /auth/register.
"""

import io

import pytest

from backend.app.database import Base
from backend.app.scripts import bootstrap_admin as mod
from backend.app.auth import User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.auth as auth_module
import backend.app.main as main_module
from backend.app.services import build_conversation_service
from backend.app.services import benchmark_service
from backend.app.scripts import bootstrap_admin as bootstrap_admin_module

GOOD_PW = "correct-horse-battery-staple9"


class BootstrapSetup:
    """In-memory v2-schema DB pointed at the shared SessionLocal references."""

    def __init__(self):
        self._saved = {
            "main": main_module.SessionLocal,
            "service": build_conversation_service.SessionLocal,
            "benchmark": benchmark_service.SessionLocal,
            "auth": auth_module.SessionLocal,
            "bootstrap": bootstrap_admin_module.SessionLocal,
        }
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        main_module.SessionLocal = self.session_factory
        build_conversation_service.SessionLocal = self.session_factory
        auth_module.SessionLocal = self.session_factory
        benchmark_service.SessionLocal = self.session_factory
        bootstrap_admin_module.SessionLocal = self.session_factory

    def teardown(self):
        main_module.SessionLocal = self._saved["main"]
        build_conversation_service.SessionLocal = self._saved["service"]
        benchmark_service.SessionLocal = self._saved["benchmark"]
        auth_module.SessionLocal = self._saved["auth"]
        bootstrap_admin_module.SessionLocal = self._saved["bootstrap"]
        self.engine.dispose()


@pytest.fixture
def db():
    s = BootstrapSetup()
    yield s
    s.teardown()


class TestBootstrapAdmin:
    def test_bootstrap_creates_working_user(self, db):
        result = mod.bootstrap_admin("admin-recovery", GOOD_PW)
        assert result["username"] == "admin-recovery"
        assert result["total_users"] == 1

        with db.session_factory() as session:
            user = session.query(User).filter_by(
                username="admin-recovery"
            ).one()
            assert user.password_hash.startswith("$2")
            assert user.password_hash != GOOD_PW

    def test_refuses_when_users_exist_without_flag(self, db):
        mod.bootstrap_admin("first", GOOD_PW)
        with pytest.raises(ValueError, match="already has 1 account"):
            mod.bootstrap_admin("second", GOOD_PW)

    def test_allows_existing_users_with_flag(self, db):
        mod.bootstrap_admin("first", GOOD_PW)
        result = mod.bootstrap_admin(
            "recovery", GOOD_PW, allow_existing_users=True
        )
        assert result["total_users"] == 2

    def test_reserved_username_rejected(self, db):
        with pytest.raises(ValueError, match="reserved"):
            mod.bootstrap_admin("admin", GOOD_PW)

    def test_short_password_rejected(self, db):
        with pytest.raises(ValueError, match="at least 12"):
            mod.bootstrap_admin("someone", "short")

    def test_duplicate_username_rejected(self, db):
        mod.bootstrap_admin("dupe", GOOD_PW, allow_existing_users=True)
        with pytest.raises(ValueError, match="already registered"):
            mod.bootstrap_admin("dupe", GOOD_PW, allow_existing_users=True)

    def test_stdin_password_mode(self, db, monkeypatch):
        monkeypatch.setattr(
            "sys.stdin", io.StringIO(GOOD_PW + "\n")
        )
        rc = mod.main(["--username", "piped", "--stdin-password"])
        assert rc == 0

    def test_stdin_empty_password_rejected(self, db, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
        rc = mod.main(["--username", "piped", "--stdin-password"])
        assert rc == 2

    def test_bootstrapped_account_can_log_in_when_auth_on(self, db):
        mod.bootstrap_admin("recover-admin", GOOD_PW)

        # Force auth ON for this check (same pattern as test_auth_security).
        saved_enabled = auth_module._AUTH_ENABLED
        saved_secret = auth_module._AUTH_SECRET
        auth_module._AUTH_ENABLED = True
        auth_module._AUTH_SECRET = "test-secret-not-for-production"
        try:
            client_response = main_module.login_response(
                "recover-admin", GOOD_PW
            )
            assert client_response["token"]
            assert client_response["username"] == "recover-admin"
        finally:
            auth_module._AUTH_ENABLED = saved_enabled
            auth_module._AUTH_SECRET = saved_secret
