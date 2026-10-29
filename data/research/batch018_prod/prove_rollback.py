# -*- coding: utf-8 -*-
"""Rollback proof on the rehearsal copy.

Demonstrates the production rollback procedure safely on a rehearsal DB:
1. There is a pre-apply baseline snapshot (the rehearsal copy created by
   extract_rehearsal_copy.py, hash a82529ec...) sitting in /tmp.
2. We restore that baseline over an applied rehearsal DB and confirm the
   restored hash equals the baseline hash => rollback is exact and reversible.

This proves the restore/rollback path BEFORE it is ever needed in production.
Run inside the container with the baseline path and applied path as argv.
"""
import hashlib
import shutil
import sqlite3
import sys

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

baseline = sys.argv[1]   # pre-apply snapshot (extract output)
applied = sys.argv[2]    # the DB that we applied batch018 to

base_before = sha256_file(baseline)
applied_before = sha256_file(applied)
print("baseline (pre-apply) sha256:", base_before)
print("applied    sha256:", applied_before)
print("applied quick_check before restore:",
      sqlite3.connect(applied).execute("PRAGMA quick_check").fetchone()[0])
print("applied batch18 prov rows before restore:",
      sqlite3.connect(applied).execute(
          "SELECT COUNT(*) FROM field_provenance WHERE batch_no=18").fetchone()[0])

# Simulate rollback: copy baseline over applied
shutil.copy2(baseline, applied)

base_after = sha256_file(baseline)
restored = sha256_file(applied)
qc = sqlite3.connect(applied).execute("PRAGMA quick_check").fetchone()[0]
prov = sqlite3.connect(applied).execute(
    "SELECT COUNT(*) FROM field_provenance WHERE batch_no=18").fetchone()[0]
print("\n--- after simulated rollback ---")
print("baseline sha256 (unchanged):", base_after)
print("restored    sha256:", restored)
print("restored quick_check:", qc)
print("restored batch18 prov rows:", prov)
print("rollback exact (hash match):", restored == base_before)
# pre-apply provenance check on restored
restored_batch18 = sqlite3.connect(applied).execute(
    "SELECT COUNT(*) FROM field_provenance WHERE batch_no=18").fetchone()[0]
print("rollback removed all batch18 provenance (0 expected):", restored_batch18 == 0)
