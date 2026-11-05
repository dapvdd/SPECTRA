# -*- coding: utf-8 -*-
"""Generate a self-contained production NULL-guard checker with the 965
batch018 records embedded as a Python literal.

Usage:
  python emit_nullguard_checker.py > verify_prod_nullguard_selfcontained.py
Then pipe:
  Get-Content verify_prod_nullguard_selfcontained.py -Raw | ssh david-lab \
    "docker exec -i spectra-backend python -"
"""
import json

records = json.load(open("data/research/batch017/batch018_valid_records.json", encoding="utf-8"))

L = []
A = L.append
A('# -*- coding: utf-8 -*-')
A('"""READ-ONLY production NULL-guard check (Batch 018). Piped via stdin."""')
A('import sqlite3, hashlib, os')
A("RECORDS = %s" % json.dumps(records))
A('con = sqlite3.connect("/app/data/spectra.db")')
A('con.row_factory = sqlite3.Row')
A('print("candidate records:", len(RECORDS))')
A('violations = []; n_iface = 0; n_bw = 0')
A('for r in RECORDS:')
A('    hwid = r["hardware_id"]; field = r["field"]')
A('    row = con.execute("SELECT %s FROM gpu_specifications WHERE hardware_id=?" % field, (hwid,)).fetchone()')
A('    existing = row[0] if row else None')
A('    if existing is not None:')
A('        violations.append((hwid, field, existing, r.get("name")))')
A('    elif field == "interface":')
A('        n_iface += 1')
A('    elif field == "memory_bus_width_bits":')
A('        n_bw += 1')
A('print("interface NULL-in-prod (safe):", n_iface)')
A('print("bus_width NULL-in-prod (safe):", n_bw)')
A('print("already-populated conflicts:", len(violations))')
A('for v in violations[:20]:')
A('    print("  CONFLICT", v)')
A('qc = con.execute("PRAGMA quick_check").fetchone()[0]')
A('print("quick_check:", qc)')
A('con.close()')
A('h = hashlib.sha256()')
A('with open("/app/data/spectra.db", "rb") as f:')
A('    for chunk in iter(lambda: f.read(1 << 20), b""):')
A('        h.update(chunk)')
A('print("prod DB sha256:", h.hexdigest())')
A('print("prod DB bytes:", os.path.getsize("/app/data/spectra.db"))')

out_path = "data/research/batch017/verify_prod_nullguard_selfcontained.py"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
    f.write("\n")
print("wrote", out_path, len(records), "embedded records")
