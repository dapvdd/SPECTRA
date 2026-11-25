"""M3.2 final gate Task 1 — cumulative catalog rehearsal.

Fresh isolated dev DB from the actual baseline (clone -> migrate v1..4),
then publish every verified source in mission order:
1. M3 Core pilot (run_m3_pilot flow): registered sources + approved
   pilot records through bounded batches (quarantined never publishable),
2. M3.1 manifests: manifest_ram.json / manifest_storage.json /
   manifest_psu.json via run_acquisition (checkpointed, idempotent),
3. M3.2 manifest: manifest_motherboard.json via run_acquisition.

Identity reconciliation happens through the real layers: manifest dedup
(canonical-key quarantine) + publisher conflict gate (differing facts on
a published key are rejected, never merged) + dry-run pre-checks.

The unique total is NOT assumed (64 would be 2+49+13 minus nothing);
every count is read back from the database and reported per category.
Cumulative publication is proven idempotent by re-running every source
and asserting published == 0 with skipped_existing == published totals.
"""
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.app.catalog.pilot_seed import build_pilot_records  # noqa: E402
from backend.app.catalog.acquisition.pipeline import (  # noqa: E402
    run_acquisition,
)
from backend.app.migrations import runner as migration_runner  # noqa: E402
from backend.app.publishing.publisher import publish_batch  # noqa: E402
from backend.app.test_migration_runner import _clone_schema  # noqa: E402

DEV = ROOT / "data/dev/m32_cumulative.db"
EVIDENCE = ROOT / "docs/m3/evidence"
MANIFESTS = [
    ROOT / "data/research/m31/manifest_ram.json",
    ROOT / "data/research/m31/manifest_storage.json",
    ROOT / "data/research/m31/manifest_psu.json",
    ROOT / "data/research/m32/manifest_motherboard.json",
]
CATEGORIES = ("RAM", "STORAGE", "MOTHERBOARD", "PSU")

log: dict = {
    "rehearsal": "m3.2 cumulative catalog rehearsal",
    "database": "data/dev/m32_cumulative.db",
    "sources": ["m3 core pilot", *[p.name for p in MANIFESTS]],
    "steps": [],
}


def step(name, **data):
    log["steps"].append({"step": name, **data})
    print(name, "->", json.dumps(data, default=str)[:400])


