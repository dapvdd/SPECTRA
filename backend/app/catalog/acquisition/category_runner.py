"""M3.1 Task 7 — category runner: resolve every inventory candidate.

Loads one or more category manifests (each a Task 2 manifest dict), merges
their ``verified_skus`` and classifies every Task 1 inventory candidate
exactly once via the deterministic Task 2 resolver
(``resolve_candidate``): INVALID → MATCHED → REPLACED → UNRESOLVED.

Key fail-closed rule (finding from the Task 4/5 dry runs): only MATCHED
manifest entries participate in identity resolution. A UNRESOLVED manifest
entry carries no verified identity (no MPN, no per-SKU URL), so letting it
into the resolver's family filter would classify same-family candidates as
REPLACED against an entry that verifies nothing. Families whose manifest
entries are all UNRESOLVED therefore yield UNRESOLVED candidates — the
honest outcome.

Output: ``02_resolution_report.json`` with per-candidate outcome + evidence
+ confidence and per-category counters. Deterministic: identical inputs
always yield byte-identical output (no time, no randomness — the report's
generated stamp is the caller's concern).
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.catalog.acquisition.manifest import VerifiedSKU
from backend.app.catalog.acquisition.resolver import (
    _norm_family,
    resolve_candidate,
)
from backend.app.identity.canonical import normalize_manufacturer

REPORT_VERSION = 1


def load_category_manifests(paths: list[str | Path]) -> dict:
    """Load and merge category manifests into one verified-SKU pool.

    Validates each manifest on load (fail-closed) and merges the
    ``verified_skus`` lists in file order; ``source`` is the join of the
    per-manifest sources.
    """
    from backend.app.catalog.acquisition.manifest import load_manifest

    merged: list[dict] = []
    sources: list[str] = []
    for p in paths:
        man = load_manifest(p)
        merged += man.get("verified_skus", [])
        if man.get("source"):
            sources.append(man["source"])
    return {
        "manifest_version": 1,
        "source": " + ".join(sources),
        "verified_skus": merged,
    }


def resolve_inventory(
    candidates: list[dict],
    verified_skus: list,
) -> list[dict]:
    """Resolve every inventory candidate against the verified pool.

    ``candidates`` are Task 1 inventory rows (their ``claimed_spec`` may be
    pre-parsed or still the ``claimed_spec_json`` string). Returns one
    resolution row per candidate, in input order.

    Only MATCHED verified entries participate in identity resolution:
    UNRESOLVED manifest entries verify nothing and must not turn
    same-family candidates REPLACED (see module docstring).
    """
    matched_skus = [
        s for s in verified_skus
        if (s.get("classification") if isinstance(s, dict)
            else s.classification) == "MATCHED"
    ]

    rows: list[dict] = []
    for cand in candidates:
        row = dict(cand)
        if "claimed_spec" not in row:
            row["claimed_spec"] = json.loads(
                row.get("claimed_spec_json") or "{}")
        resolution = resolve_candidate(row, matched_skus)
        sku = resolution.verified_sku
        rows.append({
            "candidate_index": row.get("index", ""),
            "category": row.get("category", ""),
            "manufacturer": row.get("manufacturer", ""),
            "product_family": row.get("product_family", ""),
            "name": row.get("name", ""),
            "canonical_key": row.get("canonical_key", ""),
            "claimed_spec": row.get("claimed_spec", {}),
            "classification": resolution.classification,
            "reason": resolution.reason,
            "mpn": (sku or {}).get("mpn", "") if sku else "",
            "verified_sku": sku,
            # Confidence: MATCHED on an exact evidence anchor is the only
            # outcome with verified identity behind it (1.0); REPLACED is a
            # family-level assertion (0.5); UNRESOLVED/INVALID assert
            # nothing (0.0).
            "confidence": {"MATCHED": 1.0, "REPLACED": 0.5,
                           "UNRESOLVED": 0.0, "INVALID": 0.0}[
                               resolution.classification],
            "is_publishable": resolution.is_publishable,
        })
    return rows


def build_resolution_report(
    candidates: list[dict],
    verified_skus: list,
) -> dict:
    """Resolve all candidates and assemble the resolution report dict."""
    rows = resolve_inventory(candidates, verified_skus)
    counters: dict[str, dict[str, int]] = {}
    for row in rows:
        cat = row["category"] or "UNKNOWN"
        counters.setdefault(cat, {})
        counters[cat][row["classification"]] = (
            counters[cat].get(row["classification"], 0) + 1)

    matched_keys = sorted({
        row["mpn"] for row in rows if row["classification"] == "MATCHED"
    })
    return {
        "report_version": REPORT_VERSION,
        "source": "m31 category runner",
        "total_candidates": len(rows),
        "counters": counters,
        "matched_mpns": matched_keys,
        "candidates": rows,
    }


def save_resolution_report(report: dict, path: str | Path) -> None:
    """Write the resolution report JSON (deterministic, stable order)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_resolution_report(
    inventory_path: str | Path,
    manifest_paths: list[str | Path],
    report_path: str | Path,
) -> dict:
    """End-to-end: inventory + manifests -> 02_resolution_report.json."""
    candidates = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    if isinstance(candidates, dict):
        candidates = candidates.get("candidates", [])
    man = load_category_manifests(manifest_paths)
    report = build_resolution_report(candidates, man["verified_skus"])
    report["source"] = man["source"]
    save_resolution_report(report, report_path)
    return report


# Family-collision guard used by tests: a family whose verified entries are
# all UNRESOLVED must not resolve its candidates as REPLACED.
def unresolved_families(verified_skus: list) -> set[str]:
    """Normalized families whose manifest entries are all UNRESOLVED."""
    by_family: dict[str, list[str]] = {}
    for s in verified_skus:
        fam = _norm_family(
            s.get("product_family") if isinstance(s, dict)
            else s.product_family)
        cls = s.get("classification") if isinstance(s, dict) \
            else s.classification
        mfr = s.get("manufacturer") if isinstance(s, dict) else s.manufacturer
        by_family.setdefault(fam, []).append(cls)
    return {
        fam for fam, classes in by_family.items()
        if classes and all(c == "UNRESOLVED" for c in classes)
    }


__all__ = [
    "build_resolution_report",
    "load_category_manifests",
    "resolve_inventory",
    "save_resolution_report",
    "unresolved_families",
    "write_resolution_report",
    "normalize_manufacturer",
]
