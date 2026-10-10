"""Batch 010 Workstream B — external identifier source-1 audit.

Determines whether every external identifier currently labelled source_id=1
(PassMark) can be reconciled to a specific base-import artifact value, and
whether the stored source label is inaccurate.

Writes id_audit_results.json and id_audit_patch.csv (affected rows + intended
new source targets) into the batch010 research directory.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.importers.cpu_normalizer import normalize_name  # noqa: E402
from backend.app.services.identifier_source import (  # noqa: E402
    AMD_CSV_SOURCE_NAME,
    INTEL_CSV_SOURCE_NAME,
)

HOME = Path.home()
INTEL_CSV = HOME / "Downloads" / "intel-cpus.csv"
AMD_CSV = HOME / "Downloads" / "amd-cpus.csv"
PASSMARK_CSV = HOME / "Downloads" / "benchmark-cpus.csv"
DB = REPO_ROOT / "data" / "spectra.db"
BATCH_DIR = REPO_ROOT / "data" / "research" / "batch010"


def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    intel_rows = load_csv(INTEL_CSV)
    amd_rows = load_csv(AMD_CSV)
    pm_rows = load_csv(PASSMARK_CSV)

    # Registered source names for the base-import artifacts (batch 009).
    INTEL_SOURCE_NAME = INTEL_CSV_SOURCE_NAME
    AMD_SOURCE_NAME = AMD_CSV_SOURCE_NAME

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    intel_ids = set()
    col_cpuid = None
    for h in (intel_rows[0].keys() if intel_rows else []):
        if h and h.lower() == "cpuid":
            col_cpuid = h
    if col_cpuid:
        intel_ids = {row.get(col_cpuid, "").strip() for row in intel_rows}
        intel_ids.discard("")

    amd_tray = {row.get("Product ID Tray", "").strip() for row in amd_rows}
    amd_boxed = {row.get("Product ID Boxed", "").strip() for row in amd_rows}
    amd_mpk = {row.get("Product ID MPK", "").strip() for row in amd_rows}

    # PassMark SourceUrl id namespace (for the negative check)
    pm_url_ids = set()
    for row in pm_rows:
        url = (row.get("SourceUrl") or "")
        if "id=" in url:
            pm_url_ids.add(url.split("id=")[-1].strip())

    rows = con.execute(
        "SELECT e.id, e.hardware_id, h.name, h.manufacturer, e.identifier_type, "
        "e.external_id, e.source_id "
        "FROM external_identifiers e JOIN hardware h ON h.id = e.hardware_id "
        "ORDER BY e.id"
    ).fetchall()

    stats = Counter()
    mismatched_entity = []
    not_in_expected_file = []

    rows_out = []
    for r in rows:
        eid = r["external_id"]
        itype = r["identifier_type"]
        rec = {
            "identifier_id": r["id"],
            "hardware_id": r["hardware_id"],
            "hardware_name": r["name"],
            "hardware_manufacturer": r["manufacturer"],
            "identifier_type": itype,
            "external_id": eid,
            "stored_source_id": r["source_id"],
        }

        if itype == "intel_cpu_id":
            in_intel = eid in intel_ids
            in_pm = eid in pm_url_ids
            entity_ok = r["manufacturer"] == "Intel"
            rec["expected_source_name"] = INTEL_SOURCE_NAME
            rec["in_intel_cpuids"] = in_intel
            rec["in_passmark_url_ids"] = in_pm
            rec["entity_is_intel"] = entity_ok
            if not entity_ok:
                mismatched_entity.append((r["id"], itype, r["manufacturer"]))
            if not in_intel:
                not_in_expected_file.append((r["id"], itype, eid))
            stats["intel_cpu_id_total"] += 1
            if in_intel:
                stats["intel_cpu_id_matches_intel_csv"] += 1
            if entity_ok:
                stats["intel_cpu_id_on_intel_hw"] += 1
        elif itype in ("product_id_tray", "product_id_boxed", "product_id_mpk"):
            bucket = {"product_id_tray": amd_tray,
                      "product_id_boxed": amd_boxed,
                      "product_id_mpk": amd_mpk}[itype]
            rec["expected_source_name"] = AMD_SOURCE_NAME
            rec["in_amd_product_ids"] = eid in bucket
            rec["entity_is_amd"] = r["manufacturer"] == "AMD"
            if r["manufacturer"] != "AMD":
                mismatched_entity.append((r["id"], itype, r["manufacturer"]))
            if eid not in bucket:
                not_in_expected_file.append((r["id"], itype, eid))
            stats["amd_product_id_total"] += 1
            if eid in bucket:
                stats["amd_product_id_matches_amd_csv"] += 1
            if r["manufacturer"] == "AMD":
                stats["amd_product_id_on_amd_hw"] += 1
        else:
            rec["expected_source_name"] = None
            stats["unknown_type"] += 1

        rows_out.append(rec)

    stats["total"] = len(rows)
    mapped_to_intel = sum(1 for r in rows_out if r["expected_source_name"] == INTEL_SOURCE_NAME)
    mapped_to_amd = sum(1 for r in rows_out if r["expected_source_name"] == AMD_SOURCE_NAME)
    stats["mapped_to_intel"] = mapped_to_intel
    stats["mapped_to_amd"] = mapped_to_amd

    # verify uniqueness of updates: (hardware_id, new source, identifier_type, external_id)
    target_keys = [
        (r["hardware_id"], r["expected_source_name"], r["identifier_type"], r["external_id"])
        for r in rows_out if r["expected_source_name"] is not None
    ]
    dupes = [k for k, c in Counter(target_keys).items() if c > 1]
    stats["duplicate_target_keys"] = len(dupes)

    summary = {
        "intel_csv_rows": len(intel_rows),
        "amd_csv_rows": len(amd_rows),
        "passmark_rows": len(pm_rows),
        "intel_cpuid_count": len(intel_ids),
        "passmark_url_id_count": len(pm_url_ids),
        "stats": dict(stats),
        "mismatched_entity_rows": mismatched_entity[:20],
        "not_in_expected_file_rows": not_in_expected_file[:20],
        "not_in_expected_file_count": len(not_in_expected_file),
        "conclusion_proven": bool(
            stats["intel_cpu_id_total"]
            and stats["intel_cpu_id_matches_intel_csv"] == stats["intel_cpu_id_total"]
            and stats["intel_cpu_id_on_intel_hw"] == stats["intel_cpu_id_total"]
            and stats["amd_product_id_total"]
            and stats["amd_product_id_matches_amd_csv"] == stats["amd_product_id_total"]
            and stats["amd_product_id_on_amd_hw"] == stats["amd_product_id_total"]
            and not mismatched_entity
            and not not_in_expected_file
        ),
    }

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    with open(BATCH_DIR / "id_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    patch = [r for r in rows_out if r["expected_source_name"] is not None]
    with open(BATCH_DIR / "id_audit_patch.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "identifier_id", "hardware_id", "hardware_name", "hardware_manufacturer",
            "identifier_type", "external_id", "stored_source_id", "expected_source_name",
        ])
        writer.writeheader()
        for r in patch:
            writer.writerow({k: r[k] for k in writer.fieldnames})

    print("=== external identifier audit summary ===")
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())