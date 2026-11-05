"""Priority 2 safe identity resolution + Priority 3 candidate revalidation.

MATCHING: exact token-set intersection preserving model-digit anchors.
Multiple CSV candidates for one DB GPU with DIFFERENT TDP = quarantine.
Multiple CSV candidates with SAME TDP = ok (consistent evidence).
"""
import sys, json, re, csv, shutil, sqlite3, hashlib
from pathlib import Path
from collections import defaultdict

P = Path(__file__).resolve().parents[3]
DEV_DB   = P / "data" / "dev" / "spectra_dev.db"
CSV_PATH = P / "data" / "research" / "batch017" / "gpuark-gpu-specs.csv"
BASELINE = P / "data" / "dev" / "spectra_dev.baseline_rollback.db"
SCRATCH  = P / "data" / "dev" / "spectra_p3_scratch.db"
OUTPUT   = P / "data" / "dev" / "investigation_P3_revalidation.json"
sys.path.insert(0, str(P))

from backend.app.scripts import source_acquisition as sa
from backend.app.scripts import enrichment_pipeline as ep

def sha256(p): return hashlib.sha256(p.read_bytes()).hexdigest()

_MISSING = frozenset({"unknown","n/a","na","none","null","-","\u2014","\u2013"})

def is_sentinel(val):
    if val is None: return True
    return str(val).strip().lower() in _MISSING

def parse_gpu_name(name):
    """Return (vendor, series, model_digits) from a GPU name."""
    n = name.lower()
    vendor = next((v for v in ("nvidia","amd","intel","ati") if n.startswith(v)), "unknown")
    # strip vendor
    remainder = re.sub(r"^(nvidia|amd|intel|ati|msi|asus|gigabyte|sapphire|xfx|evga|zotac)\s+", "", n)
    # collect tokens + digit groups
    tokens = remainder.split()
    digits = [d for d in re.findall(r"\d+", remainder)]
    series = digits[0] if digits else ""
    return vendor, series, digits, remainder

def token_set(name):
    """All whitespace-separated tokens + digit groups for a GPU name."""
    n = name.lower()
    # strip vendor prefix
    n = re.sub(r"^(nvidia|amd|intel|ati|msi|asus|gigabyte|sapphire|xfx|evga|zotac)\s+", "", n)
    parts = n.split()
    tokens = set()
    for p in parts:
        tokens.add(p)
        tokens.update(re.findall(r"\d+", p))
    tokens.discard("")
    return frozenset(tokens)

def matches_csv_row(csv_name, db_name):
    """True if csv_name and db_name refer to the same GPU (conservative).

    Requires: DB token set is a subset of CSV token set (all DB tokens present
    in CSV), AND DB contributes at least one model-number digit.
    Preserves HD 5770 != HD 7970, GMA 600 != GMA 3600, Vega 48 != Vega 16.
    """
    db_tokens  = token_set(db_name)
    csv_tokens = token_set(csv_name)
    db_digits  = set(re.findall(r"\d+", db_name.lower()))
    # require all DB tokens present in CSV and at least one numeric anchor
    return db_tokens.issubset(csv_tokens) and bool(db_digits)

# Load adapter
adapter = sa.GpuArkAdapter.from_csv(str(CSV_PATH))
csv_valid = {}  # csv_name -> norm_tdp (non-None)
for row in adapter._rows:
    name = (row.get("name") or "").strip()
    raw  = (row.get("tdp") or "").strip()
    norm, _ = adapter.normalize_field_value("tdp_w", raw)
    if not name or norm is None:
        continue
    csv_valid[name] = norm

# Load DB GPUs
conn = sqlite3.connect(str(DEV_DB)); conn.execute("PRAGMA foreign_keys=ON")
db_rows = conn.execute(
    "SELECT h.id, h.name, h.segment, g.tdp_w FROM hardware h "
    "JOIN gpu_specifications g ON g.hardware_id = h.id WHERE h.type='GPU'"
).fetchall()
conn.close()

db_null = [r for r in db_rows if r[3] is None or r[3] == ""]
db_by_name = {r[1]: dict(id=r[0], seg=r[2] or "unknown", tdp=r[3]) for r in db_rows}

# For each NULL-TDP DB GPU, find all matching CSV rows
db_null_needing_enrich = []
for r in db_null:
    db_name, db_id, db_seg = r[1], r[0], r[2]
    candidates = []
    for csv_name, csv_tdp in csv_valid.items():
        if matches_csv_row(csv_name, db_name):
            candidates.append(dict(csv_name=csv_name, csv_tdp=csv_tdp))
    db_null_needing_enrich.append(dict(
        db_name=db_name, db_id=db_id, db_seg=db_seg,
        csv_candidates=candidates
    ))

