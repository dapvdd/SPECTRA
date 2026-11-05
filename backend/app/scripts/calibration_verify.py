"""Stage 6 — calibration verification of suitability star anchors.

Verifies that the star anchors hard-coded in
``backend.app.services.suitability_service`` are consistent with the actual
score distribution in the benchmarked population (without changing the scoring
methodology). Any drift is *reported*, not silently rewritten.

Contract:
- ``anchor_percentiles(sf, test_type)`` returns the observed p10..p90 score
  values for the given benchmark family from the dev DB.
- ``calibration_report()`` compares documented anchors vs observed percentiles
  and returns a deterministic dict with per-family ``documented``,
  ``observed``, ``max_pct_err``, ``status`` (``ok`` | ``drift``).
- The single-core / multi-core families must both be analyzable.
- Debugging/verification only: no scoring file is mutated by this module.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.services.suitability_service import (
    _MULTI_CORE_ANCHORS,
    _SINGLE_CORE_ANCHORS,
)

# Dev database — never production.
_DEV_DB = str(Path(__file__).resolve().parents[3] / "data" / "dev" / "spectra_dev.db")

# Drift threshold: flag as "drift" when max % error exceeds this fraction.
_DRIFT_THRESHOLD = 0.10  # 10 %

# Percentile ranks to compute (p10, p30, p50, p70, p90 → map to stars 1-5).
_PERCENTILES = (10, 30, 50, 70, 90)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _index_for_percentile(p: int, n: int) -> int:
    """0-based index into the sorted array for percentile ``p``.

    Uses the standard nearest-rank formulation ``round(p * (n - 1) / 100)``,
    clamped to ``[0, n-1]``. For 10 values this maps p10->1, p50->4/5,
    p90->8, matching the test's expected anchor distribution.
    """
    raw = p * (n - 1) / 100.0
    return max(0, min(round(raw), n - 1))


def anchor_percentiles(sf: sessionmaker, test_type: str) -> dict | None:
    """Return observed percentile score values for a benchmark family.

    Args:
        sf: SQLAlchemy sessionmaker bound to the benchmark DB.
        test_type: one of ``"single-core"`` or ``"multi-core"``.

    Returns:
        Dict with ``p10``, ``p30``, ``p50``, ``p70``, ``p90`` and ``count``
        keys, or ``None`` when no rows exist for the family.
        Uses the nearest-rank percentile definition.
    """
    with sf() as session:
        from backend.app.models import BenchmarkResult

        rows = session.scalars(
            select(BenchmarkResult.score).where(
                BenchmarkResult.test_type == test_type,
                BenchmarkResult.score.isnot(None),
            )
        ).all()

    scores = sorted(rows)
    n = len(scores)

    if n == 0:
        return None

    result: dict = {"count": n}
    for p in _PERCENTILES:
        idx = _index_for_percentile(p, n)
        result[f"p{p}"] = float(scores[idx])

    return result


def _documented_anchors(test_type: str) -> tuple:
    """Return the documented star-anchor tuple for the given benchmark family."""
    if test_type == "single-core":
        return _SINGLE_CORE_ANCHORS
    if test_type == "multi-core":
        return _MULTI_CORE_ANCHORS
    raise ValueError(f"Unknown benchmark family: {test_type!r}")


def _max_pct_err(documented: tuple, observed: list[float]) -> float:
    """Maximum absolute percentage error between two equal-length sequences."""
    max_err = 0.0
    for d, o in zip(documented, observed):
        if d != 0:
            err = abs(o - d) / d
            if err > max_err:
                max_err = err
    return round(max_err, 6)


def _pct_err_to_pct(max_err: float) -> float:
    """Convert fraction to percentage, rounded to 2 decimal places."""
    return round(max_err * 100, 2)


def calibration_report() -> dict:
    """Compare documented anchors against observed benchmark percentiles.

    Reads benchmark data from the dev DB and compares the hard-coded
    ``_SINGLE_CORE_ANCHORS`` / ``_MULTI_CORE_ANCHORS`` star anchors against
    the actual p10/p30/p50/p70/p90 distribution of the benchmarked population.

    Returns:
        Deterministic dict::

            {
                "target": "<dev_db_path>",
                "families": {
                    "single-core": {
                        "documented": [667.0, 983.0, 1325.0, 1637.0, 2020.0],
                        "observed":   [p10,   p30,   p50,   p70,   p90  ],
                        "max_pct_err": 3.2,
                        "status": "ok",   # or "drift"
                    },
                    "multi-core": { ... },
                }
            }

    The dev DB is read-only (this function never writes).
    """
    engine = create_engine(
        f"sqlite:///{_DEV_DB}",
        connect_args={"check_same_thread": False},
    )
    sf = sessionmaker(bind=engine)

    families = ["single-core", "multi-core"]
    result: dict = {
        "target": _DEV_DB,
        "families": {},
    }

    for family in families:
        pcts = anchor_percentiles(sf, family)
        documented = _documented_anchors(family)

        if pcts is None or pcts.get("count", 0) == 0:
            # No benchmark data — honest gap.
            result["families"][family] = {
                "documented": list(documented),
                "observed": [None] * 5,
                "max_pct_err": None,
                "status": "no_data",
            }
            continue

        observed = [
            pcts.get("p10"),
            pcts.get("p30"),
            pcts.get("p50"),
            pcts.get("p70"),
            pcts.get("p90"),
        ]

        max_err = _max_pct_err(documented, observed)
        max_err_pct = _pct_err_to_pct(max_err)

        result["families"][family] = {
            "documented": list(documented),
            "observed": [float(o) if o is not None else None for o in observed],
            "max_pct_err": max_err_pct,
            "status": "drift" if max_err > _DRIFT_THRESHOLD else "ok",
        }

    engine.dispose()
    return result


# ---------------------------------------------------------------------------
# CLI (optional, for one-off verification)
# ---------------------------------------------------------------------------


def main() -> int:
    import json
    import sys

    report = calibration_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())