"""Idempotent correction of hardware names carrying invisible characters.

A canonical hardware name must not contain Unicode control (``Cc``) or
format (``Cf``) characters. ``U+200B ZERO WIDTH SPACE`` in particular is
invisible in every interface, yet it is not Unicode whitespace, so it
survives ordinary whitespace collapsing. A name that differs only by such
a character therefore defeats the exact-match identity resolution used by
hardware imports and by benchmark matching.

The correction rewrites a stored name to its normalized form only when the
two differ, so it makes no further changes when it is run again. It never
adds, removes, or reinterprets any visible part of a name.

Run with ``--dry-run`` to report the affected rows without writing.
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.importers.benchmark_normalizer import normalize_name
from backend.app.models import Hardware


def find_affected_hardware(
    session: Session,
) -> list[tuple[int, str, str]]:
    """Return ``(hardware_id, current_name, normalized_name)`` for every
    hardware row whose name is not already in normalized form."""
    affected: list[tuple[int, str, str]] = []

    for hardware in session.scalars(select(Hardware).order_by(Hardware.id)):
        normalized = normalize_name(hardware.name)

        if normalized is None or normalized == hardware.name:
            continue

        affected.append((hardware.id, hardware.name, normalized))

    return affected


def apply_correction(session: Session) -> list[tuple[int, str, str]]:
    """Normalize affected hardware names and return the applied changes."""
    changes = find_affected_hardware(session)

    if not changes:
        return []

    for hardware_id, _, normalized in changes:
        hardware = session.get(Hardware, hardware_id)
        hardware.name = normalized

    session.commit()

    return changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Remove invisible characters from stored hardware names."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report affected rows without writing them.",
    )
    arguments = parser.parse_args()

    with SessionLocal() as session:
        changes = find_affected_hardware(session)

        print(f"rows requiring normalization: {len(changes)}")

        for hardware_id, before, after in changes:
            print(f"  hardware_id={hardware_id}")
            print(f"    before: {before!r}")
            print(f"    after:  {after!r}")

        if arguments.dry_run:
            print("dry run: no changes written")
            return 0

        applied = apply_correction(session)

    print(f"rows updated: {len(applied)}")

    with SessionLocal() as session:
        remaining = find_affected_hardware(session)

    print(f"rows still requiring normalization: {len(remaining)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
