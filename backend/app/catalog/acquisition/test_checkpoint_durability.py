"""M3.2 final gate Task 4 — database-aware checkpoint durability.

The manifest-keyed checkpoint limitation: a stale checkpoint (written for
database A) silently skips publication into a fresh or different database
B, because the checkpoint carries no database identity. The rehearsal
hazard was real: a resumed apply on a freshly cloned DB reported
skipped-without-rows.

Contract (additive, backward-compatible):
- ``load_progress(manifest_path)`` loads an old checkpoint unchanged
  (no ``db_fingerprint`` key) — resume of pre-existing checkpoints still
  works, but a fresh/different DB must not silently skip.
- ``run_acquisition`` fingerprints the target database at apply start
  (absolute path + hardware row count). When the checkpoint's stored
  fingerprint differs from the live database's, the checkpoint is
  discarded (stale) and all batches run — never silently skipped.
- Same database (path + row count unchanged): checkpoint resume works
  exactly as before (crash recovery contract preserved).
- Repeated publication on the same database stays idempotent.
"""
import json
import sqlite3

import pytest

from backend.app.catalog.acquisition.manifest import (
    new_manifest,
    save_manifest,
)
from backend.app.catalog.acquisition.pipeline import (
    load_progress,
    progress_path,
    run_acquisition,
    to_publisher_record,
)
from backend.app.catalog.acquisition.test_acquisition import (
    _candidate,
    _many_skus,
    _ram_sku,
    APPROVER,
)
from backend.app.test_migration_runner import _clone_schema
from backend.app.migrations import runner as migration_runner


def _fresh_db(tmp_path, name="pub.db"):
    target = tmp_path / name
    _clone_schema(target)
    migration_runner.upgrade(target)
    return target


