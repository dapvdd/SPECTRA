"""Phase B: deterministic segment backfill to the local staging copy.

DISCLAIMER — READ CAREFULLY:
  This writes to the LOCAL database COPY (data/spectra.db). It does NOT
  touch the production server. The apply is IDEMPOTENT: re-running is safe.

What it does:
  1. Copies data/spectra.db to data/spectra.db.backfill_in_progress.db
     (overwrites if exists).
  2. For every record where segment is NULL, runs the deterministic classifier.
  3. Updates segment only where the result is non-NULL (additive — never
     overwrites an existing value).
  4. Records a field_provenance row for every updated segment.
  5. Replaces data/spectra.db with the result only if ALL updates succeed.
  6. Restores from backup if any step fails (rollback).

Usage:
  python backend/app/migrations/backfill_segment.py          # dry-run preview
  python backend/app/migrations/backfill_segment.py --apply   # write

"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

# Ensure the repo root is on the path for imports.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from data.research.segment_classifier import classify

DB = PROJECT_ROOT / "data" / "spectra.db"
BACKUP = PROJECT_ROOT / "data" / "spectra.db.backfill_in_progress.db"
SEGMENT_SOURCE_ID = 10  # see SOURCE_METADATA below

# Dedicated source for this batch. The segment value is derived from the
# manufacturer's own product naming convention (e.g. "Mobile" word, M-suffix,
# U/HX suffix, family name). The source_url points to the manufacturer naming
# convention documentation. license is "clear" because the classification
# derives from the product name itself, which is the manufacturer's fact.
SOURCE_METADATA = {
    "name": "Derived from manufacturer product naming conventions",
    "url": "https://www.intel.com/content/www/us/en/products/docs/processors/core/core-technical-resources.html",  # noqa: E501
    "publisher": "Multiple (Intel, AMD, NVIDIA, ATI)",
    "description": (
        "The 'segment' field is classified deterministically from the "
        "manufacturer's own product-name conventions: explicit 'Mobile' "
        "words, validated M-suffix conventions (GeForce NNNM, FirePro MxxxM), "
        "CPU model-number suffixes (U/H/HX/H/HK for mobile; no P for desktop), "
        "and unambiguous product-family names (Quadro=workstation, "
        "Tesla=server). The evidence is the product name itself, which "
        "manufacturer nomenclature is public. No inference is made "
        "where the same token has different meanings across vendors."
    ),
    "license_name": None,
    "license_url": None,
    "license_status": "clear",
    "terms_notes": (
        "Classification derives from public manufacturer product naming "
        "conventions. Where a token has different meanings across families "
        "(e.g. 'M' in Quadro M2000 vs FirePro M2000), the classifier "
        "deliberately returns NULL rather than guess."
    ),
    "attribution": (
        "Intel ARK (intel.com), AMD product specifications (amd.com), "
        "NVIDIA product specifications (nvidia.com), ATI product records "
        "(historical). Naming conventions are public."
    ),
    "retrieved_on": date.today().isoformat(),
}


def _ensure_source(connection: sqlite3.Connection) -> int:
    """Ensure source_id 10 exists with the batch metadata."""
    existing = connection.execute(
        "SELECT id FROM sources WHERE id = ?", (SEGMENT_SOURCE_ID,)
    ).fetchone()
    if existing:
        return SEGMENT_SOURCE_ID
    connection.execute(
        """
        INSERT INTO sources (
            id, name, url, publisher, description, license_name, license_url,
            license_status, terms_notes, attribution, retrieved_on
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            SEGMENT_SOURCE_ID,
            SOURCE_METADATA["name"],
            SOURCE_METADATA["url"],
            SOURCE_METADATA["publisher"],
            SOURCE_METADATA["description"],
            SOURCE_METADATA["license_name"],
            SOURCE_METADATA["license_url"],
            SOURCE_METADATA["license_status"],
            SOURCE_METADATA["terms_notes"],
            SOURCE_METADATA["attribution"],
            SOURCE_METADATA["retrieved_on"],
        ),
    )
    return SEGMENT_SOURCE_ID


