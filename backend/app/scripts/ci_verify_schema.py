"""CI schema-verification entry point.

``check_data_integrity.py --schema-only`` verifies a fresh/empty schema, but
in CI the production database is never committed (data/spectra.db is gitignored),
so we must create the schema before verifying it. This script:

1. Initializes a fresh schema (equivalent to init_database) at a path
   controlled by SPECTRA_DATABASE_URL or ``--database``.
2. Runs the migration runner's baseline against that copy.
3. Runs check_data_integrity in schema-only mode (quick_check + FK, no
   row-count floor, since a fresh DB has 0 rows).

It never touches a production database: the target is a fresh disposable copy.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.getenv(
            "SPECTRA_DATABASE_URL",
            str(PROJECT_ROOT / "data" / "spectra.db"),
        ),
        help="Target database path (default: SPECTRA_DATABASE_URL or data/spectra.db).",
    )
    args = parser.parse_args()
    target = Path(args.database)
    if "sqlite://" in args.database:
        target = Path(args.database.replace("sqlite:///", ""))
    target.parent.mkdir(parents=True, exist_ok=True)

    # ---- 1. Fresh schema ----
    from backend.app.database import Base, engine
    from backend.app.models import (  # noqa: F401  (register tables)
        BenchmarkResult,
        BuildConversation,
        BuildMessage,
        CPUSpecification,
        GPUSpecification,
        Hardware,
        Source,
    )
    import sqlite3
    from sqlalchemy import create_engine as _ce

    target_url = "sqlite:///" + str(target).replace("\\", "/")
    target_engine = _ce(target_url, connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=target_engine)
    finally:
        target_engine.dispose()
    print(f"fresh schema created at: {target}")

    # ---- 2. Migration runner baseline ----
    runner_result = subprocess.run(
        [sys.executable, "backend/app/migrations/runner.py", "--report", "--database", str(target)],
        check=False,
    )
    if runner_result.returncode != 0:
        print("FAIL: migration runner did not complete cleanly")
        return 1

    # ---- 3. Integrity check (schema-only) ----
    check_result = subprocess.run(
        [
            sys.executable,
            "backend/app/scripts/check_data_integrity.py",
            "--database", str(target),
            "--schema-only",
        ],
        check=False,
    )
    if check_result.returncode != 0:
        print("FAIL: data-integrity check did not pass on the fresh schema")
        return 1

    print("PASS: CI schema verification succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
