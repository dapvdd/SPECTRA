#!/usr/bin/env bash
# SPECTRA deployment wrapper — fail-closed guard for production releases.
#
# This script refuses to deploy unless the preflight passes. It is the ONLY
# sanctioned way to bring up a SPECTRA release; running `docker compose up`
# directly bypasses the collision, SHA, and mutable-tag checks.
#
# Usage:
#   ./deploy_release.sh --release-dir /home/david/releases/spectra-<sha>-ops \
#                       --expected-sha <sha> [--dry-run]
#
# What it does:
#   1. Runs the Python preflight (release SHA, dirty checkout, compose
#      collision, mutable tags, backup, migration, disk, volume).
#   2. On any blocker: prints the failures and exits non-zero. Nothing is
#      deployed.
#   3. On success (and not --dry-run): runs `docker compose -f compose.json
#      up -d` from the release directory only.
#
# The script NEVER:
#   - Deploys from a legacy checkout (/home/david/projects/spectra).
#   - Uses `latest` or any mutable tag.
#   - Restarts unrelated services.
#   - Modifies the database volume or its contents.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

RELEASE_DIR=""
EXPECTED_SHA=""
SOURCE_DIR=""
REPO_ROOT_ARG=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --release-dir)
            RELEASE_DIR="$2"
            shift 2
            ;;
        --expected-sha)
            EXPECTED_SHA="$2"
            shift 2
            ;;
        --source-dir)
            SOURCE_DIR="$2"
            shift 2
            ;;
        --repo-root)
            REPO_ROOT_ARG="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: $0 --release-dir DIR --expected-sha SHA [--source-dir DIR] [--repo-root DIR] [--dry-run]" >&2
            exit 2
            ;;
    esac
done

if [[ -z "${RELEASE_DIR}" || -z "${EXPECTED_SHA}" ]]; then
    echo "ERROR: --release-dir and --expected-sha are required." >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Guard 1: refuse to run from a legacy checkout.
# The legacy path is where the old, dirty checkout lives. Deployments must
# come from a release directory only.
# ---------------------------------------------------------------------------
case "${RELEASE_DIR}" in
    */projects/spectra|*/projects/spectra/*)
        echo "REFUSED: ${RELEASE_DIR} is a legacy checkout." >&2
        echo "Deploy only from /home/david/releases/spectra-<sha>-ops." >&2
        exit 1
        ;;
esac

if [[ ! -d "${RELEASE_DIR}" ]]; then
    echo "REFUSED: release directory does not exist: ${RELEASE_DIR}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Guard 2: the release directory must be a spectra-<sha>-ops path.
# ---------------------------------------------------------------------------
release_dir_name="$(basename "${RELEASE_DIR}")"
if [[ ! "${release_dir_name}" =~ ^spectra-[0-9a-f]{7,40}(-ops)?$ ]]; then
    echo "REFUSED: release directory name '${release_dir_name}' does not" >&2
    echo "match the required spectra-<sha>[-ops] pattern." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Guard 3: preflight must pass.
# ---------------------------------------------------------------------------
PYTHON_BIN="$(command -v python3 || command -v python)"
if [[ -z "${PYTHON_BIN}" ]]; then
    echo "REFUSED: neither python3 nor python found on PATH." >&2
    exit 2
fi

echo "Running deployment preflight for ${release_dir_name} ..."
PREFLIGHT_ARGS=(
    --release-dir "${RELEASE_DIR}"
    --expected-sha "${EXPECTED_SHA}"
)
if [[ -n "${SOURCE_DIR}" ]]; then
    PREFLIGHT_ARGS+=(--source-dir "${SOURCE_DIR}")
fi
if [[ -n "${REPO_ROOT_ARG}" ]]; then
    PREFLIGHT_ARGS+=(--repo-root "${REPO_ROOT_ARG}")
    PREFLIGHT_SCRIPT="${REPO_ROOT_ARG}/backend/app/scripts/deploy_preflight.py"
else
    PREFLIGHT_SCRIPT="${REPO_ROOT}/backend/app/scripts/deploy_preflight.py"
fi

"${PYTHON_BIN}" "${PREFLIGHT_SCRIPT}" \
    "${PREFLIGHT_ARGS[@]}"

PREFLIGHT_RC=$?
if [[ ${PREFLIGHT_RC} -ne 0 ]]; then
    echo "REFUSED: preflight failed (rc=${PREFLIGHT_RC})." >&2
    echo "Fix the blockers above before deploying." >&2
    exit 1
fi

if [[ ${DRY_RUN} -eq 1 ]]; then
    echo "DRY-RUN: preflight passed; would deploy ${RELEASE_DIR} at ${EXPECTED_SHA}."
    exit 0
fi

# ---------------------------------------------------------------------------
# Deploy: compose up from the release directory only.
# ---------------------------------------------------------------------------
echo "Deploying ${release_dir_name} at SHA ${EXPECTED_SHA} ..."
cd "${RELEASE_DIR}"
docker compose -f compose.json up -d

echo "Deployment complete. Verify with:"
echo "  curl -fsS http://localhost:8080/api/health"
echo "  curl -fsS http://localhost:8080/api/release"