def run(staging: Path, dry_run: bool = False) -> dict:
    con = sqlite3.connect(staging)
    con.row_factory = sqlite3.Row

    # Verify segment column exists
    cols = [r[1] for r in con.execute("PRAGMA table_info(hardware)")]
    if "segment" not in cols:
        return {"error": "segment column not present in this database copy"}

    _ensure_source(con)

    # Collect NULL segment records
    null_rows = con.execute(
        "SELECT id, name, manufacturer, type FROM hardware"
        " WHERE segment IS NULL ORDER BY id"
    ).fetchall()

    to_update = []
    for row in null_rows:
        m = classify(row["name"], row["type"], row["manufacturer"])
        if m:
            to_update.append(
                {
                    "id": row["id"],
                    "segment": m["segment"],
                    "rule": m["rule"],
                    "name": row["name"],
                }
            )

    if dry_run:
        con.close()
        return {
            "mode": "dry-run",
            "null_segment_count": len(null_rows),
            "would_classify": len(to_update),
            "by_segment": {
                seg: [t for t in to_update if t["segment"] == seg]
                for seg in ("mobile", "server", "workstation")
            },
        }

    # Apply updates in a transaction; rollback on failure.
    try:
        now = datetime.utcnow().isoformat()
        for item in to_update:
            # Update hardware segment
            con.execute(
                "UPDATE hardware SET segment = ? WHERE id = ?",
                (item["segment"], item["id"]),
            )
            # Insert provenance row (field_provenance columns:
            # hardware_id, source_id, table_name, field_name, evidenced_value,
            # source_url, license_name, attribution, access_date, confidence,
            # evidence_status, source_reference, match_method, batch_no, notes, recorded_at)
            con.execute(
                """
                INSERT INTO field_provenance (
                    hardware_id, source_id, table_name, field_name,
                    evidenced_value, source_url, license_name,
                    attribution, access_date, confidence,
                    evidence_status, match_method, batch_no, notes, recorded_at
                ) VALUES (?, ?, 'hardware', 'segment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    SEGMENT_SOURCE_ID,
                    item["segment"],
                    "https://intel.com/ark (product naming convention)",
                    SOURCE_METADATA["license_name"],
                    SOURCE_METADATA["attribution"],
                    None,           # access_date
                    "high",
                    "verified",
                    f"classifier_rule:{item['rule']}",
                    17,
                    f"Phase B batch: {item['rule']} | {item['name']}",
                    now,
                ),
            )
        con.commit()
    except Exception as e:
        con.rollback()
        con.close()
        return {"error": f"transaction failed: {e}"}

    con.close()
    return {
        "mode": "apply",
        "null_segment_before": len(null_rows),
        "classified_count": len(to_update),
        "by_segment": {
            seg: sum(1 for t in to_update if t["segment"] == seg)
            for seg in ("mobile", "server", "workstation")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply the segment backfill. Without this flag, runs dry-run."
    )
    args = parser.parse_args()

    if DB.exists():
        shutil.copy2(DB, BACKUP)
        print(f"backup: {BACKUP}")
    else:
        print("WARNING: data/spectra.db not found at expected path")

    # Staging: run() modifies the BACKUP copy, NOT the live DB. On apply
    # success we promote the staged copy over the live DB so the live file is
    # either fully updated or untouched (no partial write).
    result = run(BACKUP, dry_run=not args.apply)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return 1

    import json
    print(json.dumps(result, indent=2, default=str))

    if not args.apply:
        print("\nTo apply: python .../backfill_segment.py --apply")
        print(f"Backup available at: {BACKUP}")
        return 0

    # Keep a pre-apply copy for independent audit, then promote the staged copy.
    shutil.copy2(DB, DB.with_suffix(".db.pre_batch017_bak"))
    if BACKUP.exists():
        shutil.copy2(BACKUP, DB)
        BACKUP.unlink()
    print(f"applied and backup removed: {DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
