"""M3 Phase 4 — record lifecycle (state machine, fail-closed).

Implements docs/m3/M3_DATA_CONTRACT.md §2.4: the publication lifecycle
DISCOVERED → EXTRACTED → NORMALIZED → VALIDATED → APPROVED → PUBLISHED with
terminal states QUARANTINED / REJECTED / SUPERSEDED.

Fail-closed guarantees (tested):
- no jump transitions (DISCOVERED cannot reach PUBLISHED or APPROVED);
- APPROVED requires a non-empty approver identity;
- terminal states are frozen (only SUPERSEDED may follow PUBLISHED);
- the publication gate is the explicit requirement checklist.
"""
from __future__ import annotations

DISCOVERED = "DISCOVERED"
EXTRACTED = "EXTRACTED"
NORMALIZED = "NORMALIZED"
VALIDATED = "VALIDATED"
APPROVED = "APPROVED"
PUBLISHED = "PUBLISHED"
QUARANTINED = "QUARANTINED"
REJECTED = "REJECTED"
SUPERSEDED = "SUPERSEDED"

_ACTIVE_STATES = (DISCOVERED, EXTRACTED, NORMALIZED, VALIDATED, APPROVED)

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    DISCOVERED: (EXTRACTED, QUARANTINED),
    EXTRACTED: (NORMALIZED, QUARANTINED, REJECTED),
    NORMALIZED: (VALIDATED, QUARANTINED, REJECTED),
    VALIDATED: (APPROVED, QUARANTINED, REJECTED),
    APPROVED: (PUBLISHED, QUARANTINED),
    PUBLISHED: (SUPERSEDED,),
    QUARANTINED: (),
    REJECTED: (),
    SUPERSEDED: (),
}

# Machine-checkable publication checklist (docs/m3/M3_DATA_CONTRACT.md §4;
# mission §6 Phase 4 bullet list).
PUBLICATION_REQUIREMENTS: tuple[str, ...] = (
    "valid_identity",
    "verifiable_source",
    "required_category_fields",
    "passing_validation",
    "no_blocking_conflict",
    "explicit_approval",
    "publication_batch",
)


class InvalidTransition(Exception):
    """A lifecycle transition that is not allowed."""


def allowed_transitions(state: str) -> tuple[str, ...]:
    return _TRANSITIONS.get(state, ())


def transition(
    state: str,
    next_state: str,
    *,
    approved_by: str | None = None,
) -> str:
    """Apply one lifecycle transition; returns the new state.

    Raises InvalidTransition for any disallowed move, including APPROVED
    without a non-empty ``approved_by`` identity.
    """
    allowed = allowed_transitions(state)
    if next_state not in allowed:
        raise InvalidTransition(
            f"invalid transition {state} -> {next_state} "
            f"(allowed: {allowed})"
        )
    if next_state == APPROVED:
        if not approved_by or not str(approved_by).strip():
            raise InvalidTransition(
                "transition to APPROVED requires a non-empty approved_by "
                "identity (explicit approval is mandatory)"
            )
    return next_state


def publication_allowed(requirements: dict[str, bool]) -> bool:
    """True only when every publication requirement is satisfied."""
    return all(bool(requirements.get(req)) for req in PUBLICATION_REQUIREMENTS)
