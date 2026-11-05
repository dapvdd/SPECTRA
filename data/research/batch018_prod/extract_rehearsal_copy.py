# -*- coding: utf-8 -*-
"""Consistency-safe extraction of a rehearsal copy of the production DB.

Runs INSIDE the spectra-backend container, piped via stdin:
    Get-Content extract_rehearsal_copy.py -Raw | ssh david-lab "docker exec -i spectra-backend python -"

- Reads /app/data/spectra.db (production DB) READ-ONLY via the SQLite backup API.
- Writes the consistent snapshot ONLY to container-local /tmp (NOT the
  spectra-sqlite-data volume, NOT the production DB itself).
- Prints the backup target path and its sha256 so the host can verify the copy.

Rationale: a raw filesystem copy of a live SQLite file is unsafe (WAL mode may
have unwritten pages). The SQLite online backup API produces a consistent
snapshot even while the DB is in use.
"""
import hashlib
import os
import sqlite3
import time

SRC = "/app/data/spectra.db"
DST = "/tmp/spectra_rehearsal_%s.db" % time.strftime("%Y%m%dT%H%M%S")

# --- 1. Consistency-safe backup via the SQLite online backup API
src = sqlite3.connect("file:%s?mode=ro" % SRC, uri=True)
dst = sqlite3.connect(DST)
src.backup(dst)
dst.close()
src.close()

# --- 2. Report source metadata + copy hash for host-side verification
def db_meta(path):
    c = sqlite3.connect("file:%s?mode=ro" % SRC)
    meta = {
        "journal_mode": c.execute("PRAGMA journal_mode").fetchone()[0],
        "page_size": c.execute("PRAGMA page_size").fetchone()[0],
        "page_count": c.execute("PRAGMA page_count").fetchone()[0],
        "schema_version": c.execute("PRAGMA schema_version").fetchone()[0],
    }
    c.close()
    return meta

h = hashlib.sha256()
with open(SRC, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
src_sha = h.hexdigest()

h = hashlib.sha256()
with open(DST, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
dst_sha = h.hexdigest()

print("src_path:", SRC)
print("dst_path:", DST)
print(json_dumps := repr(db_meta(SRC)))
print("src_sha256:", src_sha)
print("src_bytes:", os.path.getsize(SRC))
print("dst_sha256:", dst_sha)
print("dst_bytes:", os.path.getsize(DST))
print("quick_check:", dst_data := sqlite3.connect(DST).execute("PRAGMA quick_check").fetchone()[0])
