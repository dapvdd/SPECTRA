"""Batch 008 - Extract and reconcile evidence provenance for batches 001-006.

This module reads the committed research artifacts for every enrichment batch,
normalises each evidence record into a single structure, reconciles each
record against the live database value, and reports which records can be
reliably traced to a persisted specification value.

Run as a script for the audit-only path (writes provenance_audit.json and
evidence_reconciliation.csv). Functionality for writing the records into the
database lives in load_provenance.py.

The module never writes to the hardware specification tables.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
RESEARCH_DIR = DATA_DIR / "research"

# Tables and columns that the hardware enrichment batches were permitted to
# write. Anything outside this set is an invalid field reference.
PERMITTED_FIELDS = {
    "hardware": {
        "release_date",
        "architecture",
    },
    "cpu_specifications": {
        "cores",
        "threads",
        "base_clock_ghz",
        "boost_clock_ghz",
        "tdp_w",
        "process_node_nm",
        "socket",
    },
    "gpu_specifications": {
        "memory_gb",
        "memory_type",
        "core_clock_mhz",
        "boost_clock_mhz",
        "vram_bandwidth_gbps",
        "memory_bus_width_bits",
        "tdp_w",
        "interface",
        "length_mm",
    },
}

# Documented licence/attribution facts, taken only from committed artifacts.
LICENSE_BY_SOURCE = [
    ("wikipedia", "CC BY-SA 4.0", None,
     "Wikipedia contributors; CC BY-SA 4.0; share-alike applies to derived uses."),
    ("gpu ark", "CC BY 4.0", None,
     "GPU Ark (2026). GPU specifications & benchmarks dataset. "
     "https://gpuark.com/datasets/ ; CC BY 4.0 attribution required."),
    ("techpowerup", None,
     "TechPowerUp robots.txt permits only personal, non-commercial use and "
     "prohibits data mining / bulk dataset creation; reuse not clear. Values "
     "predate that assessment (batch001); 16 of the 44 were cross-checked "
     "against NVIDIA official product pages.",
     "TechPowerUp GPU Database (source_id 3)."),
    ("intel ark", None,
     "No bulk reuse grant documented; used only as an archived (Wayback "
     "Machine) cross-check source.",
     "Intel ARK (archived via Wayback Machine)."),
]

SOURCE_CANONICAL = {
    "TechPowerUp GPU Database (gpu_1986-2026.csv)": (
        "https://www.techpowerup.com/gpu-specs/"
    ),
    "TechPowerUp": ("https://www.techpowerup.com/gpu-specs/"),
    "GPU Ark": ("https://gpuark.com/datasets/"),
    "GPU Ark GPU specifications & benchmarks dataset": (
        "https://gpuark.com/datasets/"
    ),
    "GPU Ark (gpuark-gpu-specs.csv)": (
        "https://gpuark.com/datasets/"
    ),
    "Wikipedia": ("https://en.wikipedia.org/"),
    "Intel ARK": ("https://ark.intel.com/"),
}


def _canonical_source_name(source_name: str) -> str:
    low = (source_name or "").lower()
    if "techpowerup" in low:
        return "TechPowerUp GPU Database"
    if "gpu ark" in low:
        return "GPU Ark"
    if "wikipedia" in low:
        return "Wikipedia"
    if "ark" in low:
        return "Intel ARK"
    if "passmark" in low:
        return "PassMark"
    if "geekbench" in low:
        return "Geekbench"
    return source_name


def _canonical_source_url(source_name: str, source_url: str | None) -> str:
    if source_url:
        return source_url
    name = _canonical_source_name(source_name or "")
    return {
        "TechPowerUp GPU Database": "https://www.techpowerup.com/gpu-specs/",
        "GPU Ark": "https://gpuark.com/datasets/",
        "Wikipedia": "https://en.wikipedia.org/",
        "Intel ARK": "https://ark.intel.com/",
        "PassMark": "https://www.cpubenchmark.net/",
        "Geekbench": "https://browser.geekbench.com/",
    }.get(name, "")


def license_for_source(source_name: str) -> tuple[str | None, str | None, str | None, str | None]:
    low = (source_name or "").lower()
    for key, license_name, license_notes, attribution in LICENSE_BY_SOURCE:
        if key in low:
            return license_name, license_notes, attribution, None
    return None, None, None, None


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def numeric_value(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def values_equal(evidenced, stored) -> bool:
    """Compare an evidenced value to a stored database value.

    Numeric string/int/float values are compared numerically; everything else
    is compared as exact text after trimming.
    """
    ev_num = numeric_value(evidenced)
    st_num = numeric_value(stored)
    if ev_num is not None and st_num is not None:
        return ev_num == st_num
    return _as_text(evidenced) == _as_text(stored)


def get_stored_value(conn, table_name: str, hardware_id: int, field) -> object:
    if table_name == "hardware":
        from_clause = f'SELECT "{field}" FROM "hardware" WHERE id = ?'
    else:
        from_clause = (
            f'SELECT "{field}" FROM "{table_name}" WHERE hardware_id = ?'
        )
    row = conn.execute(from_clause, (hardware_id,)).fetchone()
    if row is None:
        return None
    return row[0]


def load_batch001():
    """Evidence from the batch001 database patch (applied) and exclusions."""
    path = RESEARCH_DIR / "batch001" / "05_database_patch.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for update in data["updates"]:
        records.append({
            "batch": 1,
            "hardware_id": update["hardware_id"],
            "table_name": update["table"],
            "field_name": update["column"],
            "evidenced_value": _as_text(update["new_value"]),
            "source_name": update["source"],
            "source_url": update.get("source_url") or _canonical_source_url(
                update["source"], None
            ),
            "confidence": update.get("confidence"),
            "batch_status": "applied",
            "notes": update.get("notes") or "",
            "source_reference": None,
            "match_method": None,
        })
    for excluded in data.get("deliberately_excluded", []):
        records.append({
            "batch": 1,
            "hardware_id": excluded["hardware_id"],
            "table_name": "hardware",
            "field_name": excluded["field"],
            "evidenced_value": "",
            "source_name": "Unknown (deliberately excluded)",
            "source_url": "",
            "confidence": None,
            "batch_status": "excluded",
            "notes": excluded["reason"],
            "source_reference": None,
            "match_method": None,
        })
    return records


def load_batch002():
    """Evidence from the batch002 GPU Ark patch, excluded and unmatched."""
    path = RESEARCH_DIR / "batch002" / "04_database_patch.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for update in data["updates"]:
        records.append({
            "batch": 2,
            "hardware_id": update["hardware_id"],
            "table_name": update["table"],
            "field_name": update["column"],
            "evidenced_value": _as_text(update["new_value"]),
            "source_name": update["source"],
            "source_url": update.get("source_url")
                          or _canonical_source_url(update["source"], None),
            "confidence": update.get("confidence"),
            "batch_status": "applied",
            "notes": "",
            "source_reference": update.get("source_record_id"),
            "match_method": update.get("match_method"),
        })
    for record in data.get("excluded", []):
        notes = f"status={record.get('status')}. {record.get('reason', '')}"
        records.append({
            "batch": 2,
            "hardware_id": record["hardware_id"],
            "table_name": "gpu_specifications",
            "field_name": "core_clock_mhz",
            "evidenced_value": _as_text(record.get("source_value")),
            "source_name": "GPU Ark",
            "source_url": "https://gpuark.com/datasets/",
            "confidence": None,
            "batch_status": "excluded",
            "notes": notes.strip(),
            "source_reference": record.get("source_record_id"),
            "match_method": None,
        })
    for record in data.get("unmatched", []):
        records.append({
            "batch": 2,
            "hardware_id": record["hardware_id"],
            "table_name": "gpu_specifications",
            "field_name": "core_clock_mhz",
            "evidenced_value": "",
            "source_name": "GPU Ark",
            "source_url": "https://gpuark.com/datasets/",
            "confidence": None,
            "batch_status": "unmatched",
            "notes": record.get("reason", ""),
            "source_reference": None,
            "match_method": None,
        })
    return records


def load_batch003():
    """Evidence from the batch003 Wikipedia patch and exclusions."""
    path = RESEARCH_DIR / "batch003" / "05_database_patch.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for update in data["updates"]:
        records.append({
            "batch": 3,
            "hardware_id": update["hardware_id"],
            "table_name": update["table"],
            "field_name": update["column"],
            "evidenced_value": _as_text(update["new_value"]),
            "source_name": update["source"],
            "source_url": update.get("source_url")
                          or _canonical_source_url(update["source"], None),
            "confidence": update.get("confidence"),
            "batch_status": "applied",
            "notes": "",
            "source_reference": update.get("source_reference"),
            "match_method": update.get("match_method"),
        })
    for record in data.get("excluded", []):
        records.append({
            "batch": 3,
            "hardware_id": record["hardware_id"],
            "table_name": "hardware",
            "field_name": record.get("field", "architecture"),
            "evidenced_value": _as_text(record.get("source_value")),
            "source_name": record.get("source_name") or "Wikipedia",
            "source_url": record.get("source_url")
                          or "https://en.wikipedia.org/",
            "confidence": record.get("confidence"),
            "batch_status": "excluded",
            "notes": record.get("caveat", ""),
            "source_reference": record.get("source_reference"),
            "match_method": record.get("match_method"),
        })
    return records


def load_batch004():
    """Batch 004 produced no applicable evidence (schema-blocked bus width)."""
    return []


def load_batch005():
    """Evidence from the batch005 GPU clock CSV (applied in batch005)."""
    path = RESEARCH_DIR / "batch005" / "03_evidence_table.csv"
    records = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append({
                "batch": 5,
                "hardware_id": int(row["hardware_id"]),
                "table_name": "gpu_specifications",
                "field_name": row["target_field"],
                "evidenced_value": _as_text(row.get("normalized_value")
                                            or row.get("source_value")),
                "source_name": row["source_name"],
                "source_url": row.get("source_url")
                              or _canonical_source_url(row["source_name"], None),
                "confidence": row.get("confidence"),
                "batch_status": "applied",
                "notes": row.get("caveats") or "",
                "source_reference": row.get("source_record_id"),
                "match_method": row.get("match_method"),
            })
    return records


def load_batch006():
    """Evidence from the batch006 bus-width CSV (applied in batch006)."""
    path = RESEARCH_DIR / "batch006" / "03_evidence_table.csv"
    records = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append({
                "batch": 6,
                "hardware_id": int(row["hardware_id"]),
                "table_name": "gpu_specifications",
                "field_name": "memory_bus_width_bits",
                "evidenced_value": _as_text(row.get("normalized_value")
                                            or row.get("source_value")),
                "source_name": row["source_name"],
                "source_url": row.get("source_url")
                              or _canonical_source_url(row["source_name"], None),
                "confidence": row.get("confidence"),
                "batch_status": "applied",
                "notes": row.get("caveats") or "",
                "source_reference": row.get("source_record_id"),
                "match_method": row.get("match_method"),
            })
    return records


def extract_all() -> list[dict]:
    records = []
    for loader in (
        load_batch001,
        load_batch002,
        load_batch003,
        load_batch004,
        load_batch005,
        load_batch006,
    ):
        records.extend(loader())
    for record in records:
        record["canonical_source"] = _canonical_source_name(record["source_name"])
        source_verified = bool(record["source_url"])
        if not source_verified and record["batch_status"] in ("excluded", "unmatched"):
            source_verified = True
            if record["source_name"].startswith("Unknown"):
                source_verified = False
        license_name, license_notes, attribution, _ = license_for_source(
            record["source_name"]
        )
        if not source_verified:
            license_name = None
            license_notes = (
                "Source identity not documented in the research artifact."
            )
            attribution = None
        record["license_name"] = license_name
        record["license_notes"] = license_notes
        record["attribution"] = attribution
    return records


def reconcile(records: list[dict], conn) -> list[dict]:
    """Classify each evidence record against the live database."""
    reconciled = []
    for record in records:
        field = record["field_name"]
        table_name = record["table_name"]
        hw_id = record["hardware_id"]

        invalid_ref = (
            table_name not in PERMITTED_FIELDS
            or field not in PERMITTED_FIELDS[table_name]
        )
        if invalid_ref:
            record["reconciled_status"] = "invalid_reference"
            record["stored_value"] = None
        else:
            stored = get_stored_value(conn, table_name, hw_id, field)
            record["stored_value"] = stored
            if record["batch_status"] == "excluded":
                record["reconciled_status"] = "excluded"
            elif record["batch_status"] == "unmatched":
                record["reconciled_status"] = "unmatched"
            elif stored is None:
                record["reconciled_status"] = "uncertain_not_present"
            elif values_equal(record["evidenced_value"], stored):
                record["reconciled_status"] = "verified"
            else:
                record["reconciled_status"] = "uncertain_value_differs"

        # Access date is only recorded explicitly in the batch003
        # provenance.json (2026-10-09). Everything else is unknown.
        record["access_date"] = "2026-10-09" if record["batch"] == 3 else None
        reconciled.append(record)
    return reconciled


def summarize(records: list[dict]) -> dict:
    from collections import Counter

    counts = Counter(r["reconciled_status"] for r in records)
    by_batch = {}
    for batch in sorted({r["batch"] for r in records}):
        sub = [r for r in records if r["batch"] == batch]
        by_batch[batch] = {
            "records": len(sub),
            "verified": sum(r["reconciled_status"] == "verified" for r in sub),
            "uncertain_not_present": sum(
                r["reconciled_status"] == "uncertain_not_present" for r in sub
            ),
            "uncertain_value_differs": sum(
                r["reconciled_status"] == "uncertain_value_differs" for r in sub
            ),
            "excluded": sum(r["reconciled_status"] == "excluded" for r in sub),
            "unmatched": sum(r["reconciled_status"] == "unmatched" for r in sub),
            "invalid_reference": sum(
                r["reconciled_status"] == "invalid_reference" for r in sub
            ),
        }
    by_source = Counter(r["canonical_source"] for r in records)
    return {
        "total_records": len(records),
        "status_counts": dict(counts),
        "by_batch": by_batch,
        "distinct_sources": dict(by_source),
    }


def write_csv(records: list[dict], path: Path) -> None:
    columns = [
        "batch",
        "hardware_id",
        "table_name",
        "field_name",
        "evidenced_value",
        "stored_value",
        "source_name",
        "canonical_source",
        "source_url",
        "license_name",
        "license_notes",
        "attribution",
        "confidence",
        "batch_status",
        "reconciled_status",
        "source_reference",
        "match_method",
        "access_date",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def main() -> int:
    import sqlite3

    records = extract_all()
    conn = sqlite3.connect(DATA_DIR / "spectra.db")
    reconciled = reconcile(records, conn)
    conn.close()

    audit = {
        "report": "SPECTRA provenance audit (Batch 008)",
        "database": str(DATA_DIR / "spectra.db"),
        **summarize(reconciled),
    }
    audit_path = RESEARCH_DIR / "batch008" / "provenance_audit.json"
    audit_path.write_text(
        json.dumps(audit, indent=2, default=str), encoding="utf-8"
    )
    write_csv(
        reconciled,
        RESEARCH_DIR / "batch008" / "evidence_reconciliation.csv",
    )
    print(json.dumps(audit, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())