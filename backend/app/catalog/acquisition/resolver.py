"""M3.1 Task 2 — deterministic identity resolution (pure functions, no I/O).

Classifies a Task 1 inventory candidate against a VerifiedSKU into exactly
one of the plan's four outcomes:

- MATCHED     — the candidate IS the verified SKU: the candidate's recorded
                canonical_key equals the canonical_key recomputed from the
                verified SKU's own identity fields.
- REPLACED    — same manufacturer + family + category, different variant
                (the verified SKU supersedes the candidate: e.g. the
                candidate claimed a family-tier combination the vendor does
                not sell, and the verified page documents a different tier).
- UNRESOLVED  — no verified SKU exists for that family + category (the
                honest outcome; the candidate stays in the backlog).
- INVALID     — the candidate's claimed spec violates physical/category
                sanity (reuses the ``m3_validation`` unit-sanity ranges where
                importable) or breaks cross-field consistency.

Determinism: identical inputs always yield identical outcomes — no randomness,
no time, no I/O. Family comparison is normalization-aware via
``canonical.normalize_manufacturer`` and case-insensitive family names.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.app.identity.canonical import (
    canonical_key,
    normalize_manufacturer,
    variant_key,
)
from backend.app.importers import m3_validation

if TYPE_CHECKING:
    from backend.app.catalog.acquisition.manifest import VerifiedSKU

MATCHED = "MATCHED"
REPLACED = "REPLACED"
UNRESOLVED = "UNRESOLVED"
INVALID = "INVALID"


@dataclass
class Resolution:
    """The outcome of resolving one candidate against the verified set."""

    classification: str  # MATCHED | REPLACED | UNRESOLVED | INVALID
    reason: str
    # Verified SKU (dict view) for MATCHED/REPLACED, else None.
    verified_sku: dict | None = None

    @property
    def is_publishable(self) -> bool:
        return self.classification == MATCHED


# Reuse the fail-closed m3_validation gate for sanity checking.
_RANGE_CHECKS = m3_validation.unit_checks
_CROSS_CHECKS = m3_validation.cross_field_checks


def _norm_family(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def validate_candidate_spec(category: str, spec: dict) -> list[str]:
    """Category sanity checks on a claimed spec (INVALID classification).

    Reuses ``m3_validation.unit_checks`` ranges where the category is one of
    the four planner categories; unknown categories have no registered
    ranges, so only cross-field rules apply there.
    """
    blockers: list[str] = []
    if m3_validation._RANGES.get((category or "").upper()) is not None:
        blockers += _RANGE_CHECKS(category, spec).failures
    blockers += _CROSS_CHECKS(category, spec).failures
    return blockers


def resolve_candidate(
    candidate: dict,
    verified_skus: list,
) -> Resolution:
    """Classify one candidate dict against the verified SKU list.

    ``candidate`` is a Task 1 inventory row (dict with category, name,
    manufacturer, product_family, canonical_key, claimed_spec...).
    ``verified_skus`` is a list of manifest VerifiedSKU instances (or their
    dict form).

    Order of precedence (fail-closed): INVALID first (a spec that violates
    physical sanity is never published no matter what else matches), then
    MATCHED, then REPLACED, then UNRESOLVED.
    """
    sku_objs = [_sku_view(s) for s in verified_skus]
    category = str(candidate.get("category", "")).upper()
    spec = dict(candidate.get("claimed_spec") or {})

    # ---- INVALID: physical/category sanity, fail-closed ----
    sanity = validate_candidate_spec(category, spec)
    if sanity:
        return Resolution(
            INVALID,
            "claimed spec violates unit-sanity/consistency rules: "
            + "; ".join(sanity),
        )

    family = candidate.get("product_family", "")
    manufacturer = candidate.get("manufacturer", "")

    candidates_in_family = [
        s for s in sku_objs
        if str(s["category"]).upper() == category
        and _norm_family(s["product_family"]) == _norm_family(family)
        and normalize_manufacturer(s["manufacturer"])
        == normalize_manufacturer(manufacturer)
    ]
    if not candidates_in_family:
        return Resolution(
            UNRESOLVED,
            f"no verified SKU for family {family!r} in category {category}",
        )

    candidate_key = str(candidate.get("canonical_key") or "").strip()

    # ---- MATCHED: candidate canonical_key == recomputed verified key ----
    for sku in candidates_in_family:
        sku_variant = variant_key(category, dict(sku["spec"] or {}))
        sku_key = canonical_key(
            sku["manufacturer"], category, sku["product_family"],
            sku_variant,
        )
        # Exact key equality OR the candidate key carries the verified
        # variant as a component (inventory keys append the variant suffix
        # to a name-based key; both must share the same variant token).
        if candidate_key == sku_key:
            return Resolution(
                MATCHED,
                f"canonical_key matches verified SKU {sku['mpn']!r}",
                sku,
            )
        variant_from_candidate = variant_key(category, spec)
        if (
            variant_from_candidate
            and sku_variant == variant_from_candidate
            and candidate_key.endswith(variant_from_candidate)
        ):
            return Resolution(
                MATCHED,
                f"variant token {variant_from_candidate!r} matches verified "
                f"SKU {sku['mpn']!r}",
                sku,
            )

    # ---- REPLACED: same family, different variant ----
    best = candidates_in_family[0]
    return Resolution(
        REPLACED,
        f"family {family!r} verified but variant differs; superseded by "
        f"verified SKU {best['mpn']!r}",
        best,
    )


# ---------------------------------------------------------------------------
# Duck-typed access: VerifiedSKU dataclass or plain dict both work, keeping
# this module import-light (manifest.py is only needed by callers).
# ---------------------------------------------------------------------------

_FIELDS = ("category", "name", "manufacturer", "product_family", "mpn",
           "spec")


def _sku_view(sku):
    """Return a uniform getitem-able view over a VerifiedSKU or dict."""
    if isinstance(sku, dict):
        return sku
    return {f: getattr(sku, f) for f in _FIELDS}
