"""GPU identity resolution — conservative, source-aware matching.

The enrichment pipeline matches hardware on EXACT name by default (never
conflates distinct variants). For candidate discovery against a research CSV
whose names carry vendor prefixes, this module provides a SAFE normalizer that:

- Strips only the leading vendor product prefix (NVIDIA/AMD/Intel/MSI/...).
- PRESERVES model-number digits (HD 5770 != HD 7970, GMA 600 != GMA 3600,
  Vega 48 != Vega 16).
- PRESERVES desktop/mobile and SKU suffixes by token identity.
- A candidate CSV name matches a DB name only if the DB token set is a SUBSET
  of the CSV token set AND the DB name carries at least one digit anchor.

Ambiguity is never resolved by guessing: callers should quarantine candidates
whose TDP conflicts rather than picking one.
"""

from __future__ import annotations

import re

# Leading vendor / board-partner prefixes that do NOT carry GPU identity.
# Deliberately product-agnostic so a wrong vendor on a CSV row is tolerated
# while model identity is preserved.
_VENDOR_PREFIXES = (
    "nvidia", "amd", "intel", "ati", "msi", "asus", "gigabyte", "sapphire",
    "xfx", "evga", "zotac", "galax", "palit", "gainward", "inno3d", "colorful",
    "maxsun", "powercolor", "kfa2", "pny", "his", "visiontek", "leadtek",
    "sparkle", "biostar", "manli", "club3d", "point of view", "pny",
)
_VENDOR_RE = re.compile(
    r"^(?:" + "|".join(re.escape(v) for v in sorted(_VENDOR_PREFIXES, key=len, reverse=True)) + r")\s+",
    re.IGNORECASE,
)


def strip_vendor_prefix(name: str) -> str:
    """Remove only the leading vendor/product prefix; keep the model identity."""
    n = name.strip()
    n = _VENDOR_RE.sub("", n)
    return re.sub(r"\s+", " ", n).strip()


def identity_tokens(name: str) -> frozenset[str]:
    """Token identity of a GPU name: every whitespace token, whole.

    Preserves '5770' vs '7970', '600' vs '3600', '48' vs '16', and trailing
    SKU/mobility markers ('6970m' != '6970', 'mobile' differs).
    Sub-digit strings are NOT extracted from alphanumeric tokens, so '6970m'
    stays a single token and never matches '6970'.
    """
    n = strip_vendor_prefix(name).lower()
    return frozenset(part for part in n.split() if part)


def safe_gpu_match(csv_name: str, db_name: str) -> bool:
    """True only when csv_name is a plausible identity match for db_name.

    Conservative rules:
    - All DB whole tokens must be present in the CSV token set (CSV may add
      vendor/SKU tokens, but may NOT drop any DB token).
    - Every non-digit DB token must appear DIRECTLY in CSV tokens (blocks
      "6970m" matching "6970" because the DB token "6970" is not a whole
      token in "6970m").
    - DB name must carry at least one purely-numeric token (model anchor).
    - This preserves HD 5770 != HD 7970, GMA 600 != GMA 3600, Vega 48 != Vega 16,
      and desktop vs mobile suffix differences.
    """
    db_tokens = identity_tokens(db_name)
    csv_tokens = identity_tokens(csv_name)
    if not db_tokens.issubset(csv_tokens):
        return False
    pure_letter_db = {t for t in db_tokens if not t.isdigit()}
    if not pure_letter_db.issubset(csv_tokens):
        return False
    # DB must carry at least one purely-numeric token as model anchor.
    db_numeric_tokens = {t for t in db_tokens if t.isdigit()}
    return bool(db_numeric_tokens)


def gpu_collides(csv_name_a: str, csv_name_b: str) -> bool:
    """True if two CSV names report DIFFERENT model-digit identities for the same DB match.

    Used to quarantine ambiguous candidates before any import.
    """
    digits_a = set(re.findall(r"\d+", csv_name_a.lower()))
    digits_b = set(re.findall(r"\d+", csv_name_b.lower()))
    return digits_a != digits_b



