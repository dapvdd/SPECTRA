"""M3.2 final gate Task 2 — verified catalog contract vs the cumulative DB.

Points the app at data/dev/m32_cumulative.db (64 verified-published rows
across all four acquired categories) and exercises the real API:

- GET /hardware?verified=1 returns ALL eligible published+confirmed rows
  (64, four categories present, X-Total-Count matches).
- GET /hardware/facets?verified=1 counts reflect the same filter.
- Pagination, search (q), and type filtering stay consistent with the
  total under verified=1.
- Default (no verified param) still includes everything (64).
- Lifecycle honesty: a published+confirmed row is NOT proof that optional
  fields exist — the API must return whatever fields the row actually
  carries, never fabricate or overstate (checked by sampling rows and
  asserting spec payloads are exactly the published spec columns).

Run: python data/research/m32/verified_contract_check.py
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

DB = ROOT / "data/dev/m32_cumulative.db"
# The DATABASE_URL is read at import time: it MUST be set before any
# backend.app import touches backend.app.database.
os.environ["SPECTRA_DATABASE_URL"] = "sqlite:///" + str(DB).replace("\\", "/")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import main  # noqa: E402

CATEGORIES = ("RAM", "STORAGE", "MOTHERBOARD", "PSU")
SPEC_TABLES = {
    "RAM": "ram_specifications",
    "STORAGE": "storage_specifications",
    "MOTHERBOARD": "motherboard_specifications",
    "PSU": "psu_specifications",
}

results: list[dict] = []


def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (" — " + str(detail)[:160] if detail else ""))


def run_checks():
    conn = sqlite3.connect(DB)
    expected_verified = dict(conn.execute(
        "SELECT type, COUNT(*) FROM hardware "
        "WHERE record_status='PUBLISHED' AND identity_status='confirmed' "
        "GROUP BY type").fetchall())
    expected_total = conn.execute(
        "SELECT COUNT(*) FROM hardware WHERE record_status='PUBLISHED' "
        "AND identity_status='confirmed'").fetchone()[0]
    # Ground truth: which rows SHOULD have which spec fields
    truth = {}
    for cat, table in SPEC_TABLES.items():
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")
                if r[1] not in ("hardware_id", "id")]
        for row in conn.execute(
            f"SELECT h.id, h.name, {', '.join('s.' + c for c in cols)} "
            f"FROM hardware h JOIN {table} s ON s.hardware_id = h.id "
            f"WHERE h.type = ?", (cat,)
        ).fetchall():
            values = dict(zip(cols, row[2:]))
            truth[row[0]] = {
                "name": row[1], "category": cat,
                "populated": {k: v for k, v in values.items() if v is not None},
            }
    conn.close()

    client = TestClient(main.app)

    def fetch_all_verified(**extra):
        """Page through /hardware?verified=1 (limit cap is 200)."""
        out, offset = [], 0
        while True:
            resp = client.get("/hardware", params={
                "verified": 1, "limit": 200, "offset": offset, **extra})
            if resp.status_code != 200:
                return resp, out
            batch = resp.json()
            out.extend(batch)
            if len(batch) < 200 or offset + len(batch) >= int(
                    resp.headers.get("x-total-count", "0")):
                return resp, out
            offset += len(batch)

    # 1. All eligible records appear under verified=1
    r, items = fetch_all_verified()
    check("verified=1 returns 200", r.status_code == 200, r.status_code)
    items = r.json()
    check("verified=1 returns all eligible rows",
          len(items) == expected_total,
          f"got {len(items)}, expected {expected_total}")
    check("X-Total-Count matches", r.headers.get("x-total-count") == str(expected_total),
          r.headers.get("x-total-count"))

    # 2. All four categories represented
    by_type = {}
    for item in items:
        by_type[item["type"]] = by_type.get(item["type"], 0) + 1
    check("all four acquired categories present",
          all(by_type.get(c, 0) == expected_verified.get(c, 0) for c in CATEGORIES),
          {c: (by_type.get(c, 0), expected_verified.get(c, 0)) for c in CATEGORIES})

    # 3. Facets consistent
    rf = client.get("/hardware/facets", params={"verified": 1})
    check("facets verified=1 returns 200", rf.status_code == 200)
    facets = rf.json()
    facet_types = {f["value"]: f["count"] for f in facets["types"]}
    check("facet type counts match DB truth",
          all(facet_types.get(c, 0) == expected_verified.get(c, 0) for c in CATEGORIES),
          {c: (facet_types.get(c, 0), expected_verified.get(c, 0)) for c in CATEGORIES})
    facet_mfrs = {f["value"]: f["count"] for f in facets["manufacturers"]}
    check("facet manufacturer total == row total",
          sum(facet_mfrs.values()) == expected_total,
          f"{sum(facet_mfrs.values())} vs {expected_total}")

    # 4. Pagination consistency
    p1 = client.get("/hardware", params={"verified": 1, "limit": 10, "offset": 0})
    p2 = client.get("/hardware", params={"verified": 1, "limit": 10, "offset": 10})
    check("page 1 returns 10", len(p1.json()) == 10)
    check("page 2 returns 10", len(p2.json()) == 10)
    ids1 = {i["id"] for i in p1.json()}
    ids2 = {i["id"] for i in p2.json()}
    check("pages do not overlap", not (ids1 & ids2))
    check("X-Total-Count stays the full set under pagination",
          p1.headers.get("x-total-count") == str(expected_total),
          p1.headers.get("x-total-count"))

    # 5. Search consistency
    sq = client.get("/hardware", params={"verified": 1, "q": "corsair", "limit": 200})
    sq_items = sq.json()
    check("search 'corsair' returns only Corsair verified rows",
          all(i["manufacturer"] == "Corsair" for i in sq_items) and len(sq_items) > 0,
          f"{len(sq_items)} rows")
    sq2 = client.get("/hardware/facets", params={"verified": 1, "q": "corsair"})
    sq2_types = {f["value"]: f["count"] for f in sq2.json()["types"]}
    sq2_total = sum(sq2_types.values())
    check("facets under search match the row set", sq2_total == len(sq_items),
          f"{sq2_total} vs {len(sq_items)}")

    # 6. Type filter consistency
    for cat in CATEGORIES:
        rt_all = []
        offset = 0
        while True:
            rt = client.get("/hardware", params={
                "verified": 1, "type": cat, "limit": 200, "offset": offset})
            batch = rt.json()
            rt_all.extend(batch)
            if len(batch) < 200:
                break
            offset += len(batch)
        check(f"type={cat} returns exactly the verified count",
              len(rt_all) == expected_verified[cat]
              and rt.headers.get("x-total-count") == str(expected_verified[cat]),
              f"{len(rt_all)} vs {expected_verified[cat]}")

    # 7. Default behavior still returns the full cumulative catalog
    rd_all, rd_items = [], []
    offset = 0
    while True:
        resp = client.get("/hardware", params={"limit": 200, "offset": offset})
        batch = resp.json()
        rd_all.append(resp)
        rd_items.extend(batch)
        if len(batch) < 200:
            break
        offset += len(batch)
    rd = rd_all[0]
    check("no-verified default returns the same 64 rows (all are verified)",
          len(rd_items) == expected_total,
          f"{len(rd_items)} vs {expected_total}")

    # 8. Optional-field honesty: sample every row, spec payload must be
    # exactly what the DB carries — never fabricated, never overstated.
    conn = sqlite3.connect(DB)
    api_rows = {i["id"]: i for i in items}
    mismatches = []
    for hw_id, t in truth.items():
        api = api_rows.get(hw_id)
        if api is None:
            mismatches.append((hw_id, "missing from API"))
            continue
        # detail endpoint carries the spec block
        rdet = client.get(f"/hardware/{hw_id}")
        if rdet.status_code != 200:
            mismatches.append((hw_id, f"detail {rdet.status_code}"))
            continue
        spec = rdet.json().get("specifications") or {}
        populated = {k: v for k, v in spec.items() if v is not None}
        expected_keys = set(t["populated"].keys())
        got_keys = set(populated.keys())
        # The API may expose extra non-spec identity fields; every spec key
        # present must be one the DB publishes, and every DB spec key must
        # be present (missing optional field stays missing — never invented).
        if got_keys != expected_keys:
            mismatches.append((hw_id, {
                "category": t["category"],
                "missing": sorted(expected_keys - got_keys),
                "extra": sorted(got_keys - expected_keys),
            }))
    conn.close()
    check("spec payloads match DB truth exactly (no fabricated fields)",
          not mismatches, mismatches[:3])

    ok = all(r["ok"] for r in results)
    out = ROOT / "docs/m3/evidence/m32_verified_contract_checks.json"
    out.write_text(json.dumps({
        "database": "data/dev/m32_cumulative.db",
        "expected_total": expected_total,
        "expected_by_type": expected_verified,
        "checks": results,
        "all_passed": ok,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("WROTE", out)
    print("ALL PASSED" if ok else "FAILURES PRESENT")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    run_checks()