# Classify candidates
safe_updates = []      # exactly 1 consistent candidate
quarantined  = []      # multiple candidates with conflicting TDP
unresolved   = []      # 0 candidates
for entry in db_null_needing_enrich:
    cands = entry["csv_candidates"]
    if len(cands) == 0:
        unresolved.append(entry)
    elif len(cands) == 1:
        safe_updates.append({**entry, "chosen_tdp": cands[0]["csv_tdp"],
                              "chosen_csv_name": cands[0]["csv_name"]})
    else:
        # multiple candidates: check if they agree on TDP
        tdps = {c["csv_tdp"] for c in cands}
        if len(tdps) > 1:
            quarantined.append({**entry, "conflicting_tdps": sorted(tdps)})
        else:
            # all agree on same TDP -> safe
            safe_updates.append({**entry, "chosen_tdp": cands[0]["csv_tdp"],
                                  "chosen_csv_name": cands[0]["csv_name"],
                                  "note": f"{len(cands)} candidates agree on {cands[0]['csv_tdp']}"})

stats = dict(
    db_null_tdp_count=len(db_null),
    csv_valid_rows=len(csv_valid),
    safe_updates=len(safe_updates),
    quarantined=len(quarantined),
    unresolved=len(unresolved),
    already_filled=len(db_rows) - len(db_null),
    demo_targets=[u["db_name"] for u in safe_updates[:5]],
)
print(json.dumps(stats, indent=2))

# Perform demo import on first 5 safe updates
demo = safe_updates[:5]
if demo:
    b_sha = sha256(BASELINE)
    if SCRATCH.exists(): SCRATCH.unlink()
    shutil.copyfile(BASELINE, SCRATCH)

    # Snapshot tdp BEFORE import for verification
    tdp_before = {}
    for m in demo:
        c = sqlite3.connect(str(SCRATCH)); c.execute("PRAGMA foreign_keys=ON")
        t = c.execute("SELECT tdp_w FROM gpu_specifications WHERE hardware_id=?", (m["db_id"],)).fetchone()[0]
        c.close()
        tdp_before[m["db_id"]] = t

    acq = [ep._reconstruct_acquisition(dict(
        source_name="GPU Ark", source_url="https://www.gpuark.com",
        license_status="clear", license_name="CC BY 4.0",
        source_reference="gpuark-gpu-specs.csv",
        hardware_name=m["db_name"], hardware_kind="GPU",
        field="tdp_w", raw_value=m["chosen_tdp"],
        normalized_value=m["chosen_tdp"], unit="W", confidence="high"
    )) for m in demo]

    val   = ep.validate_acquisitions(acq)
    first = ep.import_dev(str(SCRATCH), acq)
    second= ep.import_dev(str(SCRATCH), acq)

    # Verify AFTER import
    tdp_after = {}
    for m in demo:
        c = sqlite3.connect(str(SCRATCH)); c.execute("PRAGMA foreign_keys=ON")
        t = c.execute("SELECT tdp_w FROM gpu_specifications WHERE hardware_id=?", (m["db_id"],)).fetchone()[0]
        c.close()
        tdp_after[m["db_id"]] = t

    # Rollback
    shutil.copyfile(BASELINE, SCRATCH)
    rb_sha = sha256(SCRATCH)

    mutated = []
    for m in demo:
        before = tdp_before[m["db_id"]]
        after  = tdp_after[m["db_id"]]
        mutated.append(dict(
            db_name=m["db_name"], csv_tdp=m["chosen_tdp"],
            tdp_before=before, tdp_after=after,
            clean_write=(after == m["chosen_tdp"]),
            provenance_verified=before is None and after == m["chosen_tdp"]
        ))

    stats.update(dict(
        validation=val,
        first_applied=first["applied"], first_skipped=first["skipped"], first_rejected=first["rejected"],
        second_applied=second["applied"], idempotent=second["applied"]==0,
        rollback_verified=rb_sha==b_sha,
        baseline_sha=b_sha,
        mutated_records=mutated,
        safe_update_details=safe_updates,
        quarantined_details=quarantined,
        unresolved_details=[{"db_name":u["db_name"],"db_id":u["db_id"]} for u in unresolved],
    ))

OUTPUT.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
print("wrote", OUTPUT)
