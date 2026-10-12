# Batch 014 — Mapping and Exclusions

## 1. Extraction method (deterministic, dependency-free)

Raw wikitext is fetched with `?action=raw` and parsed by
`data/research/batch014/wikitext_tables.py`, a small wikitext table parser
(`find_tables` → `parse_table` → `clean_cell`) that:

* splits tables on `{|` … `|}` and rows on `|-`;
* splits cells on `||` / `!!` and `|` / `!` per line, preserving merged-header rows;
* strips HTML comments, `<ref>`/`<refn>` footnotes, footnote templates
  (`efn`, `refn`, `note`, `ref`, `r`, `sfn`), `<br>` (→ space) and wiki markup.

`build_candidates.py` then maps 16 known table regions (by file and line offset) to
canonical records using only pure functions. It is deterministic: re-running it
produces the same inventory from the same sources. It classifies each candidate
against a reference database (`--db`), so the pre-apply proposal can be reproduced
from the backup.

Candidate inventory: **141 candidates, 0 collisions with the existing catalog**,
3 excluded rows.

## 2. Canonical naming

Names follow the conventions already present in the catalog so that no new naming
style is introduced and no existing record is renamed:

| Family | Canonical form | Example |
|---|---|---|
| Intel 14th-gen | `Intel Core iN-14xxx[F/K/KF/KS] Processor` | `Intel Core i9-14900K Processor` |
| Intel Core Ultra 1/2 | `Intel Core Ultra N NNN[V/H/U/HX] Processor` | `Intel Core Ultra 7 155H Processor` |
| AMD Ryzen (desktop/mobile) | `AMD Ryzen N NNNN[G/F/H/HX/X3D]` | `AMD Ryzen 9 9950X` |
| AMD Ryzen PRO | `AMD Ryzen N NNNN PRO …` / `AMD Ryzen AI N PRO NNN` | `AMD Ryzen AI 9 PRO 360` |
| AMD Ryzen AI 300 | `AMD Ryzen AI N [HX ]NNN` | `AMD Ryzen AI 9 HX 370` |

Model tokens are cleaned by dropping annotations introduced by `<br/>`
(e.g. a `9950X3D2` cell with a "Dual Edition" annotation → `9950X3D2`). `(PRO)`
annotations in the Ryzen AI table are resolved into a proper `PRO` position. Intel
names keep the ` Processor` suffix that the existing catalog uses for Intel parts.

## 3. Value semantics (source-supported only)

| Value | Rule applied |
|---|---|
| `boost_clock_ghz` | the table's **max boost / Turbo** column; never the base clock. With multiple turbo columns (P/E core) the **highest** published boost is taken. |
| `base_clock_ghz` | the table's **base** column. |
| `tdp_w` | the table's **default/base power** column (TDP/PBP). The **configurable** ceiling (MTP/PPT/configurable TDP range) is deliberately *not* stored, because the schema has a single `tdp_w` field. |
| `cores` / `threads` | for hybrid Intel parts, P-core and E-core counts are **summed** (e.g. Core Ultra 7 155H = 6 P + 8 E + 2 LP-E = 16 cores, 22 threads). |
| `release_date` | a **full launch date only**. Quarter windows (`Q4'23`), month-only and platform windows are ignored (NULL), and announcement vs retail launch is resolved in favour of the retail launch when both appear. |
| desktop vs mobile | kept distinct: mobile SKUs (H/U/HL/UL/V/HX) are only taken from mobile tables; desktop SKUs only from desktop tables. No SKU is duplicated across form factors. |

Every value must pass `valid_candidate()` sanity gates (1–128 cores, 1–256 threads,
0.5–6.5 GHz base, base ≤ boost ≤ 7.0 GHz, 5–500 W) or the row is dropped.

## 4. Architecture, process node and socket decisions

