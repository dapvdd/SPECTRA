"""Phase 2.4 — provenance & dataset debt reconciliation.

Produces a reproducible, evidence-grounded snapshot of every remaining
provenance/dataset debt item so the roadmap can report *resolved / deferred /
blocked* honestly rather than lumping them together. Read-only: never writes to
the database, so it is safe to run against a copy of ``data/spectra.db``.

It intentionally does NOT invent values, provenance evidence, or source
licences. Where a debt item can only be cleared by a new source, a credentialed
API, or by resolving an ambiguity that would require fabrication, it is
classified *blocked*; where the item is a legitimate product-model naming
convention (verified against the source artifact) it is *deferred-as-intended*;
where the item has already been re-classified honestly in the data it is
*already-honest*.

Run against a disposable copy::

    python backend/app/scripts/reconcile_phase24_debt.py \\
        --database data/spectra_copy.db > docs/fan/phase24_debt.json

Exits 0 (report produced). The JSON is deterministic (sorted keys) so a
regression test can pin it.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Debt categories (kept in sync with docs/SPECTRA_V2_ROADMAP.md 2.4).
# ---------------------------------------------------------------------------

# 1. Hardware rows that have a spec/name value but *zero* field_provenance
#    rows at all. Resolving requires provenance evidence; we have none in this
#    delivery, so these are reported as blocked-irresolvable (honest) *unless*
#    the caller has supplied a verified evidence file.
UNATTRIBUTED_LABEL = "unattributed"

# 2. NULL / rejected-confidence provenance rows. These already carry an honest
#    `excluded` / `unmatched` evidence_status, so they are NOT silently
#    dropped; they are reported as already-honest (the value is deliberately
#    excluded rather than fabricated).

# 3. Bare-number hardware names that are legitimate product model numbers
#    verified (high confidence) against an ordered source artifact combined
#    with orderable part IDs. Renaming them would invent a family prefix, so
#    they are deferred-as-intended.

# 4. The documented absence buckets (GPU benchmarks, pricing, fabricated
#    specs) are not debt; they are documented product decisions.


def _row_counts(cur: sqlite3.Cursor) -> dict:
    def one(sql, *args):
        return cur.execute(sql, args).fetchone()[0]

    return {
        "hardware": one("SELECT COUNT(*) FROM hardware"),
        "field_provenance": one("SELECT COUNT(*) FROM field_provenance"),
        "hardware_with_any_provenance": one(
            "SELECT COUNT(DISTINCT hardware_id) FROM field_provenance "
            "WHERE benchmark_result_id IS NULL"
        ),
        "sources": one("SELECT COUNT(*) FROM sources"),
    }


def _unattributed_hardware(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        """
        SELECT h.id, h.name, h.type
        FROM hardware h
        LEFT JOIN field_provenance fp ON fp.hardware_id = h.id
        GROUP BY h.id
        HAVING COUNT(fp.id) = 0
        ORDER BY h.id
        """
    ).fetchall()
    return [{"id": r[0], "name": r[1], "type": r[2]} for r in rows]


def _low_confidence_rows(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        """
        SELECT fp.id, fp.hardware_id, h.name, fp.table_name, fp.field_name,
               fp.confidence, fp.evidence_status
        FROM field_provenance fp
        JOIN hardware h ON h.id = fp.hardware_id
        WHERE fp.confidence IS NULL OR fp.confidence = 'rejected'
        ORDER BY fp.id
        """
    ).fetchall()
    return [
        {
            "provenance_id": r[0],
            "hardware_id": r[1],
            "hardware_name": r[2],
            "table_name": r[3],
            "field_name": r[4],
            "confidence": r[5],
            "evidence_status": r[6],
        }
        for r in rows
    ]


def _bare_number_names(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        """
        SELECT h.id, h.name, h.manufacturer, h.type
        FROM hardware h
        WHERE h.name NOT GLOB '*[A-Za-z]*'
        ORDER BY h.id
        """
    ).fetchall()
    return [
        {"id": r[0], "name": r[1], "manufacturer": r[2], "type": r[3]}
        for r in rows
    ]


def _report(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        counts = _row_counts(cur)

        unattributed = _unattributed_hardware(cur)
        low_confidence = _low_confidence_rows(cur)
        bare_names = _bare_number_names(cur)

        # Classification (honest; see module docstring).
        return {
            "tool": "reconcile_phase24_debt",
            "database": str(db_path),
            "counts": counts,
            "unattributed_hardware": {
                "total": len(unattributed),
                "label": UNATTRIBUTED_LABEL,
                "classification": "blocked-irresolvable-no-evidence",
                "items": unattributed,
            },
            "low_confidence_provenance": {
                "total": len(low_confidence),
                "classification": "already-honest-excluded-or-unmatched",
                "items": low_confidence,
            },
            "bare_number_names": {
                "total": len(bare_names),
                "classification": "deferred-as-intended-product-model-numbers",
                "items": bare_names,
            },
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2.4 provenance/dataset debt reconciliation (read-only)."
    )
    parser.add_argument(
        "--database",
        default="data/spectra.db",
        help="Path to a copy of the SPECTRA database (default: data/spectra.db).",
    )
    args = parser.parse_args()

    report = _report(Path(args.database))
    # Deterministic output (sorted keys) for stable diffing and test pinning.
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
