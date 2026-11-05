"""Stage 8 output: write dev-rehearsal report JSON + Markdown to docs/fan.

Runs the full dev enrichment rehearsal drill against an isolated scratch copy:
- snapshot baseline -> scratch
- acquire real GPU Ark values (clear CC BY 4.0)
- validate, import into NULL gaps, prove idempotency
- rollback scratch to baseline and verify SHA256

Generates:
- docs/fan/stage8_rehearsal.json
- docs/fan/DEV_REHEARSAL_REPORT.md

Never touches production or the shared dev DB.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import dev_rehearsal as dr

OUT = PROJECT_ROOT / "docs" / "fan"


def _markdown(r: dict) -> str:
    lines = [
        "# Stage 8 — Dev Enrichment Rehearsal Report",
        "",
        "**Tool**: `dev_rehearsal.py` (isolated scratch copy; never production).",
        f"**Baseline**: `{r['baseline']}`",
        f"**Scratch (gitignored)**: `{r['scratch']}`",
        "",
        "## 1. Snapshot",
        "",
        f"- Baseline SHA256: `{r['baseline_sha256']}`",
        f"- Scratch SHA256 before: `{r['scratch_sha256_before']}`",
        f"- NULL `tdp_w` gaps before import: `{r['gap_rows_before']}`",
        "",
        "## 2. Validation",
        "",
        f"- accepted: `{r['validation']['accepted']}`",
        f"- rejected: `{r['validation']['rejected']}`",
        f"- quarantined: `{r['validation']['quarantined']}`",
        f"- blocked: `{r['validation']['blocked']}`",
        "",
        "## 3. Import (dev scratch only)",
        "",
        f"- applied: `{r['import_first']['applied']}`",
        f"- skipped (already-filled): `{r['import_first']['skipped']}`",
        f"- rejected: `{r['import_first']['rejected']}`",
        "",
        "## 4. Idempotency",
        "",
        f"- re-run applied: `{r['import_second']['applied']}` "
        + ("✓ idempotent (0 new writes)" if r["idempotent"] else "✗ NOT idempotent"),
        "",
        "## Interpretation",
        "",
        "- The drill writes **only** to the scratch copy; the baseline SHA256 is "
        "recorded above so a follow-up run can prove no mutation.",
        "- GPU Ark is a clear CC BY 4.0 source, so every accepted value is "
        "publishable; rejected values carry explicit reasons (never invented).",
        "- The shared dev DB and production `data/spectra.db` are untouched.",
    ]
    return "\n".join(lines)


def main() -> int:
    baseline = str(PROJECT_ROOT / "data" / "dev" / "spectra_dev.baseline_rollback.db")
    csv = str(PROJECT_ROOT / "data" / "research" / "batch017" / "gpuark-gpu-specs.csv")
    out_dir = str(PROJECT_ROOT / "data" / "dev")
    OUT.mkdir(parents=True, exist_ok=True)

    result = dr.run_rehearsal(baseline, csv, out_dir)

    json_path = OUT / "stage8_rehearsal.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str),
                         encoding="utf-8")

    md_path = OUT / "DEV_REHEARSAL_REPORT.md"
    md_path.write_text(_markdown(result), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())