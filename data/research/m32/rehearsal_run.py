"""M32 Task 6 — publication rehearsal to the isolated dev DB.

Mirrors the M3.1 rehearsal flow for the motherboard manifest:
1. clone the current-model baseline schema into data/dev/m32_acquisition.db,
2. upgrade v1..LATEST with the migration runner,
3. run_acquisition dry-run for the motherboard manifest (writes nothing),
4. apply the manifest (bounded batches, checkpointed),
5. re-run apply — idempotency: skipped_existing == published,
6. PRAGMA integrity_check + foreign_key_check,
7. write docs/m3/evidence/m32_run_log.json.

The rehearsal never touches data/spectra.db (publisher refuses it anyway).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.acquisition.pipeline import run_acquisition  # noqa: E402
from backend.app.migrations import runner as migration_runner  # noqa: E402
from backend.app.test_migration_runner import _clone_schema  # noqa: E402

M32 = ROOT / "data/research/m32"
DEV = ROOT / "data/dev/m32_acquisition.db"
EVIDENCE = ROOT / "docs/m3/evidence"
MANIFESTS = [M32 / "manifest_motherboard.json"]

log: dict = {
    "rehearsal": "m32 publication rehearsal",
    "database": "data/dev/m32_acquisition.db",
    "manifests": [p.name for p in MANIFESTS],
    "steps": [],
}


def step(name, **data):
    log["steps"].append({"step": name, **data})
    print(name, "->", json.dumps(data, default=str)[:220])


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    DEV.parent.mkdir(parents=True, exist_ok=True)
    if DEV.exists():
        DEV.unlink()
    # A stale checkpoint (from a previous rehearsal) makes the publisher
    # skip every batch on a freshly cloned DB: resume reports the batches
    # as completed without any row existing. The rehearsal starts clean.
    checkpoint = MANIFESTS[0].with_name(MANIFESTS[0].name + ".progress.json")
    if checkpoint.exists():
        checkpoint.unlink()
        step("checkpoint_reset", checkpoint=checkpoint.name)
    _clone_schema(DEV)
    up = migration_runner.upgrade(DEV)
    step("schema_clone_upgrade", status=up["status"],
         from_version=up.get("from_version"),
         to_version=up.get("to_version"),
         applied=[a["version"] for a in up.get("applied", [])])

    totals = {"dry_run_published": 0, "dry_run_rejected": 0,
              "published": 0, "skipped_existing": 0, "rejected": 0}
    for man in MANIFESTS:
        dry = run_acquisition(man, DEV, mode="dry-run")
        # Known pre-existing quirk (not an M3.2 regression): the dry-run
        # path never registers the acquisition source (that write happens
        # only on apply), so on a fresh DB every record reports "cites
        # unregistered source". Apply then registers the source and
        # publishes cleanly — the counts below stay the honest record.
        step("dry_run", manifest=man.name,
             unique_records=dry["unique_records"],
             would_publish=dry["published"],
             rejected=dry["rejected"],
             rejected_note=("unregistered-source rejections are expected "
                            "on a fresh DB; apply registers the source"),
             batches=dry["total_batches"])
        totals["dry_run_published"] += dry["published"]
        totals["dry_run_rejected"] += dry["rejected"]

        first = run_acquisition(man, DEV, mode="apply")
        step("apply", manifest=man.name, published=first["published"],
             skipped_existing=first["skipped_existing"],
             rejected=first["rejected"],
             quarantine=len(first["quarantined_conflicts"]))
        totals["published"] += first["published"]
        totals["rejected"] += first["rejected"]
        if first["rejected"]:
            step("apply_rejections", manifest=man.name,
                 reasons=first["rejection_reasons"][:10])

        second = run_acquisition(man, DEV, mode="apply")
        idem = (second["skipped_existing"] == first["published"]
                and second["published"] == 0)
        step("idempotent_rerun", manifest=man.name,
             published=second["published"],
             skipped_existing=second["skipped_existing"],
             idempotent=idem)
        if not idem:
            raise SystemExit(
                f"IDEMPOTENCY FAILURE on {man.name}: "
                f"{second['skipped_existing']} != {first['published']}")

    import sqlite3
    conn = sqlite3.connect(DEV)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk_viol = conn.execute("PRAGMA foreign_key_check").fetchall()
    hw = conn.execute("SELECT COUNT(*) FROM hardware").fetchone()[0]
    verified_hw = conn.execute(
        "SELECT COUNT(*) FROM hardware WHERE record_status='PUBLISHED' "
        "AND identity_status='confirmed'").fetchone()[0]
    prov = conn.execute(
        "SELECT COUNT(*) FROM field_provenance").fetchone()[0]
    conn.close()
    step("integrity", integrity_check=integrity,
         foreign_key_violations=len(fk_viol),
         hardware_rows=hw, verified_rows=verified_hw,
         provenance_rows=prov)
    if integrity != "ok" or fk_viol:
        raise SystemExit("INTEGRITY FAILURE")

    totals["hardware_rows"] = hw
    totals["verified_rows"] = verified_hw
    totals["provenance_rows"] = prov
    log["totals"] = totals
    out = EVIDENCE / "m32_run_log.json"
    out.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print("WROTE", out)


if __name__ == "__main__":
    main()