| Family | `architecture` | `process_node_nm` | `socket` |
|---|---|---|---|
| Intel 14th-gen | `Raptor Lake Refresh` | 10.0 | `FCLGA1700` |
| Intel Core Ultra (Meteor Lake) | `Meteor Lake` | NULL (multi-tile) | NULL (mobile) |
| Intel Core Ultra 200 (Arrow Lake) | `Arrow Lake` | NULL (multi-tile) | `FCLGA1851` for -S, NULL for U/H/HX |
| Intel Core Ultra 200V (Lunar Lake) | `Lunar Lake` | NULL (multi-tile) | NULL (mobile) |
| AMD Ryzen 9000 (desktop) | `Zen 5` | 4.0 | `AM5` |
| AMD Ryzen 8000G / 8000F | `Zen 4` | 4.0 | `AM5` |
| AMD Ryzen 8040 (mobile) | `Zen 4` | 4.0 | NULL (mobile) |
| AMD Ryzen 8045 (mobile HX) | `Zen 4` | 5.0 | NULL (mobile) |
| AMD Ryzen AI 300 (mobile) | `Zen 5` | 4.0 | NULL (mobile) |

Rationale:

* **Process node** is stored only where it is unambiguous. Intel Meteor Lake, Arrow
  Lake and Lunar Lake are multi-tile packages with no single process number, so
  `process_node_nm` is left NULL rather than choosing an arbitrary tile. Zen 4
  desktop APUs and Zen 4 mobile (8040) are 4 nm; the 8045 HX parts are the 5 nm
  variant; Zen 5 desktop and Ryzen AI 300 are 4 nm.
* **Socket** is stored only for docked desktop parts: LGA1700 (14th-gen), LGA1851
  (Arrow Lake-S), AM5 (Zen 4/5 desktop). Mobile parts have no single socket in the
  schema's sense and are left NULL.
* Architecture uses the platform/marketing codename convention already set by
  Batches 001/003.

Resulting coverage of the 141 new records: `architecture` 141, `cores/threads/base/
boost/tdp` 141 each, `release_date` 102, `process_node_nm` 76, `socket` 73.

## 5. Matching guard (no duplicates, no overwrites)

`apply_batch014.py` matches each candidate against the target DB by
`(lower(name), manufacturer, type='CPU')`. A candidate whose canonical name already
exists is skipped entirely, so:

* no existing hardware/spec row is updated, deleted or renamed;
* re-running the loader inserts nothing (idempotent);
* the catalog cannot acquire duplicate CPU names from this batch.

Field provenance is written with `INSERT OR IGNORE` behind the partial unique index
`uq_field_provenance_identity`, so re-applying the same evidence cannot duplicate
provenance rows.

## 6. Exclusions

| Category | Count | Reason |
|---|---:|---|
| Intel `Processor 300` / `300T` | 2 | not `Core`-branded; outside the modern Core/Ultra scope |
| Intel `Core 7 245HX` | 1 | non-`Ultra` Core 7 branding; did not match the Core Ultra convention |
| Arrow Lake "Plus" 2026 refresh | table | announcement/launch ambiguity; deferred to a future batch |
| AMD Ryzen 9000 mobile PRO / other PRO tables | tables | outside the requested target set |
| Intel ARK, AMD.com | source | unknown redistribution rights (Batch 009/010) |
| PassMark, TechPowerUp | source | restricted bulk redistribution |

The three excluded rows are recorded verbatim in `_candidates.json` under
`excluded`. Nothing is silently dropped: candidate rows that fail the naming or
validation gates are either excluded with a reason or never formed.

## 7. Reproducibility

```
# 1. rebuild the candidate inventory (use the pre-apply backup to reproduce the proposal)
python data/research/batch014/build_candidates.py \
    --db data/backups/spectra.db.batch014-20261012T053835Z.bak

# 2. dry-run, then apply (guarded, backup + single transaction, INSERT-only)
python data/research/batch014/apply_batch014.py --db data/spectra.db --expect 141
python data/research/batch014/apply_batch014.py --db data/spectra.db --apply --expect 141

# 3. independent audit
python data/research/batch014/audit_batch014.py \
    --db data/spectra.db \
    --before data/backups/spectra.db.batch014-20261012T053835Z.bak
```

Reruns are safe: step 1 reproduces the same rows, step 2 finds 0 to insert, step 3
still passes.
