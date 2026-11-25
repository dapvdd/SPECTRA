"""M32 Task 1 — resolve all 100 motherboard candidates via the runner.

Writes 02_resolution_report_motherboard.json (M32) from the M3.1 inventory
+ the M32 motherboard manifest. Prints counters and any candidate whose
variant token diverges from the verified SKU (sanity check).
"""
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\user\spectra-m32")
sys.path.insert(0, str(ROOT))

from backend.app.catalog.acquisition.category_runner import (  # noqa: E402
    write_resolution_report,
)
from backend.app.identity.canonical import (  # noqa: E402
    canonical_key,
    variant_key,
)

INV = ROOT / "data/research/m31/01_candidate_inventory.json"
MAN = ROOT / "data/research/m32/manifest_motherboard.json"
OUT = ROOT / "data/research/m32/02_resolution_report_motherboard.json"

report = write_resolution_report(INV, [MAN], OUT)

print("counters:", json.dumps(report["counters"]))
print("total:", report["total_candidates"])

# Variant-token sanity: recompute canonical key from page-verified spec and
# compare with the candidate's inventory key; list divergences.
cands = {c["candidate_index"]: c for c in report["candidates"]}
for sku in json.loads(MAN.read_text(encoding="utf-8"))["verified_skus"]:
    if sku["classification"] != "MATCHED":
        continue
    vk = variant_key("MOTHERBOARD", dict(sku["spec"]))
    ck = canonical_key(sku["manufacturer"], "MOTHERBOARD",
                       sku["product_family"], vk)
    cand = cands.get(sku["candidate_index"], {})
    same = cand.get("canonical_key", "").endswith(vk)
    print(f'{sku["candidate_index"]} variant={vk!r} '
          f'inv_endswith={same} ck={ck}')
