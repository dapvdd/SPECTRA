"""M31 Task 7 run: produce 02_resolution_report.json from all manifests."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\user\spectra-m31")
sys.path.insert(0, str(ROOT))

from backend.app.catalog.acquisition.category_runner import (  # noqa: E402
    write_resolution_report,
)

M31 = ROOT / "data/research/m31"
report = write_resolution_report(
    M31 / "01_candidate_inventory.json",
    [M31 / "manifest_ram.json", M31 / "manifest_storage.json",
     M31 / "manifest_psu.json"],
    M31 / "02_resolution_report.json",
)
counts = Counter()
for row in report["candidates"]:
    counts[row["classification"]] += 1
print("total:", report["total_candidates"])
print("counters:", dict(counts))
print("matched MPNs:", len(report["matched_mpns"]))

# determinism check: rerun and compare bytes
b1 = (M31 / "02_resolution_report.json").read_bytes()
write_resolution_report(
    M31 / "01_candidate_inventory.json",
    [M31 / "manifest_ram.json", M31 / "manifest_storage.json",
     M31 / "manifest_psu.json"],
    M31 / "02_resolution_report.json",
)
b2 = (M31 / "02_resolution_report.json").read_bytes()
print("deterministic:", b1 == b2)

# per-category counter summary from the report itself
print("report counters:", json.dumps(report["counters"], sort_keys=True))