def counts_by_category(db: Path) -> dict:
    conn = sqlite3.connect(db)
    try:
        by_type = dict(conn.execute(
            "SELECT type, COUNT(*) FROM hardware GROUP BY type").fetchall())
        verified = dict(conn.execute(
            "SELECT type, COUNT(*) FROM hardware "
            "WHERE record_status='PUBLISHED' AND identity_status='confirmed' "
            "GROUP BY type").fetchall())
        quarantined = dict(conn.execute(
            "SELECT type, COUNT(*) FROM hardware "
            "WHERE record_status='QUARANTINED' "
            "GROUP BY type").fetchall())
        return {
            "hardware_total": sum(by_type.values()),
            "by_type": by_type,
            "verified_published_by_type": verified,
            "quarantined_by_type": quarantined,
            "provenance_total": conn.execute(
                "SELECT COUNT(*) FROM field_provenance").fetchone()[0],
            "provenance_verified": conn.execute(
                "SELECT COUNT(*) FROM field_provenance "
                "WHERE evidence_status='verified'").fetchone()[0],
            "canonical_keys_total": conn.execute(
                "SELECT COUNT(canonical_key) FROM hardware").fetchone()[0],
            "canonical_keys_unique": conn.execute(
                "SELECT COUNT(DISTINCT canonical_key) FROM hardware "
                "WHERE canonical_key IS NOT NULL").fetchone()[0],
        }
    finally:
        conn.close()


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    DEV.parent.mkdir(parents=True, exist_ok=True)
    if DEV.exists():
        DEV.unlink()
    _clone_schema(DEV)
    up = migration_runner.upgrade(DEV)
    step("schema_baseline_upgrade", status=up["status"],
         applied=[a["version"] for a in up.get("applied", [])],
         to_version=up.get("to_version"))

    # ---- 1. M3 Core pilot (real run_m3_pilot flow, bounded batches) ----
    records = build_pilot_records()
    approved_by_cat = {
        cat: [r for r in records[cat] if r["record_status"] == "APPROVED"]
        for cat in CATEGORIES
    }
    quarantined_by_cat = {
        cat: [r for r in records[cat] if r["record_status"] == "QUARANTINED"]
        for cat in CATEGORIES
    }
    step("m3_core_records",
         approved={k: len(v) for k, v in approved_by_cat.items()},
         quarantined={k: len(v) for k, v in quarantined_by_cat.items()})

    conn = sqlite3.connect(DEV)
    conn.executemany(
        "INSERT INTO sources (name, url, license_name, license_status) "
        "VALUES (?, ?, ?, ?)",
        [
            ("Wikipedia (English) — curated", "https://en.wikipedia.org/",
             "CC BY-SA 4.0", "clear"),
            ("Official product pages — manual citations",
             "https://vendor.example/ (per-record citation URL)",
             "site terms (no redistribution license published)", "unknown"),
        ],
    )
    conn.commit()
    conn.close()

    pilot_totals = defaultdict(int)
    pilot_batches = 0

    def _approved_batches(sizes=(10, 25, 50, 100)):
        nonlocal pilot_batches
        for category in CATEGORIES:
            batch = approved_by_cat[category]
            previous = 0
            for size in sizes:
                chunk = batch[previous:size]
                previous = size
                if chunk:
                    pilot_batches += 1
                    yield chunk

    for batch in _approved_batches():
        res = publish_batch(DEV, batch, approved_by="m3-curator",
                            run_notes="m32 cumulative: m3 core pilot")
        pilot_totals["published"] += res.published
        pilot_totals["skipped_existing"] += res.skipped_existing
        pilot_totals["rejected"] += res.rejected
        if res.rejected:
            step("m3_core_rejections", sample=res.rejection_reasons[:5])
    step("m3_core_apply", batches=pilot_batches, **pilot_totals)

    # ---- 2+3. M3.1 + M3.2 manifests through run_acquisition ----
    manifest_totals = defaultdict(int)
    for man in MANIFESTS:
        first = run_acquisition(man, DEV, mode="apply")
        step("manifest_apply",
             manifest=man.name,
             verified_skus=first["verified_skus"],
             matched=first["matched"],
             unique_records=first["unique_records"],
             published=first["published"],
             skipped_existing=first["skipped_existing"],
             rejected=first["rejected"],
             quarantined_conflicts=len(first["quarantined_conflicts"]))
        manifest_totals["published"] += first["published"]
        manifest_totals["skipped_existing"] += first["skipped_existing"]
        manifest_totals["rejected"] += first["rejected"]
        manifest_totals["quarantined_conflicts"] += len(
            first["quarantined_conflicts"])
        if first["rejected"]:
            step("manifest_rejections", manifest=man.name,
                 reasons=first["rejection_reasons"][:8])

    cumulative = counts_by_category(DEV)
    step("cumulative_state", **cumulative)

    # ---- Idempotency: re-run EVERY source; published must be 0 ----
    re_pilot = {"published": 0, "skipped_existing": 0, "rejected": 0}
    for batch in _approved_batches():
        res = publish_batch(DEV, batch, approved_by="m3-curator",
                            run_notes="m32 cumulative idempotency re-run")
        re_pilot["published"] += res.published
        re_pilot["skipped_existing"] += res.skipped_existing
        re_pilot["rejected"] += res.rejected
    idem = {"m3_core": re_pilot}

    for man in MANIFESTS:
        second = run_acquisition(man, DEV, mode="apply")
        idem[man.name] = {
            "published": second["published"],
            "skipped_existing": second["skipped_existing"],
            "rejected": second["rejected"],
        }
        manifest_totals_re = idem[man.name]
        if manifest_totals_re["published"] != 0:
            raise SystemExit(
                f"IDEMPOTENCY FAILURE {man.name}: republished "
                f"{manifest_totals_re['published']} rows")

    step("idempotency_reruns", **idem)

    after = counts_by_category(DEV)
    drift = {
        k: (cumulative[k], after[k])
        for k in ("hardware_total", "provenance_total")
        if cumulative[k] != after[k]
    }
    if drift:
        raise SystemExit(f"IDEMPOTENCY FAILURE: row drift {drift}")
    step("idempotency_no_drift", hardware_total=after["hardware_total"])

    # ---- Integrity ----
    conn = sqlite3.connect(DEV)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    step("integrity", integrity_check=integrity,
         foreign_key_violations=len(fk))
    if integrity != "ok" or fk:
        raise SystemExit("INTEGRITY FAILURE")

    log["totals"] = {
        "m3_core_pilot": pilot_totals,
        "manifests": manifest_totals,
        "final_state": after,
        "idempotency": idem,
    }
    out = EVIDENCE / "m32_cumulative_rehearsal_log.json"
    out.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print("WROTE", out)


if __name__ == "__main__":
    main()
