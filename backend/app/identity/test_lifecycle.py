"""M3 Phase 4 — record lifecycle tests (RED first).

Pins docs/m3/M3_DATA_CONTRACT.md §2.4:
- lifecycle states + allowed transitions (fail-closed)
- DISCOVERED cannot jump to PUBLISHED
- APPROVED requires explicit approver identity
- PUBLISHED requires: valid identity, verified evidence, critical fields,
  passing validation, no blocking conflict, approval, publication batch
- SUPERSEDED records keep superseded_by_id
"""
from __future__ import annotations

import pytest

from backend.app.identity.lifecycle import (
    APPROVED,
    DISCOVERED,
    EXTRACTED,
    NORMALIZED,
    PUBLISHED,
    QUARANTINED,
    REJECTED,
    SUPERSEDED,
    VALIDATED,
    InvalidTransition,
    PUBLICATION_REQUIREMENTS,
    allowed_transitions,
    transition,
)


class TestTransitions:
    def test_happy_path(self):
        state = DISCOVERED
        for next_state in (EXTRACTED, NORMALIZED, VALIDATED, APPROVED, PUBLISHED):
            state = transition(state, next_state, approved_by="curator")
        assert state == PUBLISHED

    def test_discovered_cannot_jump_to_published(self):
        with pytest.raises(InvalidTransition):
            transition(DISCOVERED, PUBLISHED, approved_by="curator")

    def test_discovered_cannot_jump_to_approved(self):
        with pytest.raises(InvalidTransition):
            transition(DISCOVERED, APPROVED, approved_by="curator")

    def test_approved_requires_approver(self):
        with pytest.raises(InvalidTransition):
            transition(VALIDATED, APPROVED, approved_by=None)
        with pytest.raises(InvalidTransition):
            transition(VALIDATED, APPROVED, approved_by="")

    def test_quarantine_from_any_active_state(self):
        for state in (DISCOVERED, EXTRACTED, NORMALIZED, VALIDATED, APPROVED):
            assert transition(state, QUARANTINED) == QUARANTINED

    def test_rejection_from_active_states(self):
        for state in (EXTRACTED, NORMALIZED, VALIDATED):
            assert transition(state, REJECTED) == REJECTED

    def test_terminal_states_are_frozen(self):
        for state in (PUBLISHED, QUARANTINED, REJECTED, SUPERSEDED):
            with pytest.raises(InvalidTransition):
                transition(state, DISCOVERED)

    def test_supersede_published(self):
        assert transition(PUBLISHED, SUPERSEDED) == SUPERSEDED

    def test_allowed_transitions_table(self):
        assert PUBLISHED not in allowed_transitions(DISCOVERED)
        assert PUBLISHED in allowed_transitions(APPROVED)
        assert allowed_transitions(PUBLISHED) == (SUPERSEDED,)


class TestPublicationRequirements:
    def test_requirements_documented(self):
        # The gate checklist is explicit and machine-checkable.
        assert set(PUBLICATION_REQUIREMENTS) == {
            "valid_identity",
            "verifiable_source",
            "required_category_fields",
            "passing_validation",
            "no_blocking_conflict",
            "explicit_approval",
            "publication_batch",
        }

    def test_publish_gate_requires_all(self):
        from backend.app.identity.lifecycle import publication_allowed

        full = {req: True for req in PUBLICATION_REQUIREMENTS}
        assert publication_allowed(full)

        for missing in PUBLICATION_REQUIREMENTS:
            partial = {req: True for req in PUBLICATION_REQUIREMENTS}
            partial[missing] = False
            assert not publication_allowed(partial)
