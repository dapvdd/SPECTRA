"""
SPECTRA Batch 017 - GPU Ark CC BY 4.0 enrichment (APPLY)

SOURCE: GPU Ark GPU specifications & benchmarks dataset
URL:    https://gpuark.com/datasets/
LICENSE: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
SHA256: bcaba010961cdeca4d2260028d7f27f2c18317e67ffbddec7a09d3dddfa9f734
FETCHED: 2026-10-28 (13,566 GPU rows)
ATTRIBUTION: GPU Ark (2026). GPU specifications & benchmarks dataset.
             https://gpuark.com/datasets/

VALIDATION FINDINGS (dry-run):
  - Total candidates: 993
  - Valid (non-empty values): 965
    - interface: 938 (PCIe, AGP, MXM, IGP, Ring Bus, FSB, PCI, QPI, Apple MPX)
    - memory_bus_width_bits: 27 (HBM bus widths for Instinct/A100/H100/H800)
  - Invalid EXCLUDED (28):
    - 28 interface records where GPU Ark bus_interface is empty in source.
      These are console/SoC/embedded GPUs (Wii U, Xbox, PlayStation, Switch,
      Steam Deck, Ryzen Z1/Z2). GPU Ark has no PCIe bus interface data for
      custom unified-memory systems. Value not fabricated.
  - Zero same-name-to-multiple-interface conflicts.
  - Zero duplicate hardware IDs per field.

APPLY FIELDS:
  gpu_specifications.interface            <- GPU Ark bus_interface (938 records)
  gpu_specifications.memory_bus_width_bits <- GPU Ark bus_width       (27 records)

CONSTRAINTS:
  - Source_id=4 (GPU Ark, already registered)
  - batch_no=18 (avoids collision with segment batch_no=17)
  - NULL-only guard: never overwrites existing non-NULL values
  - match_method: normalized_name + vendor_prefix_stripped
  - confidence: medium (normalized name match; corroboration by boost clocks
    where available in GPU Ark, but conservative acceptance of non-PCIe
    interface strings as published by GPU Ark)
  - evidence_status: verified
  - license_name: CC BY 4.0

USAGE:
  python batch017_apply.py          # dry-run report
  python batch017_apply.py --apply # write to staging DB
"""

import datetime
import json
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STAGING_DB = REPO / "data" / "spectra_staging.db"
DRYRUN_JSON = REPO / "data" / "research" / "batch017" / "dry_run_results.json"
META_JSON = REPO / "data" / "research" / "batch017" / "source_metadata.json"
BACKUP_PRE = REPO / "data" / "spectra_staging.db.pre_batch018_bak"
BACKUP_POST = REPO / "data" / "spectra_staging.db.post_batch018_bak"

SOURCE_ID = 4
BATCH_NO = 18
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

VALID_INTERFACE_VALUES = None  # loaded lazily

PROVENANCE_COLS = [
    "hardware_id", "source_id", "table_name", "field_name",
    "evidenced_value", "source_url", "license_name",
    "attribution", "access_date", "confidence",
    "evidence_status", "source_reference", "match_method",
    "batch_no", "notes", "recorded_at",
]


def _is_empty(v):
    return v is None or str(v).strip() in ("", "None", "nan", "NaN")


def load_valid_records():
    """Load and filter the dry-run records: only non-empty source_value rows."""
    dry = json.load(open(DRYRUN_JSON, encoding="utf-8"))
    meta = json.load(open(META_JSON, encoding="utf-8"))
    recs = dry["records"]
    valid = [r for r in recs if not _is_empty(r.get("source_value"))]
    excluded = [r for r in recs if _is_empty(r.get("source_value"))]
    return valid, excluded, meta, dry


def preapply_check(con, records):
    """Verify every record passes the NULL guard (additive-only)."""
    failures = []
    for r in records:
        cur = con.execute(
            f"SELECT {r['field']} FROM gpu_specifications WHERE hardware_id=?",
            (r["hardware_id"],)
        ).fetchone()
        existing = cur[0] if cur else None
        if existing is not None:
            failures.append({
                "hardware_id": r["hardware_id"],
                "field": r["field"],
                "existing": existing,
                "proposed": r["source_value"],
                "name": r["name"],
            })
    return failures


