"""Stage 3 demo: run the enrichment pipeline against the dev DB (read-only).

Produces:
- docs/fan/stage3_dev_audit.json          (audit_dev_db output)
- docs/fan/stage3_gpuark_plan.json        (validated GPU Ark acquisition plan)

All dev-DB reads here are against the isolated copy in data/dev/. Nothing is
written to production data/spectra.db.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.scripts import enrichment_pipeline as ep
from backend.app.scripts import source_acquisition as sa

DEV_DB = PROJECT_ROOT / "data" / "dev" / "spectra_dev.db"
GPUARK_CSV = PROJECT_ROOT / "data" / "research" / "batch017" / "gpuark-gpu-specs.csv"
OUT_DIR = PROJECT_ROOT / "docs" / "fan"


def main() -> None:
    out = OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    # 1) read-only dev DB audit
    audit = ep.audit_dev_db(str(DEV_DB))
    (out / "stage3_dev_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8"
    )
    print("[audit] GPU:", audit["gpu"], "| CPU:", audit["cpu"])

    # 2) validate a sampled slice of GPU Ark acquisitions (read-only gate)
    adapter = sa.GpuArkAdapter.from_csv(str(GPUARK_CSV))
    all_values = sa.acquire(adapter, field="tdp_w")
    print("[acquire] total tdp_w values:", len(all_values))

    # validate treats every value as publishable only if clear + known field
    verdict = ep.validate_acquisitions(all_values[:2000])
    print("[validate] accepted:", verdict["accepted"],
          "rejected:", verdict["rejected"],
          "blocked:", verdict["blocked"])

    (out / "stage3_gpuark_plan.json").write_text(
        json.dumps({"sample_size": 2000, "validate": verdict},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("[done] wrote stage3_dev_audit.json + stage3_gpuark_plan.json")


if __name__ == "__main__":
    main()
