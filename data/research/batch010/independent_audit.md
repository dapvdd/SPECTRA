# Batch 010 - Independent Audit

Date: 2026-10-10

## Database state
- Pre-mutation SHA-256: `c0e843edece6a2999cf8376a782f1602262b092a6cf5f32cb4bce1763d10c3ce`
- Post-mutation SHA-256: `20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127`
- Pre `PRAGMA quick_check`: ok
- Post `PRAGMA quick_check`: ok
- Post `PRAGMA foreign_key_check`: []

## Benchmark records
- Count before/after: 1040 / 1040
- Score/test-config changes: none
- Gaming benchmark rows: 0

## External identifiers
- Count before/after: 3575 / 3575
- Source associations changed (1 -> Intel ARK / AMD): 3575
- By type: {'product_id_tray': 620, 'product_id_mpk': 65, 'product_id_boxed': 215, 'intel_cpu_id': 2675}
- Identifier value/hardware changes: none
- Invalid source transitions: none
- Rows added/removed: 0 / 0

## Sources
- Unchanged (9 rows): True

## Provenance table
- Pre-existing spec rows preserved: 34809
- New provenance rows: 1040
- New rows by source: {2: 1040}
- New-row violations: none
- Benchmark provenance total: 1040
- Specification provenance total: 34809
- Orphan benchmark refs: 0
- Orphan hardware refs: 0
- Duplicate benchmark provenance: 0

### By source
- source 1: 546
- source 2: 1040
- source 3: 12884
- source 4: 2573
- source 5: 757
- source 6: 2
- source 7: 6
- source 8: 16276
- source 9: 1765
### By status
- excluded: 58
- unmatched: 4
- verified: 35787

## Evidence cross-check
- New rows matched to Geekbench reconciliation evidence: 1040/1040

## Verdict: PASS