class TestCheckpointFingerprint:
    def test_apply_stores_database_fingerprint(self, tmp_path):
        """After a successful apply, the checkpoint carries the database
        fingerprint so a later run can tell whether it still applies."""
        db = _fresh_db(tmp_path)
        manifest_path = tmp_path / "m.json"
        save_manifest(new_manifest([_ram_sku()], [_candidate()]), manifest_path)

        run_acquisition(manifest_path, db, mode="apply")

        progress = load_progress(manifest_path)
        assert progress["completed_batches"] == [0]
        fingerprint = progress.get("db_fingerprint")
        assert isinstance(fingerprint, dict)
        assert fingerprint["hardware_rows"] == 1
        # The path is normalized (casefolded, forward slashes) so the same
        # database reached through a different spelling still matches.
        assert fingerprint["path"].replace("\\", "/").endswith("pub.db")

    def test_stale_checkpoint_on_fresh_db_does_not_skip(self, tmp_path):
        """A checkpoint written for database A must not skip publication
        into a fresh database B: the fingerprint mismatches, the stale
        checkpoint is discarded, and every batch runs."""
        db_a = _fresh_db(tmp_path, "a.db")
        db_b = _fresh_db(tmp_path, "b.db")
        manifest_path = tmp_path / "m.json"
        save_manifest(new_manifest(_many_skus(12)), manifest_path)

        first = run_acquisition(manifest_path, db_a, mode="apply")
        assert first["published"] == 12

        # Same manifest, brand-new database: the checkpoint says "12 done"
        # but db_b has zero rows — the stale checkpoint must not skip.
        second = run_acquisition(manifest_path, db_b, mode="apply")
        assert second["published"] == 12, (
            "stale checkpoint silently skipped publication into a fresh DB"
        )
        conn = sqlite3.connect(db_b)
        total = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='RAM'").fetchone()[0]
        conn.close()
        assert total == 12

    def test_same_database_resume_still_works(self, tmp_path):
        """Crash recovery on the SAME database is preserved: a checkpoint
        whose fingerprint matches the live database still skips completed
        batches and publishes the remainder."""
        db = _fresh_db(tmp_path)
        manifest_path = tmp_path / "m.json"
        skus = _many_skus(30)  # batches: 10 + 20
        save_manifest(new_manifest(skus), manifest_path)

        # Simulate a crash after batch 0: publish it manually, then write
        # the checkpoint in the pre-Task-4 shape PLUS a fingerprint that
        # matches the live database (rows published so far).
        from backend.app.publishing.publisher import publish_batch
        from backend.app.catalog.acquisition.pipeline import (
            _ensure_source_registered,
            to_publisher_record,
        )

        _ensure_source_registered(db)
        first_batch = [to_publisher_record(s) for s in skus[:10]]
        result = publish_batch(db, first_batch, approved_by=APPROVER)
        assert result.published == 10

        from backend.app.catalog.acquisition.pipeline import (
            _database_fingerprint,
        )

        progress_path(manifest_path).write_text(json.dumps({
            "completed_batches": [0],
            "published_records": [r["canonical_key"] for r in first_batch],
            "db_fingerprint": _database_fingerprint(db),
        }), encoding="utf-8")

        summary = run_acquisition(manifest_path, db, mode="apply")
        statuses = [b["status"] for b in summary["batches"]]
        assert statuses[0] == "skipped_completed"
        assert summary["published"] == 20
        conn = sqlite3.connect(db)
        total = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='RAM'").fetchone()[0]
        conn.close()
        assert total == 30

    def test_legacy_checkpoint_without_fingerprint_on_fresh_db(self, tmp_path):
        """An old checkpoint (no fingerprint key) meeting a fresh database
        is treated as stale: publication runs instead of skipping."""
        db = _fresh_db(tmp_path)
        manifest_path = tmp_path / "m.json"
        save_manifest(new_manifest(_many_skus(12)), manifest_path)

        # Pre-seed a legacy-shape checkpoint (exactly the old schema).
        progress_path(manifest_path).write_text(json.dumps({
            "completed_batches": [0],
            "published_records": ["k0", "k1"],
        }), encoding="utf-8")

        summary = run_acquisition(manifest_path, db, mode="apply")
        assert summary["published"] == 12, (
            "legacy checkpoint without a fingerprint silently skipped "
            "publication into a fresh DB"
        )

    def test_legacy_checkpoint_without_fingerprint_on_matching_db_resumes(
        self, tmp_path,
    ):
        """A legacy checkpoint (no fingerprint key) is never trusted — the
        safe contract. On the SAME database the re-run is still safe: the
        publisher's canonical-key idempotency reports the already-published
        rows as skipped_existing and the row count never drifts."""
        db = _fresh_db(tmp_path)
        manifest_path = tmp_path / "m.json"
        skus = _many_skus(30)  # batches: 10 + 20
        save_manifest(new_manifest(skus), manifest_path)

        from backend.app.publishing.publisher import publish_batch
        from backend.app.catalog.acquisition.pipeline import (
            _ensure_source_registered,
            to_publisher_record,
        )

        _ensure_source_registered(db)
        first_batch = [to_publisher_record(s) for s in skus[:10]]
        result = publish_batch(db, first_batch, approved_by=APPROVER)
        assert result.published == 10

        # Legacy checkpoint (old shape, no fingerprint) as the crash left it.
        progress_path(manifest_path).write_text(json.dumps({
            "completed_batches": [0],
            "published_records": [r["canonical_key"] for r in first_batch],
        }), encoding="utf-8")

        summary = run_acquisition(manifest_path, db, mode="apply")
        # Reconciled legacy checkpoint: every named record exists in THIS
        # database, so crash recovery is preserved — batch 0 skipped, the
        # remainder published, rows never drift.
        statuses = [b["status"] for b in summary["batches"]]
        assert statuses[0] == "skipped_completed"
        assert summary["published"] == 20
        assert summary["skipped_existing"] == 10
        conn = sqlite3.connect(db)
        total = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='RAM'").fetchone()[0]
        conn.close()
        assert total == 30

    def test_interrupted_publication_then_repeat(self, tmp_path):
        """Interrupt (crash after batch 0 of 2), then run twice more on the
        same database: the first completes the remainder, the second is a
        no-op (idempotent), and the row count never drifts."""
        db = _fresh_db(tmp_path)
        manifest_path = tmp_path / "m.json"
        skus = _many_skus(30)
        save_manifest(new_manifest(skus), manifest_path)

        # Publish batch 0 through the real pipeline by interrupting: run
        # with a monkeypatched publish_batch that raises on batch 1.
        import backend.app.catalog.acquisition.pipeline as pipeline

        real_publish = pipeline.publish_batch
        calls = {"n": 0}

        def interrupting_publish(db_path, batch, **kwargs):
            if calls["n"] == 1:
                raise RuntimeError("simulated crash")
            calls["n"] += 1
            return real_publish(db_path, batch, **kwargs)

        pipeline.publish_batch = interrupting_publish
        try:
            with pytest.raises(RuntimeError, match="simulated crash"):
                run_acquisition(manifest_path, db, mode="apply")
        finally:
            pipeline.publish_batch = real_publish

        # Batch 0 committed; the checkpoint names only batch 0.
        progress = load_progress(manifest_path)
        assert progress["completed_batches"] == [0]

        # Resume: the remainder publishes.
        resumed = run_acquisition(manifest_path, db, mode="apply")
        assert resumed["published"] == 20

        # Repeat: fully idempotent.
        repeat = run_acquisition(manifest_path, db, mode="apply")
        assert repeat["published"] == 0
        assert repeat["skipped_existing"] == 30

        conn = sqlite3.connect(db)
        total = conn.execute(
            "SELECT COUNT(*) FROM hardware WHERE type='RAM'").fetchone()[0]
        conn.close()
        assert total == 30

    def test_fingerprint_ignores_row_count_drift_on_same_db(self, tmp_path):
        """The fingerprint's row-count component makes checkpoints written
        for a DIFFERENT data state of the same path stale as well: rows
        removed underneath a checkpoint must not cause silent skips."""
        db = _fresh_db(tmp_path)
        manifest_path = tmp_path / "m.json"
        save_manifest(new_manifest(_many_skus(12)), manifest_path)

        first = run_acquisition(manifest_path, db, mode="apply")
        assert first["published"] == 12

        # Wipe the rows (fresh copy of the same path). Spec tables carry a
        # UNIQUE hardware_id; SQLite rowid reuse would collide on republish,
        # so the wipe covers every category table as well.
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM hardware")
        conn.execute("DELETE FROM field_provenance")
        for table in ("ram_specifications", "storage_specifications",
                      "motherboard_specifications", "psu_specifications"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.close()

        again = run_acquisition(manifest_path, db, mode="apply")
        assert again["published"] == 12, (
            "checkpoint with a matching path but stale row count silently "
            "skipped publication"
        )
