"""M31 Task 7 (RED phase): category runner tests.

Contract from the continuation plan:
- loads one or more category manifests,
- resolves EVERY inventory candidate exactly once (INVALID → MATCHED →
  REPLACED → UNRESOLVED precedence via resolve_candidate),
- UNRESOLVED manifest entries never cause REPLACED inflation: a family
  whose manifest entries are all UNRESOLVED yields UNRESOLVED candidates,
- writes 02_resolution_report.json: per-candidate outcome + evidence +
  confidence, plus per-category counters; deterministic output.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(r"C:\Users\user\spectra-m31")
sys.path.insert(0, str(ROOT))

from backend.app.catalog.acquisition.category_runner import (  # noqa: E402
    build_resolution_report,
    load_category_manifests,
    resolve_inventory,
)


def _inv_row(idx, category, family, mfr, spec):
    from backend.app.identity.canonical import canonical_key, variant_key

    name = f"{mfr} {family} test"
    return {
        "index": idx,
        "category": category,
        "manufacturer": mfr,
        "product_family": family,
        "name": name,
        "canonical_key": canonical_key(
            mfr, category, f"{mfr} {family} test",
            variant_key(category, spec)),
        "identity_status": "unconfirmed",
        "claimed_spec_json": json.dumps(spec),
        "provenance_urls_json": "{}",
    }


def _matched(mfr, family, mpn, spec, idx="900"):
    from backend.app.catalog.acquisition.manifest import (
        FieldEvidence, VerifiedSKU)

    fields = [
        FieldEvidence(spec_field=f, normalized_value=v, source_value=str(v),
                      source_evidence_location="T", curator_decision="APPROVED",
                      source_url="https://x.example/p/" + mpn,
                      match_method="spec-table-row", access_date="2026-11-23")
        for f, v in spec.items()
    ]
    return VerifiedSKU(
        category="PSU", name=f"{mfr} {family}", manufacturer=mfr,
        product_family=family, mpn=mpn,
        per_sku_url="https://x.example/p/" + mpn,
        source_doc_revision="test page", spec=spec, fields=fields,
        classification="MATCHED", candidate_index=idx,
    )


def _unresolved(mfr, family, idx="901"):
    from backend.app.catalog.acquisition.manifest import VerifiedSKU

    return VerifiedSKU(
        category="PSU", name=f"{mfr} {family}", manufacturer=mfr,
        product_family=family, mpn="", per_sku_url="",
        source_doc_revision="", classification="UNRESOLVED",
        notes="no evidence", candidate_index=idx,
    )


def test_unresolved_entry_does_not_inflate_replaced():
    """Families whose manifest entries are UNRESOLVED stay UNRESOLVED."""
    cand = _inv_row("001", "PSU", "Focus GX", "Seasonic",
                    {"wattage": 650, "efficiency_rating": "80 Plus Gold",
                     "modular": True})
    report = build_resolution_report([cand], [_unresolved("Seasonic",
                                                          "Focus GX")])
    row = report["candidates"][0]
    assert row["classification"] == "UNRESOLVED"


def test_matched_and_replaced_split():
    cand_m = _inv_row("002", "PSU", "RMx (2021)", "Corsair",
                      {"wattage": 550, "efficiency_rating": "80 Plus Gold",
                       "modular": True})
    cand_r = _inv_row("003", "PSU", "RMx (2021)", "Corsair",
                      {"wattage": 1000, "efficiency_rating": "80 Plus Gold",
                       "modular": True})
    cand_u = _inv_row("004", "PSU", "NeverSeen", "Corsair",
                      {"wattage": 400, "efficiency_rating": "80 Plus Gold",
                       "modular": False})
    skus = [_matched("Corsair", "RMx (2021)", "CP-9020197-NA",
                     {"wattage": 550, "efficiency_rating": "80 Plus Gold",
                      "modular": True})]
    report = build_resolution_report([cand_m, cand_r, cand_u], skus)
    got = {r["candidate_index"]: r["classification"]
           for r in report["candidates"]}
    assert got["002"] == "MATCHED"
    assert got["003"] == "REPLACED"
    assert got["004"] == "UNRESOLVED"


def test_resolution_report_shape_and_counters():
    cand = _inv_row("005", "PSU", "RMx (2021)", "Corsair",
                    {"wattage": 550, "efficiency_rating": "80 Plus Gold",
                     "modular": True})
    skus = [_matched("Corsair", "RMx (2021)", "CP-9020197-NA",
                     {"wattage": 550, "efficiency_rating": "80 Plus Gold",
                      "modular": True})]
    report = build_resolution_report([cand], skus)
    assert report["total_candidates"] == 1
    assert report["counters"]["PSU"] == {"MATCHED": 1}
    row = report["candidates"][0]
    assert row["mpn"] == "CP-9020197-NA"
    assert row["verified_sku"] and row["verified_sku"]["mpn"] == "CP-9020197-NA"
    assert row["confidence"] == 1.0


def test_determinism():
    cand = _inv_row("006", "PSU", "RMx (2021)", "Corsair",
                    {"wattage": 550, "efficiency_rating": "80 Plus Gold",
                     "modular": True})
    skus = [_matched("Corsair", "RMx (2021)", "CP-9020197-NA",
                     {"wattage": 550, "efficiency_rating": "80 Plus Gold",
                      "modular": True})]
    a = build_resolution_report([cand], skus)
    b = build_resolution_report([cand], skus)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_load_category_manifests(tmp_path):
    from backend.app.catalog.acquisition.manifest import new_manifest

    p = tmp_path / "m.json"
    p.write_text(json.dumps(new_manifest(
        [_unresolved("Seasonic", "Focus GX")],
        source="t")), encoding="utf-8")
    man = load_category_manifests([p])
    assert man["source"] == "t"
    assert len(man["verified_skus"]) == 1
