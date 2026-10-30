"""Deterministic benchmark quality & confidence scoring (Phase 1.2).

The score is computed strictly from data that already exists for a benchmark
result — no new columns, no invented numbers, no writes. It weights three
honest evidence signals and a provenance vote:

  - attribution   : the row carries a ``source_id`` (a real source, not NULL)
  - timestamp     : the row carries a ``recorded_at`` value
  - licence       : the source's ``license_status`` is a clearly-permissive one
  - evidence      : the benchmark's provenance records vote verified/uncertain

Rules that keep the score honest (matching the roadmap AC):

  * The score is deterministic: the same data always yields the same value.
  * ``excluded`` / ``unmatched`` provenance votes veto the row: it gets no
    score (``None``) rather than a confidence we have explicitly disclaimed.
  * A row with no disposing evidence still returns a score (a low one), but a
    row with a provenance ``excluded`` / ``unmatched`` vote returns ``None``.

The returned payload reports each signal and the labelled score band so the UI
can surface it without making any absolute "this is correct" claim.
"""

# Normalised weights for the headline signals; sum to 1 so the score is a
# fraction of the available evidence.
_ATTRIBUTION_WEIGHT = 0.35
_TIMESTAMP_WEIGHT = 0.25
_LICENCE_WEIGHT = 0.20
_EVIDENCE_WEIGHT = 0.20

# A provenance vote of verified/uncertain carries a strength; excluded and
# unmatched veto the row entirely (they are the documented "no score" cases).
_VERIFIED_STRENGTH = 1.0
_UNCERTAIN_STRENGTH = 0.5
_VETO_STATUSES = frozenset({"excluded", "unmatched"})

# Licence statuses that read as clearly permissive for benchmark reuse.
_CLEAR_LICENCE_STATUSES = frozenset({"clear"})

# Labelled bands so consumers never have to interpret a raw float.
def _band(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def score_benchmark_quality(*, benchmark) -> dict:
    """Return a deterministic quality payload for one BenchmarkResult.

    ``benchmark`` may be any object exposing ``source_id``, ``recorded_at``,
    ``source`` (optional) and ``field_provenance`` (optional iterable). Each
    signal is evaluated independently and weighted; the result is a dict with a
    ``score`` (float 0..1) or ``None`` when a provenance veto applies, plus the
    per-signal breakdown for transparency.
    """
    vetoed = _provenance_vetoes(benchmark)

    if vetoed:
        return {
            "score": None,
            "band": None,
            "signals": {
                "attribution": _has_attribution(benchmark),
                "timestamp": _has_timestamp(benchmark),
                "licence": _has_clear_licence(benchmark),
                "evidence_verified": False,
                "evidence_uncertain": False,
            },
            "vetoed": True,
            "label": "no score",
            "reason": "excluded or unmatched provenance",
        }

    attribution = _has_attribution(benchmark)
    timestamp = _has_timestamp(benchmark)
    licence = _has_clear_licence(benchmark)
    evidence_verified, evidence_uncertain = _evidence_strength(benchmark)

    contribution = 0.0
    contribution += _ATTRIBUTION_WEIGHT if attribution else 0.0
    contribution += _TIMESTAMP_WEIGHT if timestamp else 0.0
    contribution += _LICENCE_WEIGHT if licence else 0.0
    contribution += _EVIDENCE_WEIGHT * (
        _VERIFIED_STRENGTH if evidence_verified
        else (_UNCERTAIN_STRENGTH if evidence_uncertain else 0.0)
    )

    score = round(contribution, 4)

    return {
        "score": score,
        "band": _band(score),
        "signals": {
            "attribution": attribution,
            "timestamp": timestamp,
            "licence": licence,
            "evidence_verified": evidence_verified,
            "evidence_uncertain": evidence_uncertain,
        },
        "vetoed": False,
        "label": _band(score),
        "reason": None,
    }


def _has_attribution(benchmark) -> bool:
    return getattr(benchmark, "source_id", None) is not None


def _has_timestamp(benchmark) -> bool:
    return getattr(benchmark, "recorded_at", None) is not None


def _has_clear_licence(benchmark) -> bool:
    source = getattr(benchmark, "source", None)
    if source is None:
        return False
    status = getattr(source, "license_status", None)
    return status in _CLEAR_LICENCE_STATUSES


def _evidence_strength(benchmark) -> tuple[bool, bool]:
    """Return (verified, uncertain) booleans for the benchmark's provenance.

    A single verified vote already carries the evidence weight; otherwise a
    single uncertain vote contributes partial weight. Absent any vote, both are
    false and the evidence signal contributes zero.
    """
    has_verified = False
    has_uncertain = False

    for record in getattr(benchmark, "field_provenance", ()) or ():
        status = getattr(record, "evidence_status", None)
        if status == "verified":
            has_verified = True
        elif status == "uncertain":
            has_uncertain = True

    return has_verified, has_uncertain


def _provenance_vetoes(benchmark) -> bool:
    """True when any provenance vote for the record is excluded/unmatched."""
    for record in getattr(benchmark, "field_provenance", ()) or ():
        status = getattr(record, "evidence_status", None)
        if status in _VETO_STATUSES:
            return True
    return False


def quality_to_response_field(quality: dict) -> dict | None:
    """Shape the quality dict for the wire response.

    A vetoed (or otherwise None-score) result is reported as None so the API
    contract reads "this row has no computed quality" rather than shipping a
    made-up confidence.
    """
    if quality["score"] is None:
        return None
    return quality
