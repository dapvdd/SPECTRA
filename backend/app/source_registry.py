"""Evidence-based licence/attribution register for the nine registered data
sources (Batch 015 — Source Transparency & Data Provenance).

The register is the reproducible, reviewable record of what is actually known
about each source's publisher, terms and redistribution status. It is derived
from the repository evidence gathered in Batch 009
(``data/research/batch009/source_license_assessment.md``) and Batch 010
(``data/research/batch010/source_permission_research.md``) and does not infer a
permissive licence from mere public accessibility.

Two things consume it:

- ``seed_source_metadata`` fills the additive, nullable ``sources`` metadata
  columns on an existing database. It is fill-only: it never overwrites a
  non-NULL value, never deletes a source and never remaps a source id.
- the read-only provenance API falls back to this register when a database row
  predates the Batch 015 columns (for example a database created before the
  migration was applied), so provenance is reported honestly rather than
  invented.

Redistribution status vocabulary (see ``models.source.LICENSE_STATUSES``):

- ``clear``      — an explicit, redistributable licence is documented.
- ``unknown``    — terms are inaccessible or undocumented; no grant exists.
- ``restricted`` — use is explicitly limited and redistribution needs consent.
- ``unresolved`` — legacy data whose redistribution status has not been settled.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.source import LICENSE_STATUSES, Source

_METADATA_FIELDS = (
    "publisher",
    "description",
    "license_name",
    "license_url",
    "license_status",
    "terms_notes",
    "attribution",
    "retrieved_on",
)


def _entry(
    *,
    name: str,
    publisher: str | None,
    description: str,
    license_name: str | None,
    license_url: str | None,
    license_status: str,
    terms_notes: str,
    attribution: str,
    retrieved_on: date | None,
) -> dict:
    if license_status not in LICENSE_STATUSES:
        raise ValueError(f"invalid license_status: {license_status!r}")
    return {
        "name": name,
        "publisher": publisher,
        "description": description,
        "license_name": license_name,
        "license_url": license_url,
        "license_status": license_status,
        "terms_notes": terms_notes,
        "attribution": attribution,
        "retrieved_on": retrieved_on,
    }


# Keyed by the stable ``sources.id`` assigned when each source was registered.
SOURCE_METADATA: dict[int, dict] = {
    1: _entry(
        name="PassMark CPU benchmark catalog (benchmark-cpus.csv)",
        publisher="PassMark Software Pty Ltd",
        description=(
            "PassMark CPU benchmark catalog redistributed as "
            "benchmark-cpus.csv."
        ),
        license_name=None,
        license_url="https://www.passmark.com/legal/disclaimer.php",
        license_status="restricted",
        terms_notes=(
            "PassMark terms restrict reproduction to unaltered material for "
            "personal, non-commercial or intra-organisation use; reproduction "
            "in whole or part for general publication or commercial purposes "
            "requires permission. No bulk redistribution licence is granted. "
            "(Batch 009/010, accessed 2026-10-10.)"
        ),
        attribution=(
            "PassMark Software Pty Ltd, CPU Benchmarks — PassMark terms apply."
        ),
        retrieved_on=date(2026, 10, 10),
    ),
    2: _entry(
        name="Geekbench Browser - Geekbench 7 CPU",
        publisher="Primate Labs Inc.",
        description=(
            "Geekbench 7 CPU results catalogued from the Geekbench Browser "
            "(processor-benchmarks.csv)."
        ),
        license_name=None,
        license_url=None,
        license_status="unknown",
        terms_notes=(
            "Primate Labs / Geekbench terms were not reachable during Batch "
            "009/010 (HTTP 403/404) and no reuse grant is documented in the "
            "repository. Licence unknown — not treated as permissive."
        ),
        attribution=(
            "Geekbench Browser data, Primate Labs Inc. Licence unknown; "
            "attribution obligation not established."
        ),
        retrieved_on=None,
    ),
    3: _entry(
        name="TechPowerUp GPU Database (gpu_1986-2026.csv)",
        publisher="TechPowerUp",
        description=(
            "TechPowerUp GPU Database snapshot, including 44 legacy GPU clock "
            "values."
        ),
        license_name=None,
        license_url="https://www.techpowerup.com/robots.txt",
        license_status="restricted",
        terms_notes=(
            "TechPowerUp robots.txt states content is for personal, "
            "non-commercial use; data mining/scraping and creating or "
            "providing cached/archived datasets are prohibited without prior "
            "written permission. No redistribution licence; contact "
            "w1zzard@techpowerup.com."
        ),
        attribution=(
            "TechPowerUp GPU Database. Redistribution restricted pending "
            "written permission."
        ),
        retrieved_on=date(2026, 10, 10),
    ),
    4: _entry(
        name="GPU Ark GPU specifications & benchmarks dataset",
        publisher="GPU Ark",
        description="GPU Ark specifications and benchmarks dataset.",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        license_status="clear",
        terms_notes=(
            "CC BY 4.0 is documented in the repository "
            "(data/raw/README.md). Attribution required; no share-alike."
        ),
        attribution="GPU Ark (CC BY 4.0).",
        retrieved_on=None,
    ),
    5: _entry(
        name="Wikipedia (English)",
        publisher="Wikimedia Foundation — Wikipedia contributors",
        description=(
            "English Wikipedia article data parsed from article wikitext."
        ),
        license_name="CC BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        license_status="clear",
        terms_notes=(
            "CC BY-SA 4.0. Attribution and share-alike obligations apply to "
            "redistributed derivatives."
        ),
        attribution="Wikipedia, The Free Encyclopedia (CC BY-SA 4.0).",
        retrieved_on=None,
    ),
    6: _entry(
        name="Intel ARK (archived via Wayback Machine)",
        publisher="Intel Corporation",
        description=(
            "Intel ARK product pages cross-checked through the Wayback Machine."
        ),
        license_name=None,
        license_url=None,
        license_status="unknown",
        terms_notes=(
            "The Intel terms-of-use page returned HTTP 403 to automated "
            "access (Batch 009); no bulk reuse grant is documented. Unknown "
            "licence — not treated as permissive."
        ),
        attribution="Intel Corporation (Intel ARK). Licence unknown.",
        retrieved_on=None,
    ),
    7: _entry(
        name="Unknown (source not documented in artifact)",
        publisher=None,
        description=(
            "Legacy Batch 008 placeholder for rows whose originating source "
            "was not documented in the import artifact."
        ),
        license_name=None,
        license_url=None,
        license_status="unresolved",
        terms_notes=(
            "The originating source is not documented; redistribution status "
            "is unresolved and must not be treated as licensed."
        ),
        attribution="Origin not documented.",
        retrieved_on=None,
    ),
    8: _entry(
        name="Intel ARK (intel-cpus.csv snapshot)",
        publisher="Intel Corporation",
        description=(
            "Intel processor specifications redistributed through the "
            "felixsteinke/cpu-spec-dataset intel-cpus.csv snapshot."
        ),
        license_name=None,
        license_url=None,
        license_status="unknown",
        terms_notes=(
            "Intel ARK terms were not accessible to automated checks (HTTP "
            "403, Batch 009); the redistributing repository declares "
            "AGPL-3.0 for its code only and no data licence. Unknown licence."
        ),
        attribution=(
            "Intel Corporation via felixsteinke/cpu-spec-dataset. Licence "
            "unknown."
        ),
        retrieved_on=date(2026, 10, 10),
    ),
    9: _entry(
        name="AMD product specifications (amd-cpus.csv snapshot)",
        publisher="Advanced Micro Devices, Inc.",
        description=(
            "AMD processor specifications redistributed through the "
            "felixsteinke/cpu-spec-dataset amd-cpus.csv snapshot."
        ),
        license_name=None,
        license_url="https://www.amd.com/en/corporate/copyright",
        license_status="unknown",
        terms_notes=(
            "The AMD copyright page was accessed (Batch 009); no bulk "
            "data-reuse grant was found. Unknown licence — not treated as "
            "permissive."
        ),
        attribution=(
            "Advanced Micro Devices, Inc. via felixsteinke/cpu-spec-dataset. "
            "Licence unknown."
        ),
        retrieved_on=date(2026, 10, 10),
    ),
}


def registered_metadata(
    source_id: int | None = None,
    name: str | None = None,
) -> dict | None:
    """Return the registered metadata for a source id and/or unique name.

    When both ``source_id`` and ``name`` are supplied they must agree, so a
    differently-named row that happens to reuse a registered id is not
    mis-attributed.
    """
    entry = SOURCE_METADATA.get(source_id) if source_id is not None else None
    if entry is not None and (name is None or entry["name"] == name):
        return entry
    if name is not None:
        for candidate in SOURCE_METADATA.values():
            if candidate["name"] == name:
                return candidate
    return None


def seed_source_metadata(session: Session) -> dict:
    """Fill the nullable ``sources`` metadata columns from the register.

    Fill-only: a non-NULL database value is never overwritten, no source row is
    created, deleted or renamed, and source ids are never remapped. Returns a
    small report of how many rows/columns were updated.
    """
    report = {"updated_rows": 0, "updated_fields": 0, "unmatched": []}

    for source in session.query(Source).order_by(Source.id).all():
        entry = registered_metadata(source.id, source.name)
        if entry is None:
            report["unmatched"].append(source.id)
            continue

        row_changed = False
        for field in _METADATA_FIELDS:
            if getattr(source, field) is not None:
                continue
            value = entry[field]
            if value is None:
                continue
            setattr(source, field, value)
            report["updated_fields"] += 1
            row_changed = True

        if row_changed:
            report["updated_rows"] += 1

    session.commit()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=None,
        help="Target database path (default: configured SPECTRA database).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the register without writing anything.",
    )
    arguments = parser.parse_args()

    if arguments.database:
        target = Path(arguments.database)
        engine = create_engine(
            "sqlite:///" + str(target).replace("\\", "/"),
        )
        session_factory = lambda: Session(engine)  # noqa: E731
    else:
        engine = None
        session_factory = SessionLocal

    with session_factory() as session:
        if arguments.dry_run:
            print(f"registered sources: {len(SOURCE_METADATA)}")
            for source_id, entry in sorted(SOURCE_METADATA.items()):
                print(
                    f"  {source_id}: {entry['name']} -> "
                    f"license_status={entry['license_status']}"
                )
            print("dry run: no changes written")
            return 0

        report = seed_source_metadata(session)
        print(f"seed report: {report}")

    if engine is not None:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
