"""M3.1 Task 3 — category-specific citation-planning adapters.

M3.1 keeps the M3 source-access contract intact (docs/m3/M3_SOURCE_REGISTRY.md):

- Wikipedia (M3-1, license clear): the ONLY automated path — revision
  resolution via ``wiki_rest.WikipediaRestClient`` so curated citations carry
  immutable revision anchors. Content planning (which article a category
  needs) is a pure function here.
- Manufacturer pages (M3-2, license unknown): human-citation workflow ONLY.
  These adapters never construct a URL to fetch; they only PLAN the citation
  a human must make (per-SKU product page) and structurally refuse to expose
  any fetch capability.

No adapter here performs network I/O at import time; the only networked
module in the package is ``wiki_rest`` (explicitly constructed by a curator
runner, never by the publisher path).
"""
from __future__ import annotations

from dataclasses import dataclass

# Wikipedia technology articles per category / fact vocabulary (M3-1).
# Same corpus the M3 pilot seed uses; planned here so a manifest row can cite
# a revision-anchored article URL deterministically.
WIKI_TECH_ARTICLES: dict[str, str] = {
    "RAM.ddr_generation": "DDR5 SDRAM",
    "STORAGE.interface": "NVM Express",
    "STORAGE.form_factor": "M.2",
    "MOTHERBOARD.form_factor": "ATX",
    "PSU.efficiency_rating": "80 Plus",
}

# Manufacturer product-page URL templates per category — citation PLANS for
# the human workflow. Deliberately NOT fetchable helpers: a plan is a string
# the curator reads and verifies; the pipeline never requests it.
MANUFACTURER_CITATION_TEMPLATE: dict[str, str] = {
    "RAM": "https://www.corsair.com/us/en/c/memory (per-SKU product page)",
    "STORAGE": "https://semiconductor.samsung.com/consumer-storage/ (per-SKU page)",
    "MOTHERBOARD": "https://www.gigabyte.com/Motherboard/ (per-SKU page)",
    "PSU": "https://seasonic.com/ (per-SKU spec page)",
}


@dataclass(frozen=True)
class CitationPlan:
    """One planned citation (what a human must verify, and where it lives)."""

    category: str
    spec_field: str
    source_kind: str  # "wikipedia" | "manufacturer-page"
    article_title: str  # Wikipedia title, or "" for manufacturer plans
    manufacturer_url_hint: str  # human-verification hint, never fetched

    @property
    def is_automatable(self) -> bool:
        """Only Wikipedia citations may ever be resolved automatically."""
        return self.source_kind == "wikipedia"


def plan_citations(category: str, spec_fields: list[str]) -> list[CitationPlan]:
    """Plan citations for one record's spec fields (pure, deterministic).

    Field-level rule (mirrors the M3 evidence tiers):
    - fields with a technology vocabulary article -> Wikipedia plan;
    - every other populated field -> manufacturer per-SKU page plan (human).
    """
    category = (category or "").upper()
    plans: list[CitationPlan] = []
    for spec_field in spec_fields:
        wiki_key = f"{category}.{spec_field}"
        if wiki_key in WIKI_TECH_ARTICLES:
            plans.append(CitationPlan(
                category=category,
                spec_field=spec_field,
                source_kind="wikipedia",
                article_title=WIKI_TECH_ARTICLES[wiki_key],
                manufacturer_url_hint="",
            ))
        else:
            plans.append(CitationPlan(
                category=category,
                spec_field=spec_field,
                source_kind="manufacturer-page",
                article_title="",
                manufacturer_url_hint=MANUFACTURER_CITATION_TEMPLATE.get(
                    category, ""),
            ))
    return plans
