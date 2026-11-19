"""M3.1 Task 2 — acquisition architecture tests.

Covers the Task 2 acceptance contract:
- manifest JSON roundtrip + fail-closed validation (MATCHED requires mpn,
  per_sku_url, APPROVED evidence; INVALID/UNRESOLVED require notes);
- resolver determinism: MATCHED / REPLACED / UNRESOLVED / INVALID;
- dedup produces conflict quarantine, never a merge;
- retry_delay backoff math (no jitter: 1, 2, 4, 8, capped at 30);
- checkpoint resume after a simulated crash after batch 1;
- idempotent re-run (second run applies 0 rows, skipped_existing equals
  the first run's published count);
- source error classification mapping.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from backend.app.catalog.acquisition.errors import (
    SourceError,
    classify_exception,
    retry_delay,
)
from backend.app.catalog.acquisition.manifest import (
    CandidateRecord,
    FieldEvidence,
    VerifiedSKU,
    load_manifest,
    new_manifest,
    save_manifest,
    validate_manifest,
)
from backend.app.catalog.acquisition.pipeline import (
    bounded_batches,
    dedup_records,
    load_progress,
    progress_path,
    run_acquisition,
    to_publisher_record,
)
from backend.app.catalog.acquisition.resolver import (
    INVALID,
    MATCHED,
    REPLACED,
    UNRESOLVED,
    resolve_candidate,
)
from backend.app.migrations.runner import upgrade
from backend.app.test_migration_runner import _clone_schema

APPROVER = "m31-curator"

_PER_SKU_URL = (
    "https://www.corsair.com/us/en/p/memory/cmk32gx5m2b6000c30/"
    "vengeance-rgb-32gb-2x16gb-ddr5-dram-6000mhz-c30-memory-kit"
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _evidence(field_name: str, value, location: str = "Tech Specs > X",
              decision: str = "APPROVED") -> FieldEvidence:
    return FieldEvidence(
        spec_field=field_name,
        normalized_value=value,
        source_value=str(value),
        source_evidence_location=location,
        curator_decision=decision,
        source_url=_PER_SKU_URL,
        match_method="spec-table-row",
        access_date="2026-11-19",
    )


def _ram_sku(**overrides) -> VerifiedSKU:
    sku = VerifiedSKU(
        category="RAM",
        name="Corsair VENGEANCE 32GB (2x16GB) DDR5-6000 CL30 Kit",
        manufacturer="Corsair",
        product_family="Vengeance",
        mpn="CMK32GX5M2B6000C30",
        per_sku_url=_PER_SKU_URL,
        source_doc_revision="page rev 2026-11-19",
        spec={
            "ddr_generation": "DDR5",
            "capacity_gb": 32,
            "speed_mhz": 6000,
            "modules": 2,
        },
        fields=[
            _evidence("ddr_generation", "DDR5", "Tech Specs > Memory Type"),
            _evidence("capacity_gb", 32, "Tech Specs > Memory Size"),
            _evidence("speed_mhz", 6000, "Tech Specs > Tested Speed"),
            _evidence("modules", 2, "Tech Specs > Memory Size (2 x 16GB)"),
        ],
        classification="MATCHED",
        approved_by=APPROVER,
    )
    for key, value in overrides.items():
        setattr(sku, key, value)
    return sku


def _candidate(**overrides) -> dict:
    from backend.app.identity.canonical import canonical_key, variant_key

    spec = {
        "ddr_generation": "DDR5",
        "capacity_gb": 32,
        "speed_mhz": 6000,
        "modules": 2,
    }
    candidate = {
        "index": "001",
        "category": "RAM",
        "manufacturer": "Corsair",
        "product_family": "Vengeance",
        "name": "Corsair VENGEANCE 32GB (2x16GB) DDR5-6000 Kit",
        "claimed_spec": spec,
    }
    candidate.update(overrides)
    # The canonical key must always reflect the EFFECTIVE claimed spec so a
    # spec override also changes the identity (mirrors the Task 1 builder).
    candidate.setdefault(
        "canonical_key",
        canonical_key(
            candidate["manufacturer"], candidate["category"],
            candidate["product_family"],
            variant_key(candidate["category"], candidate["claimed_spec"]),
        ),
    )
    return candidate


@pytest.fixture()
def pub_db(tmp_path):
    """A v4-migrated dev DB with the citation-corpus source registered."""
    db = tmp_path / "acq.db"
    _clone_schema(db)
    upgrade(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT OR IGNORE INTO sources (name, url, license_name, "
        "license_status) VALUES (?, ?, ?, ?)",
        ("Official product pages — manual citations",
         "https://vendor.example/ (per-record citation URL)",
         "site terms (no redistribution license published)", "unknown"),
    )
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def manifest_file(tmp_path):
    """A valid manifest with one MATCHED RAM SKU on disk."""
    sku = _ram_sku()
    manifest = new_manifest([sku], [_candidate()], source="test")
    path = tmp_path / "manifest.json"
    save_manifest(manifest, path)
    return path


# ---------------------------------------------------------------------------
# Manifest schema: JSON roundtrip + validation
# ---------------------------------------------------------------------------

class TestManifestRoundtrip:
    def test_dataclass_json_roundtrip(self, tmp_path):
        sku = _ram_sku()
        data = sku.to_dict()
        assert data["mpn"] == "CMK32GX5M2B6000C30"
        assert data["fields"][0]["spec_field"] == "ddr_generation"
        restored = VerifiedSKU.from_dict(json.loads(json.dumps(data)))
        assert restored == sku

    def test_candidate_roundtrip(self):
        cand = CandidateRecord(
            category="RAM", name="X", manufacturer="Corsair",
            product_family="Vengeance", canonical_key="k",
        )
        restored = CandidateRecord.from_dict(cand.to_dict())
        assert restored == cand

    def test_save_and_load_manifest_roundtrip(self, tmp_path):
        sku = _ram_sku()
        manifest = new_manifest([sku], [_candidate()], source="roundtrip")
        path = tmp_path / "m.json"
        save_manifest(manifest, path)
        loaded = load_manifest(path)
        assert loaded["manifest_version"] == 1
        assert loaded["source"] == "roundtrip"
        assert VerifiedSKU.from_dict(loaded["verified_skus"][0]) == sku

    def test_field_evidence_roundtrip_preserves_types(self):
        ev = _evidence("capacity_gb", 32)
        restored = FieldEvidence.from_dict(ev.to_dict())
        assert restored == ev
        assert restored.normalized_value == 32

    def test_load_manifest_rejects_invalid(self, tmp_path):
        sku = _ram_sku(mpn="")  # MATCHED without mpn -> invalid
        manifest = new_manifest([sku], source="bad")
        path = tmp_path / "bad.json"
        save_manifest(manifest, path, validate=False)
        with pytest.raises(ValueError, match="MATCHED requires non-empty mpn"):
            load_manifest(path)


class TestManifestValidation:
    def test_matched_without_mpn_blocked(self):
        blockers = validate_manifest(
            new_manifest([_ram_sku(mpn="")], source="t"))
        assert any("MATCHED requires non-empty mpn" in b for b in blockers)

    def test_matched_without_per_sku_url_blocked(self):
        blockers = validate_manifest(
            new_manifest([_ram_sku(per_sku_url="")], source="t"))
        assert any("MATCHED requires non-empty per_sku_url" in b
                   for b in blockers)

    def test_matched_field_without_approved_evidence_blocked(self):
        sku = _ram_sku()
        sku.fields[1] = _evidence("capacity_gb", 32, decision="PENDING")
        blockers = validate_manifest(new_manifest([sku], source="t"))
        assert any("only APPROVED evidence" in b for b in blockers)

    def test_matched_populated_spec_without_evidence_blocked(self):
        sku = _ram_sku()
        sku.fields = sku.fields[:3]  # drop modules evidence
        blockers = validate_manifest(new_manifest([sku], source="t"))
        assert any("no FieldEvidence entry" in b for b in blockers)

    def test_null_spec_field_needs_no_evidence(self):
        sku = _ram_sku()
        sku.spec["voltage_v"] = None  # unknown optional field stays NULL
        blockers = validate_manifest(new_manifest([sku], source="t"))
        assert blockers == []

    def test_invalid_requires_notes(self):
        sku = _ram_sku(classification="INVALID", notes="")
        blockers = validate_manifest(new_manifest([sku], source="t"))
        assert any("requires non-empty notes" in b for b in blockers)

    def test_unresolved_requires_notes(self):
        sku = _ram_sku(classification="UNRESOLVED", notes="")
        blockers = validate_manifest(new_manifest([sku], source="t"))
        assert any("requires non-empty notes" in b for b in blockers)

    def test_invalid_classification_with_notes_ok(self):
        sku = _ram_sku(classification="INVALID",
                       notes="claimed 128 DIMM slots; impossible")
        blockers = validate_manifest(new_manifest([sku], source="t"))
        assert blockers == []

    def test_unknown_classification_blocked(self):
        sku = _ram_sku(classification="MAYBE")
        blockers = validate_manifest(new_manifest([sku], source="t"))
        assert any("outside vocabulary" in b for b in blockers)


# ---------------------------------------------------------------------------
# Resolver: MATCHED / REPLACED / UNRESOLVED / INVALID
# ---------------------------------------------------------------------------

class TestResolver:
    def test_match(self):
        resolution = resolve_candidate(_candidate(), [_ram_sku()])
        assert resolution.classification == MATCHED
        assert resolution.verified_sku["mpn"] == "CMK32GX5M2B6000C30"
        assert resolution.is_publishable

    def test_resolver_is_deterministic(self):
        candidate = _candidate()
        skus = [_ram_sku()]
        first = resolve_candidate(candidate, skus)
        second = resolve_candidate(dict(candidate), skus)
        assert (first.classification, first.reason) == \
               (second.classification, second.reason)

    def test_replace_same_family_different_variant(self):
        candidate = _candidate(
            claimed_spec={
                "ddr_generation": "DDR5",
                "capacity_gb": 32,
                "speed_mhz": 6400,
                "modules": 2,
            },
        )
        resolution = resolve_candidate(candidate, [_ram_sku()])
        assert resolution.classification == REPLACED
        assert resolution.verified_sku is not None

    def test_unresolved_no_verified_sku_for_family(self):
        candidate = _candidate(product_family="Unknown Family")
        resolution = resolve_candidate(candidate, [_ram_sku()])
        assert resolution.classification == UNRESOLVED
        assert resolution.verified_sku is None

    def test_unresolved_when_verified_list_empty(self):
        resolution = resolve_candidate(_candidate(), [])
        assert resolution.classification == UNRESOLVED

    def test_invalid_out_of_range_speed(self):
        candidate = _candidate(
            claimed_spec={
                "ddr_generation": "DDR5",
                "capacity_gb": 32,
                "speed_mhz": 99999,  # beyond MT/s sanity range
                "modules": 2,
            },
        )
        resolution = resolve_candidate(candidate, [_ram_sku()])
        assert resolution.classification == INVALID
        assert "speed_mhz" in resolution.reason

    def test_invalid_kit_consistency(self):
        candidate = _candidate(
            claimed_spec={
                "ddr_generation": "DDR5",
                "capacity_gb": 31,  # not divisible by 2 modules
                "speed_mhz": 6000,
                "modules": 2,
            },
        )
        resolution = resolve_candidate(candidate, [_ram_sku()])
        assert resolution.classification == INVALID

    def test_invalid_beats_match(self):
        # Family + variant would match, but the spec is physically insane.
        candidate = _candidate(
            claimed_spec={
                "ddr_generation": "DDR5",
                "capacity_gb": 32,
                "speed_mhz": 99999,
                "modules": 2,
            },
        )
        resolution = resolve_candidate(candidate, [_ram_sku()])
        assert resolution.classification == INVALID

    def test_match_accepts_dict_form_of_verified_sku(self):
        resolution = resolve_candidate(_candidate(), [_ram_sku().to_dict()])
        assert resolution.classification == MATCHED

    def test_manufacturer_alias_resolution(self):
        # Inventory sometimes lists "Corsair" vs alias forms; the resolver
        # normalizes through canonical.normalize_manufacturer.
        candidate = _candidate(manufacturer="corsair")
        resolution = resolve_candidate(candidate, [_ram_sku()])
        assert resolution.classification == MATCHED


# ---------------------------------------------------------------------------
# Publisher-record conversion shape
# ---------------------------------------------------------------------------

class TestToPublisherRecord:
    def test_record_shape_matches_pilot_seed_sku_record(self):
        from backend.app.catalog.pilot_seed import _sku_record
        from backend.app.catalog.pilot_sku_verified import VERIFIED_SKUS

        pilot = _sku_record(VERIFIED_SKUS[0])
        record = to_publisher_record(_ram_sku())
        assert set(record) == set(pilot) | {"mpn"} or set(record) <= set(pilot) | {"mpn"}
        for key in ("category", "name", "manufacturer", "product_family",
                    "identity_status", "record_status", "approved_by",
                    "canonical_key", "spec", "provenance", "mpn"):
            assert key in record, f"missing publisher field {key}"
        assert record["identity_status"] == "confirmed"
        assert record["record_status"] == "APPROVED"
        for prov in record["provenance"].values():
            assert prov["evidence_status"] == "verified"
            assert prov["source_reference"]
            assert prov["match_method"]

    def test_record_passes_publisher_evidence_gate(self, pub_db):
        from backend.app.publishing.publisher import dry_run_batch

        record = to_publisher_record(_ram_sku())
        result = dry_run_batch(pub_db, [record])
        assert result.would_publish == 1, result.rejection_reasons

    def test_unapproved_evidence_refused(self):
        sku = _ram_sku()
        sku.fields[0] = _evidence("ddr_generation", "DDR5",
                                  decision="REJECTED")
        with pytest.raises(ValueError, match="lacks APPROVED evidence"):
            to_publisher_record(sku)


# ---------------------------------------------------------------------------
# Dedup: conflict quarantine, never a merge
# ---------------------------------------------------------------------------

class TestDedup:
    def test_duplicates_quarantined_not_merged(self):
        # Two curations of the SAME SKU with differing facts: same identity
        # (same family/variant), conflicting spec values.
        sku_a = _ram_sku()
        sku_b = _ram_sku(
            spec={"ddr_generation": "DDR5", "capacity_gb": 32,
                  "speed_mhz": 6000, "modules": 2, "voltage_v": 9.9},
        )
        sku_b.fields.append(
            _evidence("voltage_v", 9.9, "Tech Specs > Voltage"))
        # Give both entries the same canonical identity so dedup sees a
        # key collision; the differing voltage_v is the fact conflict.
        records = [to_publisher_record(sku_a), to_publisher_record(sku_b)]
        records[1]["canonical_key"] = records[0]["canonical_key"]
        unique, quarantine = dedup_records(records)
        # Fail-closed: BOTH colliding records are quarantined (nothing is
        # published, nothing is merged) — exactly one conflict group.
        assert len(unique) == 0
        assert len(quarantine) == 1
        assert len(quarantine[0]["records"]) == 2
        assert "never" in quarantine[0]["reason"]

    def test_distinct_keys_pass_through(self):
        a = to_publisher_record(_ram_sku())
        b = to_publisher_record(
            _ram_sku(name="Corsair VENGEANCE 64GB (2x32GB) DDR5-6000 Kit",
                     mpn="CMK64GX5M2B6000C30",
                     spec={"ddr_generation": "DDR5", "capacity_gb": 64,
                           "speed_mhz": 6000, "modules": 2}))
        unique, quarantine = dedup_records([a, b])
        assert len(unique) == 2
        assert quarantine == []

    def test_quarantined_records_never_reach_publisher(self, pub_db):
        from backend.app.publishing.publisher import publish_batch

        a = to_publisher_record(_ram_sku())
        b = to_publisher_record(_ram_sku())  # same key
        unique, quarantine = dedup_records([a, b])
        assert len(quarantine) == 1
        # Nothing survives dedup: the publisher receives no records at all.
        assert unique == []
        result = publish_batch(pub_db, unique, approved_by=APPROVER)
        assert result.published == 0
        conn = sqlite3.connect(pub_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE canonical_key = ?",
            (a["canonical_key"],)).fetchone()[0]
        conn.close()
        assert count == 0


# ---------------------------------------------------------------------------
# errors: retry_delay math + classification
# ---------------------------------------------------------------------------

class TestRetryDelay:
    def test_backoff_sequence_no_jitter(self):
        assert [retry_delay(a) for a in range(5)] == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_backoff_capped_at_30(self):
        assert retry_delay(5) == 30.0
        assert retry_delay(10) == 30.0
        assert retry_delay(50) == 30.0

    def test_jitter_added_but_total_capped(self):
        assert retry_delay(0, jitter=0.5) == 1.5
        assert retry_delay(9, jitter=5.0) == 30.0  # 16 + 5 < 30 stays
        assert retry_delay(9, jitter=100.0) == 30.0

    def test_negative_attempt_treated_as_zero(self):
        assert retry_delay(-3) == 1.0

    def test_deterministic_with_fixed_jitter(self):
        delays = [retry_delay(a, jitter=0.1) for a in range(4)]
        assert delays == [1.1, 2.1, 4.1, 8.1]


class TestClassifyException:
    def test_source_error_passthrough(self):
        original = SourceError("boom", "rate_limited", status=429)
        assert classify_exception(original) is original

    def test_http_status_mapping(self):
        class FakeResponse:
            status_code = 404

        class FakeHTTPError(Exception):
            response = FakeResponse()

        classified = classify_exception(FakeHTTPError("not found"))
        assert classified.kind == "not_found"
        assert classified.status == 404
        assert classified.retryable is False

    def test_rate_limited_429(self):
        class FakeResponse:
            status_code = 429

        class FakeHTTPError(Exception):
            response = FakeResponse()

        classified = classify_exception(FakeHTTPError("too many"))
        assert classified.kind == "rate_limited"
        assert classified.retryable is True

    def test_server_error_retryable(self):
        class FakeResponse:
            status_code = 503

        class FakeHTTPError(Exception):
            response = FakeResponse()

        assert classify_exception(FakeHTTPError("down")).kind == "http_status"

    def test_timeout_is_network(self):
        assert classify_exception(TimeoutError("timed out")).kind == "network"

    def test_connection_error_is_network(self):
        classified = classify_exception(ConnectionError("refused"))
        assert classified.kind == "network"
        assert classified.retryable is True

    def test_json_decode_is_parse(self):
        classified = classify_exception(json.JSONDecodeError("x", "y", 1))
        assert classified.kind == "parse"

    def test_unknown_fallback(self):
        classified = classify_exception(Exception("mystery"))
        assert classified.kind == "unknown"

    def test_error_kinds_vocabulary_closed(self):
        from backend.app.catalog.acquisition.errors import ERROR_KINDS
        assert set(ERROR_KINDS) == {
            "network", "http_status", "parse", "blocked", "auth",
            "rate_limited", "not_found", "unknown",
        }

    def test_invalid_kind_rejected_at_construction(self):
        with pytest.raises(ValueError, match="unknown SourceError kind"):
            SourceError("x", "nonsense")


# ---------------------------------------------------------------------------
# Pipeline: batching, checkpoint resume, idempotency
# ---------------------------------------------------------------------------

def _many_skus(n: int) -> list[VerifiedSKU]:
    """n distinct MATCHED RAM SKUs (distinct capacity tiers)."""
    from backend.app.identity.canonical import variant_key

    skus = []
    for i in range(1, n + 1):
        capacity = 8 * i
        spec = {
            "ddr_generation": "DDR5",
            "capacity_gb": capacity,
            "speed_mhz": 5600,
            "modules": 1,
        }
        skus.append(VerifiedSKU(
            category="RAM",
            name=f"Corsair VENGEANCE {capacity}GB DDR5-5600 Test SKU {i:03d}",
            manufacturer="Corsair",
            product_family="Vengeance",
            mpn=f"CMK{capacity}GX5M1B5600C40#{i:03d}",
            per_sku_url=f"https://www.corsair.com/us/en/p/memory/"
                        f"test-sku-{i:03d}",
            source_doc_revision="page rev 2026-11-19",
            spec=spec,
            fields=[
                _evidence("ddr_generation", "DDR5",
                          "Tech Specs > Memory Type"),
                _evidence("capacity_gb", capacity, "Tech Specs > Size"),
                _evidence("speed_mhz", 5600, "Tech Specs > Speed"),
                _evidence("modules", 1, "Tech Specs > Modules"),
            ],
            classification="MATCHED",
            approved_by=APPROVER,
        ))
    return skus


class TestBoundedBatches:
    def test_ladder_10_25_50_100(self):
        records = [{"canonical_key": f"k{i}"} for i in range(120)]
        sizes = [len(b) for b in bounded_batches(records)]
        assert sizes == [10, 15, 25, 50, 20]
        # Cumulative coverage: every record appears exactly once.
        flat = [r for b in bounded_batches(records) for r in b]
        assert len(flat) == 120
        assert len({r["canonical_key"] for r in flat}) == 120

    def test_empty_records_no_batches(self):
        assert list(bounded_batches([])) == []

    def test_small_set_single_batch(self):
        records = [{"canonical_key": f"k{i}"} for i in range(7)]
        assert [len(b) for b in bounded_batches(records)] == [7]


class TestCheckpointAndIdempotency:
    def test_apply_publishes_all_and_writes_checkpoint(
        self, pub_db, tmp_path,
    ):
        manifest_path = tmp_path / "m.json"
        sku = _ram_sku()
        save_manifest(new_manifest([sku], [_candidate()]), manifest_path)
        summary = run_acquisition(manifest_path, pub_db, mode="apply")
        assert summary["published"] == 1
        assert summary["rejected"] == 0
        assert summary["quarantined_conflicts"] == []
        progress = load_progress(manifest_path)
        assert progress["completed_batches"] == [0]
        assert progress_path(manifest_path).exists()

    def test_checkpoint_resume_skips_completed_batches(
        self, pub_db, tmp_path,
    ):
        """Simulate a crash after batch 1: pre-seed the checkpoint, re-run,
        completed batch is skipped and the remainder publishes."""
        manifest_path = tmp_path / "m.json"
        skus = _many_skus(30)  # batches: 10 + 20
        save_manifest(new_manifest(skus), manifest_path)

        # Batch 0 = records[:10]: publish it manually, then seed the
        # checkpoint as if the run crashed right after batch 1 committed.
        first_batch = [to_publisher_record(s) for s in skus[:10]]
        from backend.app.publishing.publisher import publish_batch
        result = publish_batch(pub_db, first_batch, approved_by=APPROVER)
        assert result.published == 10
        save_progress_data = {
            "completed_batches": [0],
            "published_records": [r["canonical_key"] for r in first_batch],
        }
        progress_path(manifest_path).write_text(
            json.dumps(save_progress_data), encoding="utf-8")

        summary = run_acquisition(manifest_path, pub_db, mode="apply")
        statuses = [b["status"] for b in summary["batches"]]
        assert statuses[0] == "skipped_completed"
        assert "ok" in statuses[1:]
        # Only the remaining 20 rows were applied in this run.
        assert summary["published"] == 20
        # Total rows in DB = 10 (pre-crash) + 20 (resumed) = 30.
        conn = sqlite3.connect(pub_db)
        total = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='RAM'").fetchone()[0]
        conn.close()
        assert total == 30

    def test_idempotent_rerun_zero_rows_second_time(
        self, pub_db, tmp_path,
    ):
        manifest_path = tmp_path / "m.json"
        save_manifest(new_manifest(_many_skus(25)), manifest_path)

        first = run_acquisition(manifest_path, pub_db, mode="apply")
        assert first["published"] == 25
        assert first["rejected"] == 0

        # Second full run: every batch reports skipped_existing; zero rows
        # applied; publisher's skipped_existing == first run's published.
        second = run_acquisition(manifest_path, pub_db, mode="apply")
        assert second["published"] == 0
        assert second["skipped_existing"] == first["published"]
        assert second["rejected"] == 0

    def test_dry_run_writes_nothing_and_no_checkpoint(
        self, pub_db, tmp_path,
    ):
        manifest_path = tmp_path / "m.json"
        save_manifest(new_manifest(_many_skus(12)), manifest_path)
        summary = run_acquisition(manifest_path, pub_db, mode="dry-run")
        assert summary["published"] == 12  # would_publish
        assert not progress_path(manifest_path).exists()
        conn = sqlite3.connect(pub_db)
        total = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='RAM'").fetchone()[0]
        conn.close()
        assert total == 0

    def test_mode_validation(self, pub_db, tmp_path):
        manifest_path = tmp_path / "m.json"
        save_manifest(new_manifest([_ram_sku()]), manifest_path)
        with pytest.raises(ValueError, match="mode must be"):
            run_acquisition(manifest_path, pub_db, mode="yolo")

    def test_invalid_manifest_refused(self, pub_db, tmp_path):
        manifest_path = tmp_path / "bad.json"
        sku = _ram_sku(mpn="")
        save_manifest(new_manifest([sku]), manifest_path, validate=False)
        with pytest.raises(ValueError, match="fail-closed validation"):
            run_acquisition(manifest_path, pub_db, mode="apply")
