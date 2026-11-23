"""M3.1 Task 1 — extract a deterministic inventory of the 443 quarantined
pilot candidates (family×tier records without per-SKU evidence).

Reads the in-repo pilot generator (`backend.app.catalog.pilot_seed`),
filters `record_status == "QUARANTINED"`, and writes:

- ``data/research/m31/01_candidate_inventory.csv``
- ``data/research/m31/01_candidate_inventory.json``

Deterministic: same seed data -> same rows, same order, same bytes.
Run from anywhere: the script adds the repo root to ``sys.path`` itself.

    python data/research/m31/build_inventory.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.catalog.pilot_seed import build_pilot_records  # noqa: E402

OUT_DIR = _REPO_ROOT / "data" / "research" / "m31"
CSV_PATH = OUT_DIR / "01_candidate_inventory.csv"
JSON_PATH = OUT_DIR / "01_candidate_inventory.json"

COLUMNS = [
    "index",
    "category",
    "manufacturer",
    "product_family",
    "name",
    "canonical_key",
    "identity_status",
    "claimed_spec_json",
    "provenance_urls_json",
]

EXPECTED_COUNTS = {
    "RAM": 128,
    "STORAGE": 109,
    "MOTHERBOARD": 100,
    "PSU": 106,
}
EXPECTED_TOTAL = 443


def _compact_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _provenance_urls(prov: dict) -> dict[str, str]:
    """Map each provenance field name to its source_url (dict order)."""
    return {
        field: entry.get("source_url", "")
        for field, entry in prov.items()
        if isinstance(entry, dict)
    }


def build_rows() -> list[dict]:
    """Deterministic quarantined-candidate rows in extraction order."""
    records = build_pilot_records()
    rows: list[dict] = []
    for category in ("RAM", "STORAGE", "MOTHERBOARD", "PSU"):
        for record in records[category]:
            if record.get("record_status") != "QUARANTINED":
                continue
            rows.append({
                "category": record["category"],
                "manufacturer": record["manufacturer"],
                "product_family": record["product_family"],
                "name": record["name"],
                "canonical_key": record["canonical_key"],
                "identity_status": record["identity_status"],
                "claimed_spec_json": _compact_json(record["spec"]),
                "provenance_urls_json": _compact_json(
                    _provenance_urls(record["provenance"])
                ),
            })
    return rows


def main() -> int:
    rows = build_rows()

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1

    indexed: list[dict] = []
    for i, row in enumerate(rows, start=1):
        indexed.append({"index": f"{i:03d}", **row})

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in indexed:
            writer.writerow(row)

    with open(JSON_PATH, "w", newline="", encoding="utf-8") as fh:
        json.dump(indexed, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"total quarantined candidates: {len(rows)}")
    for category in ("RAM", "STORAGE", "MOTHERBOARD", "PSU"):
        expected = EXPECTED_COUNTS.get(category)
        actual = counts.get(category, 0)
        marker = "OK" if actual == expected else "MISMATCH"
        print(f"  {category}: {actual} (expected {expected}) {marker}")

    ok = (
        len(rows) == EXPECTED_TOTAL
        and all(counts.get(c, 0) == n for c, n in EXPECTED_COUNTS.items())
    )
    if not ok:
        print("COUNT MISMATCH — do not adjust the data; report the discrepancy.")
        return 1
    print(f"wrote {CSV_PATH}")
    print(f"wrote {JSON_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
