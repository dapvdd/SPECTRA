"""Behavior-identical shared normalization primitives.

These functions were originally defined in
``backend/app/importers/benchmark_normalizer.py`` and are moved here verbatim
so that the shared logic has a public, tested home. Importers continue to
import these from their existing facade modules, so behavior does not change.
"""

import re
import unicodedata

# Control and format characters carry no visible text. They are never part of a
# hardware name, and they survive plain whitespace collapsing because they are
# not Unicode whitespace, so they must be removed explicitly or they silently
# break exact-match identity resolution downstream.
INVISIBLE_CHARACTER_CATEGORIES = frozenset({"Cc", "Cf"})


def strip_invisible_characters(value: str) -> str:
    return "".join(
        character
        for character in value
        if unicodedata.category(character)
        not in INVISIBLE_CHARACTER_CATEGORIES
    )


def normalize_name(value: str | None) -> str | None:
    if not value:
        return None

    # Collapse whitespace before removing invisible characters so that a
    # control character acting as a separator becomes a space instead of
    # silently joining two words together.
    value = re.sub(r"\s+", " ", value)
    value = strip_invisible_characters(value)

    return value.strip()


def parse_watt(value: str | None) -> float | None:
    if not value:
        return None

    # A wattage is a plain non-negative decimal followed by a complete watt
    # unit. The lookbehind rejects digits that belong to a longer numeric
    # token, so a signed value ("-5 W") or scientific notation ("1e3 W") is
    # not silently reduced to a different magnitude. The trailing word
    # boundary rejects a "w" that merely starts a longer word.
    match = re.search(
        r"(?<![\d.eE+-])(\d+(?:\.\d+)?)\s*(?:W|Watts?)\b",
        value,
        re.IGNORECASE,
    )

    if not match:
        return None

    return float(match.group(1))


def parse_int(value: str | None) -> int | None:
    if not value:
        return None

    match = re.fullmatch(
        r"\s*(\d+)\s*",
        value,
    )

    if not match:
        return None

    return int(match.group(1))
