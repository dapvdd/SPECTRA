"""Batch 009 - reconstruct base-import provenance from original source artifacts.

This module reconciles every populated database cell against the original
base-import artifacts found on this machine, using the same normalizers the
import code used, and writes a machine-readable reconciliation report.

It never writes to the hardware specification tables; persistence (loading
reconciled records into ``field_provenance``) is handled by
``load_provenance.py``.

Detected base-import datasets
-----------------------------
- ``intel``        ``intel-cpus.csv``     snapshot of Intel ARK (via
                   felixsteinke/cpu-spec-dataset)
- ``amd``          ``amd-cpus.csv``       snapshot of AMD processor
                   specification pages (same distribution)
- ``passmark``     ``benchmark-cpus.csv`` snapshot of cpubenchmark.net
- ``techpowerup``  ``data/raw/gpu_1986-2026.csv`` TechPowerUp GPU database
- ``geekbench``    ``~/Downloads/benchmark/processor-benchmarks.csv``
                   Geekbench Browser 7 CPU catalog

Decision rule (also enforced by the tested backend helper): a value is
``verified`` only when it matches exactly one dataset; a value present in two
or more datasets is ``uncertain``; a value matching none is ``unmatched``.

Run from the repository root:

    python data/research/batch009/evidence.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import sqlite3  # noqa: E402

from backend.app.importers.benchmark_matcher import normalize_match_name  # noqa: E402
from backend.app.importers.benchmark_normalizer import (  # noqa: E402
    normalize_benchmark_row,
)
from backend.app.importers.cpu_normalizer import (  # noqa: E402
    normalize_amd_row,
    normalize_intel_row,
)
from backend.app.importers.gpu_normalizer import normalize_gpu_row  # noqa: E402
from backend.app.services.base_import_provenance import (  # noqa: E402
    VALID_FIELDS,
    classify_cell,
)

DATA_DIR = REPO_ROOT / "data"
RESEARCH_DIR = DATA_DIR / "research"
BATCH_DIR = RESEARCH_DIR / "batch009"
DEFAULT_DB = DATA_DIR / "spectra.db"

HOME = Path.home()
INTEL_CSV = Path(__import__("os").environ.get(
    "SPECTRA_INTEL_CSV", HOME / "Downloads" / "intel-cpus.csv"))
AMD_CSV = Path(__import__("os").environ.get(
    "SPECTRA_AMD_CSV", HOME / "Downloads" / "amd-cpus.csv"))
PASSMARK_CSV = Path(__import__("os").environ.get(
    "SPECTRA_PASSMARK_CSV", HOME / "Downloads" / "benchmark-cpus.csv"))
GPU_CSV = DATA_DIR / "raw" / "gpu_1986-2026.csv"
GEEKBENCH_CSV = Path(__import__("os").environ.get(
    "SPECTRA_GEEKBENCH_CSV", HOME / "Downloads" / "benchmark" / "processor-benchmarks.csv"))

DATASET_INFO = {
    "intel": {
        "source_name": "Intel ARK (intel-cpus.csv snapshot)",
        "source_url": "https://ark.intel.com/",
        "artifact": "intel-cpus.csv",
    },
    "amd": {
        "source_name": "AMD product specifications (amd-cpus.csv snapshot)",
        "source_url": "https://www.amd.com/en/products/specifications/processors",
        "artifact": "amd-cpus.csv",
    },
    "passmark": {
        "source_name": "PassMark CPU benchmark catalog (benchmark-cpus.csv)",
        "source_url": "https://www.cpubenchmark.net/",
        "artifact": "benchmark-cpus.csv",
    },
    "techpowerup": {
        "source_name": "TechPowerUp GPU Database (gpu_1986-2026.csv)",
        "source_url": "https://www.techpowerup.com/gpu-specs/",
        "artifact": "gpu_1986-2026.csv",
    },
    "geekbench": {
        "source_name": "Geekbench Browser - Geekbench 7 CPU",
        "source_url": "https://browser.geekbench.com/",
        "artifact": "processor-benchmarks.csv",
    },
}

# ---- drift-tolerant column resolution -------------------------------------

def _norm_col(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def resolve_columns(fieldnames: list[str], canonical_keys: list[str]) -> dict:
    """Map canonical import column names onto the actual CSV header names."""
    actual = {}
    for header in fieldnames or ():
        actual.setdefault(_norm_col(header), header)
    mapping = {}
    for key in canonical_keys:
        mapping[key] = actual.get(_norm_col(key))
    return mapping


def remap_row(row: dict, mapping: dict) -> dict:
    return {key: row.get(actual) if actual else None for key, actual in mapping.items()}


def read_csv_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader), reader.fieldnames


def load_normalized(
    path: Path | None,
    canonical_keys: list[str] | None,
    normalizer,
    header_remap: bool = True,
) -> list[tuple[dict, dict]]:
    """Return [(normalized_row, raw_row)] or [] when the artifact is absent."""
    if path is None or not Path(path).is_file():
        return []
    rows, fieldnames = read_csv_rows(path)
    mapping = resolve_columns(fieldnames, canonical_keys or [])
    out = []
    for raw in rows:
        if header_remap and mapping:
            raw = remap_row(raw, mapping)
        out.append((normalizer(raw), raw))
    return out


# ---- artifact hashes ------------------------------------------------------

def sha256(path) -> str | None:
    if not Path(path).is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---- source entity lookups ------------------------------------------------

CPU_INTEL_COLUMNS = [
    "CpuId", "CpuName", "CoreCount", "ThreadCount", "ClockSpeed",
    "ClockSpeedMax", "MaxTDP", "Lithography", "SocketsSupported",
]
CPU_AMD_COLUMNS = [
    "Model", "# of CPU Cores", "# of Threads", "Base Clock",
    "Max. Boost Clock Ã‚Â¹ Ã‚Â²", "Default TDP", "CPU Socket",
    "Product ID Tray", "Product ID Boxed", "Product ID MPK",
]


def build_cpu_lookup():
    """Return {(manufacturer, name): {dataset: [normalized...]}}."""
    lookup = defaultdict(lambda: defaultdict(list))

    def add(dataset, norm):
        name = norm.get("name")
        mfr = norm.get("manufacturer")
        if name and mfr:
            lookup[(mfr, name)][dataset].append(norm)

    for norm, _raw in load_normalized(INTEL_CSV, CPU_INTEL_COLUMNS, normalize_intel_row):
        add("intel", norm)
    for norm, _raw in load_normalized(AMD_CSV, CPU_AMD_COLUMNS, normalize_amd_row):
        add("amd", norm)
    for norm, _raw in load_normalized(PASSMARK_CSV, None, normalize_benchmark_row, header_remap=False):
        add("passmark", norm)
    return lookup


def build_gpu_lookup():
    """Return {(manufacturer, name): {dataset: [normalized...]}}."""
    lookup = defaultdict(lambda: defaultdict(list))
    for norm, _raw in load_normalized(GPU_CSV, None, normalize_gpu_row, header_remap=False):
        name = norm.get("name")
        mfr = norm.get("manufacturer")
        if name and mfr:
            lookup[(mfr, name)]["techpowerup"].append(norm)
    return lookup


def build_geekbench_index():
    rows, _ = read_csv_rows(GEEKBENCH_CSV) if GEEKBENCH_CSV.is_file() else ([], None)
    index = defaultdict(list)
    for raw in rows:
        name = (raw.get("devices/name") or "").strip()
        norm = normalize_match_name(name)
        if norm:
            index[norm].append(raw)
    return index, rows


# ---- per-cell classification ----------------------------------------------

CPU_SPEC_FIELDS = [
    "cores", "threads", "base_clock_ghz", "boost_clock_ghz", "tdp_w",
    "process_node_nm", "socket",
]
GPU_SPEC_FIELDS = [
    "memory_gb", "memory_type", "core_clock_mhz", "boost_clock_mhz",
    "vram_bandwidth_gbps", "tdp_w", "interface", "length_mm",
]
HW_FIELDS = ["release_date", "architecture"]
IDENTITY_FIELDS = ["name", "manufacturer", "type"]

STATUS_CONFIDENCE = {
    "verified": {"1": "high", "many": "medium"},
    "uncertain": "medium",
    "unmatched": None,
    "empty": None,
}


def confidence_for(decision) -> str | None:
    if decision.status == "verified":
        return STATUS_CONFIDENCE["verified"]["1" if decision.matching_row_count <= 1 else "many"]
    return STATUS_CONFIDENCE.get(decision.status)


def reason_for(decision) -> str:
    if decision.status == "verified":
        return (
            f"stored value equals normalized source value uniquely "
            f"in dataset '{decision.dataset}' ({decision.matching_row_count} row(s))."
        )
    if decision.status == "uncertain":
        return (
            "stored value is present in multiple datasets "
            f"({', '.join(decision.matching_datasets)}); source identity ambiguous "
            "at value level, not persisted as verified."
        )
    if decision.status == "unmatched":
        return "stored value matches no documented base-import dataset."
    return "no source values available for this entity/field."


def persistable(table: str, field: str) -> bool:
    return field in VALID_FIELDS.get(table, ())


def main() -> int:
    connection = sqlite3.connect(DEFAULT_DB)
    connection.row_factory = sqlite3.Row
    cur = connection.cursor()

    artifacts = {}
    for ds, info in DATASET_INFO.items():
        path = {
            "intel": INTEL_CSV, "amd": AMD_CSV, "passmark": PASSMARK_CSV,
            "techpowerup": GPU_CSV, "geekbench": GEEKBENCH_CSV,
        }[ds]
        artifacts[ds] = {
            "artifact": info["artifact"],
            "path": str(path),
            "sha256": sha256(path),
            "present": bool(path and Path(path).is_file()),
        }

    cpu_lookup = build_cpu_lookup()
    gpu_lookup = build_gpu_lookup()
    geek_index, geek_rows = build_geekbench_index()

    # existing verified provenance coverage
    covered = set()
    for row in cur.execute(
        "SELECT table_name, hardware_id, field_name FROM field_provenance "
        "WHERE evidence_status = 'verified'"
    ):
        covered.add((row[0], row[1], row[2]))

    rows_out = []
    stats = Counter()

    def emit(dataset, table, field, hid, hname, dbval, decision,
             covered_flag=False, manufacturer=""):
        rows_out.append({
            "dataset": dataset or "",
            "entity_id": hid,
            "entity_name": hname,
            "table": table,
            "field": field,
            "db_value": dbval,
            "status": decision.status,
            "confidence": confidence_for(decision),
            "supporting_artifact": (
                DATASET_INFO[decision.dataset]["artifact"]
                if decision.dataset else ""
            ),
            "source_reference": (
                f"{DATASET_INFO[decision.dataset]['artifact']}"
                f"#{manufacturer}={hname}"
                if decision.dataset else ""
            ),
            "persistable": persistable(table, field),
            "already_covered_verified": covered_flag,
            "reason": reason_for(decision),
        })
        key = (dataset or "-", table, field, decision.status)
        stats[key] += 1
        stats[f"total_{decision.status}"] += 1

    # ---- CPU specs ----
    for row in cur.execute(
        "SELECT h.id, h.name, h.manufacturer, c.cores, c.threads, "
        "c.base_clock_ghz, c.boost_clock_ghz, c.tdp_w, c.process_node_nm, c.socket "
        "FROM hardware h JOIN cpu_specifications c ON c.hardware_id = h.id "
        "WHERE h.type = 'CPU'"):
        hid, hname = row["id"], row["name"]
        key = (row["manufacturer"], hname)
        datasets = cpu_lookup.get(key) or {}
        for field in CPU_SPEC_FIELDS:
            dbval = row[field]
            if dbval is None:
                continue
            value_map = {
                ds: [n.get(field) for n in norms if n.get(field) is not None]
                for ds, norms in datasets.items()
            }
            decision = classify_cell(dbval, value_map)
            already = ("cpu_specifications", hid, field) in covered
            emit(
                (decision.dataset if decision.status == "verified" else ""),
                "cpu_specifications", field, hid, hname, dbval, decision,
                covered_flag=already, manufacturer=row["manufacturer"],
            )

    # ---- GPU specs ----
    for row in cur.execute(
        "SELECT h.id, h.name, h.manufacturer, g.memory_gb, g.memory_type, "
        "g.core_clock_mhz, g.boost_clock_mhz, g.vram_bandwidth_gbps, g.tdp_w, "
        "g.interface, g.length_mm "
        "FROM hardware h JOIN gpu_specifications g ON g.hardware_id = h.id "
        "WHERE h.type = 'GPU'"):
        hid, hname = row["id"], row["name"]
        key = (row["manufacturer"], hname)
        datasets = gpu_lookup.get(key) or {}
        for field in GPU_SPEC_FIELDS:
            dbval = row[field]
            if dbval is None:
                continue
            value_map = {
                ds: [n.get(field) for n in norms if n.get(field) is not None]
                for ds, norms in datasets.items()
            }
            decision = classify_cell(dbval, value_map)
            already = ("gpu_specifications", hid, field) in covered
            emit(
                (decision.dataset if decision.status == "verified" else ""),
                "gpu_specifications", field, hid, hname, dbval, decision,
                covered_flag=already, manufacturer=row["manufacturer"],
            )

    # ---- hardware fields (release_date, architecture) ----
    for row in cur.execute(
        "SELECT id, name, manufacturer, type, release_date, architecture "
        "FROM hardware"):
        hid, hname = row["id"], row["name"]
        if row["type"] == "CPU":
            datasets = cpu_lookup.get((row["manufacturer"], hname)) or {}
        else:
            datasets = gpu_lookup.get((row["manufacturer"], hname)) or {}
        for field in HW_FIELDS:
            dbval = row[field]
            if dbval is None:
                continue
            value_map = {
                ds: [n.get(field) for n in norms if n.get(field) is not None]
                for ds, norms in datasets.items()
            }
            decision = classify_cell(dbval, value_map)
            already = ("hardware", hid, field) in covered
            emit(
                (decision.dataset if decision.status == "verified" else ""),
                "hardware", field, hid, hname, dbval, decision,
                covered_flag=already, manufacturer=row["manufacturer"],
            )

    # ---- identity fields (name, manufacturer, type) ----
    for row in cur.execute(
        "SELECT id, name, manufacturer, type FROM hardware"):
        hid, hname = row["id"], row["name"]
        key = (row["manufacturer"], hname)
        datasets = (
            cpu_lookup.get(key) if row["type"] == "CPU" else gpu_lookup.get(key)
        ) or {}
        for field in IDENTITY_FIELDS:
            dbval = row[field]
            value_map = {
                ds: [n.get(field) for n in norms if n.get(field) is not None]
                for ds, norms in datasets.items()
            }
            decision = classify_cell(dbval, value_map)
            emit(
                (decision.dataset if decision.status == "verified" else ""),
                "hardware", field, hid, hname, dbval, decision,
                manufacturer=row["manufacturer"],
            )

    # ---- Geekbench benchmark results (artifact-only: schema cannot          ----
    # ---- represent benchmark_results in field_provenance)                  ----
    hw_names = {
        r["id"]: r["name"]
        for r in cur.execute("SELECT id, name FROM hardware WHERE type = 'CPU'")
    }
    for row in cur.execute(
        "SELECT id, hardware_id, score, test_type FROM benchmark_results "
        "WHERE source_id = 2"):
        hid, score, test_type = row["hardware_id"], row["score"], row["test_type"]
        hname = hw_names.get(hid, "")
        norm = normalize_match_name(hname)
        cands = geek_index.get(norm or "", [])
        column = "devices/score" if test_type == "single-core" else "devices/multicore_score"
        matching = [
            raw for raw in cands
            if float_or_none(raw.get(column)) == score
        ]
        existing_by_source = ("benchmark_results", hid, "score") in covered
        if len(matching) == 1:
            status, confidence = "verified", "high"
            reason = "stored Geekbench score equals a unique processor-benchmarks.csv row."
        elif len(matching) > 1:
            status, confidence = "uncertain", "medium"
            reason = "stored Geekbench score matches multiple processor-benchmarks.csv rows."
        else:
            status, confidence = "unmatched", None
            reason = "stored Geekbench score matches no processor-benchmarks.csv row."
        rows_out.append({
            "dataset": "geekbench",
            "entity_id": hid,
            "entity_name": hname,
            "table": "benchmark_results",
            "field": "score",
            "db_value": score,
            "status": status,
            "confidence": confidence,
            "supporting_artifact": "processor-benchmarks.csv",
            "source_reference": (matching[0].get("devices/id", "") if matching else ""),
            "persistable": False,
            "already_covered_verified": existing_by_source,
            "reason": reason,
        })
        stats[f"total_{status}"] += 1
        stats[("geekbench", "benchmark_results", "score", status)] += 1

    # ---- write outputs ----
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "dataset", "entity_id", "entity_name", "table", "field", "db_value",
        "status", "confidence", "supporting_artifact", "source_reference",
        "persistable", "already_covered_verified", "reason",
    ]
    with open(BATCH_DIR / "evidence_reconciliation.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_out:
            writer.writerow(row)

    summary = {
        "generated_at": None,
        "database": str(DEFAULT_DB),
        "datasets": artifacts,
        "cell_totals": {
            "verified": stats["total_verified"],
            "uncertain": stats["total_uncertain"],
            "unmatched": stats["total_unmatched"],
        },
        "by_group": {
            f"{ds}|{table}|{field}|{status}": count
            for (ds, table, field, status), count in sorted(
                (key, value) for key, value in stats.items() if isinstance(key, tuple)
            )
        },
    }
    with open(BATCH_DIR / "provenance_reconciliation.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print("artifact inventory:")
    for ds, info in artifacts.items():
        print(f"  {ds}: present={info['present']} sha256={info['sha256']}")
    print("reconciliation rows written:", len(rows_out))
    print("by status:", {
        k: v for k, v in stats.items() if str(k).startswith("total_")
    })
    return 0


def float_or_none(value):
    try:
        return float((value or "").strip())
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