def run(staging_path, dry_run=True):
    records, excluded, meta, dry = load_valid_records()

    con = sqlite3.connect(staging_path)
    con.row_factory = sqlite3.Row

    # Field-level breakdown
    by_field = Counter(r["field"] for r in records)
    by_iface = Counter(r["source_value"] for r in records if r["field"] == "interface")

    # Pre-apply NULL guard check
    failures = preapply_check(con, records) if not dry_run else []
    if failures:
        return {"error": f"NULL guard violations: {len(failures)}",
                "failures": failures[:10]}

    if dry_run:
        con.close()
        return {
            "mode": "dry-run",
            "records_total": len(dry["records"]),
            "valid_to_apply": len(records),
            "excluded_empty_source": len(excluded),
            "excluded_fields": Counter(r["field"] for r in excluded),
            "by_field": dict(by_field),
            "interface_value_distribution": dict(by_iface),
            "bus_width_distribution": dict(Counter(r["source_value"] for r in records
                                                   if r["field"] == "memory_bus_width_bits")),
            "meta": meta,
        }

    # Write to staging DB
    applied_iface = 0
    applied_bw = 0
    prov_rows = []

    con.execute("PRAGMA foreign_keys=ON")
    con.execute("BEGIN IMMEDIATE")

    try:
        for r in records:
            hwid = r["hardware_id"]
            field = r["field"]
            val = r["source_value"]
            ark_id = r.get("ark_id", "")

            # Guard: ensure NULL before writing
            cur = con.execute(
                f"SELECT {field} FROM gpu_specifications WHERE hardware_id=?",
                (hwid,)
            ).fetchone()
            existing = cur[0] if cur else None
            if existing is not None:
                raise RuntimeError(
                    f"NULL guard violated: hardware_id={hwid} field={field} "
                    f"has existing value {existing!r}, cannot overwrite"
                )

            con.execute(
                f"UPDATE gpu_specifications SET {field}=? WHERE hardware_id=?",
                (val, hwid)
            )

            # Provenance row
            con.execute(
                f"""INSERT INTO field_provenance (
                    {", ".join(PROVENANCE_COLS)}
                ) VALUES ({", ".join("?" * len(PROVENANCE_COLS))})""",
                (
                    hwid, SOURCE_ID, "gpu_specifications", field,
                    str(val), meta["url"], "CC BY 4.0",
                    meta["attribution"], None, "medium",
                    "verified", ark_id,
                    "normalized_name + vendor_prefix_stripped",
                    BATCH_NO,
                    f"batch018: GPU Ark bus_interface enrichment",
                    NOW,
                )
            )

            if field == "interface":
                applied_iface += 1
            elif field == "memory_bus_width_bits":
                applied_bw += 1

    except Exception as e:
        con.execute("ROLLBACK")
        con.close()
        return {"error": f"Transaction failed: {e}"}

    con.execute("COMMIT")
    con.close()

    return {
        "mode": "apply",
        "applied_iface": applied_iface,
        "applied_bw": applied_bw,
        "applied_total": applied_iface + applied_bw,
        "excluded_empty_source": len(excluded),
        "batch_no": BATCH_NO,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Write to staging DB")
    args = ap.parse_args()

    if not STAGING_DB.exists():
        print(f"ERROR: staging DB not found at {STAGING_DB}")
        return 1

    # Backup before any write
    if not args.apply:
        print("MODE: dry-run")
    else:
        if BACKUP_PRE.exists():
            BACKUP_PRE.unlink()
        shutil.copy2(STAGING_DB, BACKUP_PRE)
        print(f"backup: {BACKUP_PRE}")

    result = run(str(STAGING_DB), dry_run=not args.apply)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return 1

    import json as _json
    print(_json.dumps(result, indent=2, ensure_ascii=False))

    if args.apply:
        # Verify integrity and coverage delta
        con = sqlite3.connect(str(STAGING_DB))
        con.row_factory = sqlite3.Row

        # integrity check
        qc = con.execute("PRAGMA quick_check").fetchone()[0]
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        con.close()

        print()
        print(f"integrity_check: {qc}")
        print(f"foreign_key_violations: {len(fk)}")
        print(f"applied: {result['applied_total']}")

        # Keep post-apply snapshot for independent audit
        if BACKUP_POST.exists():
            BACKUP_POST.unlink()
        shutil.copy2(STAGING_DB, BACKUP_POST)
        print(f"post-apply snapshot: {BACKUP_POST}")

        print("\nPhase 2 GPU enrichment complete. Run verify before promoting to live.")
        print("To promote: Copy data/spectra_staging.db over data/spectra.db")

    return 0


if __name__ == "__main__":
    sys.exit(main())
