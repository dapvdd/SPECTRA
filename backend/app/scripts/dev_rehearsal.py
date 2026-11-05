"""Stage 8 — dev enrichment rehearsal drill.

Proves the full read-only-to-dev enrichment cycle on an **isolated scratch
copy** of the dev database (never production, never the shared dev DB):

1. Snapshot: copy a baseline dev DB to a scratch rehearsal path.
2. Acquire: build real GPU Ark acquisitions (clear CC BY 4.0 source).
3. Validate: gate the batch (accepted/rejected/quarantined/blocked).
4. Import: apply the accepted values into NULL gaps on the scratch copy.
5. Idempotency: re-run the same batch -> applied == 0.
6. Rollback: restore the scratch copy from the baseline snapshot.

The drill is fully deterministic and reports side-effects explicitly, so a
future run can prove the scratch copy matches the baseline again.

Contract:
- ``rehearsal_scratch_path(out_dir)`` — deterministic scratch path (READY suffix).
- ``prepare_scratch(baseline, scratch)`` — copy baseline -> scratch.
- ``run_rehearsal(baseline_db, csv_path, out_dir)`` — the whole drill, returns
  a deterministic result dict (never touches production or the shared dev DB).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.models import (
    FieldProvenance,
    GPUSpecification,
    Hardware,
)
from backend.app.scripts import enrichment_pipeline as ep
from backend.app.scripts import source_acquisition as sa

# Fields to rehearse — tdp_w is the well-attested GPU Ark field with a known
# coverage pattern from Stage 3 (3491/3501 populated in the full source; the
# real NULL gap in the DB is what import fills, nothing else).
_REHEARSAL_FIELDS = ("tdp_w", "boost_clock_mhz", "memory_size_gb")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rehearsal_scratch_path(out_dir: Path) -> Path:
    """Deterministic scratch path for a ready rehearsal DB (never committed)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "spectra_rehearsal_READY.db"


def prepare_scratch(baseline: Path, scratch: Path, force: bool = False) -> None:
    """Copy ``baseline`` -> ``scratch`` so the drill starts from the baseline."""
    if scratch.exists() and not force:
        scratch.unlink()
    shutil.copyfile(baseline, scratch)


def _build_acquisitions(csv_path: Path, fields=("tdp_w",)) -> list:
    adapter = sa.GpuArkAdapter.from_csv(str(csv_path))
    values = []
    for field in fields:
        values.extend(sa.acquire(adapter, field=field))
    return values


def _gap_fill_rows(db_path: str) -> int:
    """Count NULL tdp_w rows in the scratch copy (the actionable gap)."""
    conn = __import__("sqlite3").connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM gpu_specifications WHERE tdp_w IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()


def run_rehearsal(baseline_db: str, csv_path: str, out_dir: str) -> dict:
    """Run the full dev rehearsal drill; return a deterministic result dict.

    Copy semantics: the baseline file is copied to a scratch path; EVERY write
    happens only on the scratch copy. The baseline and the shared dev DB are
    never mutated.
    """
    baseline = Path(baseline_db)
    if not baseline.is_file():
        raise FileNotFoundError(f"baseline db not found: {baseline}")
    csv = Path(csv_path)
    if not csv.is_file():
        raise FileNotFoundError(f"source csv not found: {csv}")

    scratch = rehearsal_scratch_path(Path(out_dir))
    prepare_scratch(baseline, scratch)

    baseline_sha = _sha256(baseline)
    scratch_sha_before = _sha256(scratch)

    # Eyeball null gap on the scratch copy before import.
    gap_before = _gap_fill_rows(str(scratch))

    values = _build_acquisitions(csv, fields=_REHEARSAL_FIELDS)
    validation = ep.validate_acquisitions(values)

    # Import into the scratch copy only.
    first = ep.import_dev(str(scratch), values)
    scratch_sha_after_import = _sha256(scratch)

    # Idempotency proof: re-running the same batch writes nothing new.
    second = ep.import_dev(str(scratch), values)

    hmm = f"scratch-after-import:{scratch_sha_after_import}"
    return {
        "baseline": str(baseline),
        "scratch": str(scratch),
        "baseline_sha256": baseline_sha,
        "scratch_sha256_before": scratch_sha_before,
        "gap_rows_before": gap_before,
        "validation": validation,
        "import_first": first,
        "import_second": second,
        "idempotent": second["applied"] == 0,
        "confirm": hmm,
    }


def rollback_scratch(scratch: Path, baseline: Path) -> dict:
    """Restore the scratch copy from the baseline (dev-only, copies the file).

    Raises ``FileNotFoundError`` if ``baseline`` does not exist (never create
    a database by copying from a missing source).
    """
    if not baseline.is_file():
        raise FileNotFoundError(f"baseline not found: {baseline}")
    if not scratch.is_file():
        raise FileNotFoundError(f"scratch db not found: {scratch}")
    result = ep.rollback_dev(str(scratch), str(baseline))
    return {
        **result,
        "restored_sha256": _sha256(scratch),
        "baseline_sha256": _sha256(baseline),
        "matches_baseline": _sha256(scratch) == _sha256(baseline),
    }


def main() -> int:
    import argparse
    import json

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        default=str(PROJECT_ROOT / "data" / "dev" / "spectra_dev.baseline_rollback.db"),
        help="Baseline dev DB snapshot (default: dev baseline_rollback.db).",
    )
    parser.add_argument(
        "--csv",
        default=str(PROJECT_ROOT / "data" / "research" / "batch017" / "gpuark-gpu-specs.csv"),
        help="GPU Ark CSV (clear CC BY 4.0).",
    )
    parser.add_argument(
        "--out-dir",
        default=str(PROJECT_ROOT / "data" / "dev"),
        help="Where the scratch rehearsal DB is written (gitignored).",
    )
    args = parser.parse_args()

    result = run_rehearsal(args.baseline, args.csv, args.out_dir)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())