# SPECTRA V3.1 — Deployment Guardrails

Date: 2026-11-10
Scope: the fail-closed deployment path added in M2 and how to use it. These
guardrails exist because the baseline found a legacy dirty checkout one
command away from a production takeover (F-03) and mutable `:latest` tags on
the host (F-02).

---

## 1. The two tools

| Tool | Path | Role |
|---|---|---|
| Preflight | `backend/app/scripts/deploy_preflight.py` | 8 fail-closed checks against a release directory; exits non-zero on any blocker |
| Wrapper | `backend/app/scripts/deploy_release.sh` | Operator entry point: path guards → preflight → (only then) the deploy commands; `--dry-run` stops after preflight |

## 2. Preflight checks (all must pass for a deploy)

| # | Check | Blocker | What it refuses |
|---|---|---|---|
| 1 | `release_sha` | Yes | A release whose git SHA (from the source checkout) does not equal `--expected-sha` |
| 2 | `git_clean` | No (warn) | Modified tracked files in the source checkout (transient ops files in the ops dir do not fail this) |
| 3 | `compose_collision` | Yes | A compose project named `spectra` colliding with another project's containers |
| 4 | `image_tags` | Yes | Mutable tags (`latest`, floating branches) in compose.json |
| 5 | `backup_available` | Yes | No recent backup before deploying (deployments must have a rollback point) |
| 6 | `migration_compatible` | Yes | A backup whose schema version is ahead of the runner's latest migration |
| 7 | `disk_space` | Yes | Free space below the floor |
| 8 | `volume_identity` | Yes | A volume identity mismatch (wrong/expired data volume) |

Exit codes: `0` all passed, `1` blocked, `2` usage error. `--json` gives
machine-readable output for CI.

## 3. Accepted directory shapes

The production layout is an **ops dir + sibling source checkout**, which both
shapes are supported:

```text
/home/david/releases/spectra-<sha>-ops/    ← ops dir: compose.json, backups, evidence (no .git)
/home/david/releases/spectra-<sha>/        ← clean git checkout at the release SHA
```

```bash
# Shape A — release dir IS a git checkout:
python -m backend.app.scripts.deploy_preflight \
    --release-dir /path/to/release --expected-sha <sha>

# Shape B — bare ops dir + separate source (the david-lab production shape):
python -m backend.app.scripts.deploy_preflight \
    --release-dir /home/david/releases/spectra-75eba50-ops \
    --source-dir  /home/david/releases/spectra-75eba50 \
    --repo-root   /home/david/releases/spectra-75eba50 \
    --expected-sha 75eba50b1f09052f40409f6066a2ac030344d1a0
```

`--repo-root` is needed when running from a standalone copy on a host without
the full repo (it locates `backend/app/migrations/runner.py`).

## 4. The wrapper (deploy_release.sh)

```bash
bash backend/app/scripts/deploy_release.sh \
    --release-dir /home/david/releases/spectra-<sha>-ops \
    --source-dir  /home/david/releases/spectra-<sha> \
    --repo-root   /home/david/releases/spectra-<sha> \
    --expected-sha <full-sha> \
    --dry-run          # ALWAYS dry-run first
```

Guards, in order:

1. **Legacy checkout refusal** — `/home/david/projects/spectra` is refused
   outright (verified live: `REFUSED: ... is a legacy checkout`), because a
   dirty tree shipping the same project/container names/port is the takeover
   hazard (F-03).
2. **SHA agreement** — refuses when `--expected-sha` disagrees with the
   release directory's identity.
3. **Preflight gate** — runs the 8 checks; any blocker aborts before any
   mutating command.
4. **python3 fallback** — uses `python3` when `python` is absent (the
   david-lab host has only `python3`).
5. **`--dry-run`** — prints the deploy plan and exits 0 without touching
   containers.

## 5. Verified live (david-lab, 2026-11-10, read-only toward production)

| Scenario | Result |
|---|---|
| Preflight on the real ops dir (`spectra-75eba50-ops` + source checkout) | **8/8 PASS** |
| Preflight on the legacy checkout (`/home/david/projects/spectra`) | **REFUSED, 5 blockers** (wrong SHA + dirty tree + others) |
| Wrapper dry-run on the real release | **Passed; no mutation** |
| Wrapper on legacy path | **REFUSED** |

## 6. Rules the guardrails enforce (and what they cannot)

Enforced:
- No deploy without an expected-SHA match and a recent backup.
- No deploy from a dirty or legacy tree.
- No mutable image tags in a release compose file.

NOT enforceable by tooling (operator discipline):
- Which SHA is *supposed* to deploy — the caller supplies `--expected-sha`;
  verify it against the release docs, not memory.
- Post-deploy verification — run the runbook's post-deploy checklist.
- The `:latest` images already on the host remain a latent hazard until
  manually removed (user-gated; see SECURITY_FINDINGS.md F-02).

## 7. Release identity in the browser (M2.5)

`/api/release` (cache-defeated fetch in `frontend/src/releaseIdentity.js`)
reports `{version, git_sha, built_at, auth_enabled, ai_provider_state}`.
`compareClientWithServer()` labels a tab `current` / `stale` / `unidentified` /
`unknown` against the executing bundle's build SHA — the stale-tab incident's
permanent diagnostic. The endpoint carries no secrets (tested).
