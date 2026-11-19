"""M3 Phase 2 — curated source adapters (RAM/Storage/Motherboard/PSU).

Two human-in-the-loop adapters over the existing Stage 2 SourceAdapter
framework (docs/m3/M3_SOURCE_FEASIBILITY.md §4):

1. WikipediaCuratedAdapter — curated rows citing Wikipedia article revisions.
   License status ``clear`` (CC BY-SA 4.0): attribution is carried per value
   (source_url = the cited article URL, source_reference carries the revision
   id when provided).

2. ManualOfficialCitationAdapter — curated rows citing official manufacturer
   product pages. The *source* license status stays honestly ``unknown``
   (site terms publish no redistribution license); the *acquired values* are
   evidence_status='verified' downstream because a human verified each value
   against the cited page at access time. No network I/O happens here —
   rows are prepared by a human curator; URLs are stored as citations.

Both adapters are pure transformations (no fetches), satisfying the mission
safety contract: no unauthorized crawling, no anti-bot interaction, no
secret handling.
"""
from __future__ import annotations

import json

from backend.app.scripts.source_acquisition import (
    CsvSourceAdapter,
    SourceAdapter,
    build_acquired_value,
)

# Registry keys (docs/m3/M3_SOURCE_REGISTRY.md rows M3-1 / M3-2).
WIKIPEDIA_CURATED = "wikipedia-curated"
MANUAL_OFFICIAL_CITATION = "manual-official-citation"

_WIKIPEDIA_LICENSE_NAME = "CC BY-SA 4.0"
_MANUAL_LICENSE_NAME = "site terms (no redistribution license published)"

_REQUIRED_ROW_COLUMNS = (
    "hardware_name",
    "manufacturer",
    "category",
    "citation_url",
)


class CuratedRowAdapter(CsvSourceAdapter):
    """Shared implementation for the two curated M3 adapters.

    A "row" is one curated product record:
      - hardware_name / manufacturer / category: identity,
      - fields: JSON object of spec field -> value (validated downstream),
      - citation_url: the page a human verified the values against,
      - citation_revision: optional (Wikipedia revision id),
      - access_date: when the human verified it (ISO date).
    """

    required_columns = _REQUIRED_ROW_COLUMNS
    license_name: str = ""
    # Whether provenance should reference the revision id (Wikipedia) or not.
    uses_revisions: bool = False

    def map_record(self, row: dict[str, str]) -> dict:
        hardware_name = str(row.get("hardware_name", "")).strip()
        citation_url = str(row.get("citation_url", "")).strip()
        if not hardware_name:
            raise ValueError("curated row missing hardware_name")
        if not citation_url:
            raise ValueError(
                f"curated row {hardware_name!r} missing citation_url "
                "(a curated record without a citation cannot be imported)"
            )
        fields_json = row.get("fields_json") or row.get("fields") or "{}"
        try:
            fields = json.loads(fields_json) if isinstance(fields_json, str) \
                else dict(fields_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"curated row {hardware_name!r} has invalid fields JSON: {exc}"
            ) from None
        if not isinstance(fields, dict):
            raise ValueError(
                f"curated row {hardware_name!r} fields must be an object"
            )
        return {
            "hardware_name": hardware_name,
            "manufacturer": str(row.get("manufacturer", "")).strip(),
            "category": str(row.get("category", "")).strip(),
            "fields": fields,
            "citation_url": citation_url,
            "citation_revision": str(row.get("citation_revision", "")).strip(),
            "access_date": str(row.get("access_date", "")).strip(),
        }

    def acquire_values(self, record: dict) -> list:
        """Emit one AcquiredValue per spec field in a mapped record.

        Zero network I/O: the citation URL is stored, never fetched.
        The value's ``source_url`` is the *citation* (per-record), not the
        adapter's base URL — provenance points at the page a human verified.
        """
        fields: dict = record.get("fields", {})
        revision = record.get("citation_revision", "")
        access_date = record.get("access_date", "")
        reference = (
            f"{record['citation_url']} rev {revision}" if revision
            else record["citation_url"]
        )
        values = []
        for field_name, raw_value in fields.items():
            normalized, unit = self.normalize_field_value(field_name, raw_value)
            value = build_acquired_value(
                self,
                hardware_name=record["hardware_name"],
                field=field_name,
                raw_value=raw_value,
                normalized_value=normalized,
                unit=unit,
                source_pointer=reference,
                confidence="high",
                hardware_kind=record.get("category", "").upper() or None,
            )
            # Provenance points at the cited page, not the adapter base URL.
            value.source_url = record["citation_url"]
            # Carry the human verification date in the publication date slot
            # (AcquiredValue has no dedicated access_date; the enrichment
            # pipeline maps it into field_provenance.access_date).
            value.source_publication_date = access_date or None
            values.append(value)
        return values


class WikipediaCuratedAdapter(CuratedRowAdapter):
    source_name = "Wikipedia (English) — curated"
    source_url = "https://en.wikipedia.org/"
    license_status = "clear"
    license_name = _WIKIPEDIA_LICENSE_NAME
    uses_revisions = True


class ManualOfficialCitationAdapter(CuratedRowAdapter):
    source_name = "Official product pages — manual citations"
    source_url = "https://vendor.example/ (per-record citation URL)"
    license_status = "unknown"
    license_name = _MANUAL_LICENSE_NAME
    uses_revisions = False
