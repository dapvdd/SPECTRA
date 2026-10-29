"""
SPECTRA Batch 017 - GPU Ark CC BY 4.0 enrichment

Source: https://gpuark.com/datasets/
License: CC BY 4.0
Dataset: gpuark-gpu-specs.csv (3.4 MB, ~13,566 GPUs)
Retrieved: 2026-10-28
License URL: https://creativecommons.org/licenses/by/4.0/

Attribution requirement (CC BY 4.0):
  "GPU Ark (2026). GPU specifications & benchmarks dataset.
   https://gpuark.com/datasets/"
"""

import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BATCH_DIR = REPO / "data" / "research" / "batch017"
STAGING_DB = REPO / "data" / "spectra_staging.db"
ARK_CSV = BATCH_DIR / "gpuark-gpu-specs.csv"
ARK_URL = "https://gpuark.com/datasets/gpuark-gpu-specs.csv"
METADATA_JSON = BATCH_DIR / "source_metadata.json"

SOURCE_NAME = "GPU Ark GPU specifications & benchmarks dataset"
SOURCE_URL = ARK_URL
SOURCE_LICENSE = "CC BY 4.0"
SOURCE_ATTRIBUTION = (
    "GPU Ark (2026). GPU specifications & benchmarks dataset. "
    "https://gpuark.com/datasets/"
)

# Fields GPU Ark provides, mapped to SPECTRA gpu_specifications columns.
# GPU Ark column → SPECTRA column → fill if NULL only
FIELD_MAP = [
    ("interface",      "interface",           "pcie_from_bus_width"),
    ("boost_clock",     "boost_clock_mhz",      None),
    ("tdp",             "tdp_w",                None),
    ("length_mm",       "length_mm",            None),
    ("ram",             "memory_gb",            "ram_gb"),
    ("ram_type",        "memory_type",          None),
    ("bus_width",       "memory_bus_width_bits","None"),
    ("ram_bandwidth",   "vram_bandwidth_gbps",  "bandwidth_gbps"),
    ("base_clock",      "core_clock_mhz",       None),
]
# Fields NOT in gpu_specifications schema: slug, arch_name, card_release_date,
# proc_foundry, proc_process_size, proc_transistors, cores, tensor_cores,
# fp16/fp32/fp64/bf16/tf32/int8_performance, multi_gpu, api_cuda, is_retail_board,
# gpi_value, manufacturer (hardware-level, not spec-level).


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_ark():
    """Download GPU Ark CSV with checksum verification."""
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    if ARK_CSV.exists():
        existing = sha256(ARK_CSV)
        print(f"[fetch] already present: {ARK_CSV} (sha256={existing[:16]}...)")
        return existing

    print(f"[fetch] downloading {ARK_URL} ...")
    req = urllib.request.Request(
        ARK_URL,
        headers={"User-Agent": "SPECTRA-research/1.0 (CC BY 4.0 attribution required)"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} from {ARK_URL}")
        content_type = resp.headers.get("Content-Type", "")
        print(f"[fetch] status={resp.status} content-type={content_type}")
        data = resp.read()

    with open(ARK_CSV, "wb") as f:
        f.write(data)

    chk = sha256(ARK_CSV)
    size = ARK_CSV.stat().st_size
    print(f"[fetch] saved: {size:,} bytes, sha256={chk}")
    metadata = {
        "source": SOURCE_NAME,
        "url": ARK_URL,
        "license": SOURCE_LICENSE,
        "attribution": SOURCE_ATTRIBUTION,
        "retrieved_on": datetime.date.today().isoformat(),
        "sha256": chk,
        "size_bytes": size,
        "row_count_hint": None,  # filled after row_count
    }
    METADATA_JSON.write_text(json.dumps(metadata, indent=2))
    print(f"[fetch] metadata written: {METADATA_JSON}")
    return chk


def count_ark_rows():
    """Count rows in the downloaded CSV for provenance."""
    with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
        return sum(1 for _ in f) - 1  # subtract header


def load_ark_rows():
    """Load GPU Ark rows, normalize memory unit (MB vs GB) per dataset card."""
    import csv
    rows = []
    with open(ARK_CSV, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_ram = (row.get("ram") or "").strip()
            ram_gb = None
            if raw_ram:
                try:
                    val = float(raw_ram)
                    # Dataset card rule: value ≥ 256 on old cards = MB; else GB.
                    if val >= 256:
                        ram_gb = val / 1024.0
                    else:
                        ram_gb = val
                except ValueError:
                    pass

            rows.append({
                "id":         row.get("id", "").strip(),
                "name":       row.get("name", "").strip(),
                "vendor":     (row.get("vendor") or "").strip(),
                "manufacturer": (row.get("manufacturer") or "").strip(),
                "arch_name":  row.get("arch_name", "").strip(),
                "base_clock": _float(row.get("base_clock")),
                "boost_clock": _float(row.get("boost_clock")),
                "ram":        ram_gb,
                "ram_raw":    raw_ram,
                "ram_type":   (row.get("ram_type") or "").strip(),
                "bus_width":  _float(row.get("bus_width")),
                "ram_bandwidth": _float(row.get("ram_bandwidth")),
                "tdp":        _float(row.get("tdp")),
                "length_mm":  _float(row.get("length_mm")),
                # PCIe generation inference from bus_width
                "pcie_gen":   _pcie_gen(_float(row.get("bus_width"))),
            })
    return rows


def _float(s):
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        v = float(s)
        return None if v == 0 else v
    except ValueError:
        return None


def _pcie_gen(bus_bits):
    """Derive PCIe generation from bus width. Rough heuristic; quarantine if unsure."""
    if bus_bits is None:
        return None
    # PCIe x16 lanes: x1≈x2≈x4≈x8≈x16 share common widths
    known = {
        16:    "PCIe 5.0 x16",   # 32 GB/s full-speed modern
        64:    "PCIe 5.0 x16",   # HBM-like / special
        128:   "PCIe 4.0 x16",
        192:   "PCIe 4.0 x16",
        256:   "PCIe 3.0 x16",
        384:   "PCIe 3.0 x16",
        512:   "PCIe 2.0 x16",
    }
    return known.get(int(bus_bits))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "download"
    if cmd == "download":
        chk = fetch_ark()
        n = count_ark_rows()
        print(f"GPU Ark rows (incl header): {n+1}; data rows: {n}")
        # update metadata
        m = json.loads(METADATA_JSON.read_text())
        m["row_count_hint"] = n
        METADATA_JSON.write_text(json.dumps(m, indent=2))
    elif cmd == "inspect":
        rows = load_ark_rows()
        print(f"Loaded {len(rows)} GPU Ark rows")
        vendors = {}
        for r in rows:
            v = r["vendor"] or "unknown"
            vendors[v] = vendors.get(v, 0) + 1
        print(f"Vendor distribution: {vendors}")
        # Show first few with null/ambiguous fields
        null_boost = [r for r in rows if r["boost_clock"] is None]
        null_ram = [r for r in rows if r["ram"] is None]
        print(f"  null boost_clock: {len(null_boost)}")
        print(f"  null ram: {len(null_ram)}")
        print(f"  sample row: {rows[0]}")
        # length_mm coverage
        null_len = [r for r in rows if r["length_mm"] is None]
        print(f"  null length_mm: {len(null_len)}")
        null_pcie = [r for r in rows if r["pcie_gen"] is None]
        print(f"  null/derivable PCIe: {len(null_pcie)}")
