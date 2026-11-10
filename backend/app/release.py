"""Release identity for SPECTRA.

A release is identified by the Git SHA it was built from, the build timestamp,
and the application version. These are injected at build/deploy time via
environment variables; when absent the endpoint reports ``unknown`` rather
than guessing, so a release built without identity injection is still
diagnosable (it just cannot be pinned).

Exposure rules
--------------
- The endpoint reports ONLY: version, SHA, build timestamp, image digest when
  injected, auth enabled state, AI provider configured state, and migration
  status. It never reports internal paths, secret values, database URLs, or
  environment dumps.
- Safe to call without a token (it is a diagnostic surface, not a control
  plane). Everything it returns is already observable through the HTML shell
  and /health.
"""

from __future__ import annotations

import os

from pydantic import BaseModel

from backend.app import auth


class ReleaseIdentity(BaseModel):
    version: str
    git_sha: str
    built_at: str
    image_digest: str | None
    auth_enabled: bool
    ai_provider: str


def _env(name: str, default: str = "unknown") -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    stripped = raw.strip()
    if not stripped:
        return None  # empty → caller uses `or default`
    return stripped


def get_release_identity() -> ReleaseIdentity:
    """Collect the release identity from injected environment variables.

    Missing variables resolve to "unknown" — the endpoint never fabricates a
    SHA or version. ``ai_provider`` reports only the configured state
    ("configured" / "unconfigured"), never a key value.
    """
    provider_configured = bool(
        os.getenv("GEMINI_API_KEY", "").strip()
        and os.getenv("GEMINI_MODEL", "").strip()
    )

    image_digest_raw = os.getenv("SPECTRA_IMAGE_DIGEST")
    image_digest: str | None = None
    if image_digest_raw is not None and image_digest_raw.strip():
        image_digest = image_digest_raw.strip()

    # Single source of truth for the auth flag: the auth module. Resolved at
    # call time through the module so test patches on auth take effect.
    auth_enabled = auth.is_auth_enabled()

    return ReleaseIdentity(
        version=_env("SPECTRA_RELEASE_VERSION", "unknown") or "unknown",
        git_sha=_env("SPECTRA_RELEASE_SHA", "unknown") or "unknown",
        built_at=_env("SPECTRA_RELEASE_BUILT_AT", "unknown") or "unknown",
        image_digest=image_digest,
        auth_enabled=auth_enabled,
        ai_provider="configured" if provider_configured else "unconfigured",
    )
