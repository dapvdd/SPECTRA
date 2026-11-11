# M2 Baseline Audit — Build Planner Compatibility Engine

Tanggal: 2026-11-11 · Branch: `feat/build-planner-m2-compatibility` · Base: `92931d9` (origin/main, M1 ter-merge)

## 0. Verifikasi repositori

- `origin/main` = `92931d9` ✓ (M1 ter-merge, diverifikasi `ls-remote`)
- Worktree baru `.worktrees/build-planner-m2`, clean tree
- Baseline hijau: backend 1166 passed / 2 skipped / 2 deselected; frontend 637 pass; vite build OK
- Dev DB disalin ke worktree (data/spectra.db 51MB + data/dev/spectra_dev.db) — tidak ter-track git

## 1. Skema aktual (PRAGMA, dari DB nyata)

### cpu_specifications
`id, hardware_id, cores, threads, base_clock_ghz, boost_clock_ghz, tdp_w, process_node_nm, socket VARCHAR(50)`

- Data nyata: `socket` terisi untuk mayoritas CPU. Nilai umum: `FCLGA1151 (172), AM4 (152), FCLGA3647 (134), FCLGA2011 (115), FCLGA1150 (113), FCLGA1200 (110), FCLGA1700 (108), FCLGA2011-3 (94)`.
- **Tidak ada kolom BIOS/platform support.** → aturan BIOS = selalu UNKNOWN (kecuali data M3).

### gpu_specifications
`id, hardware_id, memory_gb, memory_type, core_clock_mhz, boost_clock_mhz, vram_bandwidth_gbps, tdp_w, interface VARCHAR(50), length_mm, memory_bus_width_bits`

- `interface` data nyata: `PCIe 1.0/2.0/3.0/4.0 x16, PCIe 3.0 x8, PCIe 4.0 x8, PCIe 4.0 x4, Apple MPX`.
- **Tidak ada kolom power connector (8-pin/12VHPWR).** → aturan konektor PSU↔GPU hanya bisa UNKNOWN di sisi GPU. (psu_specifications punya `pcie_8pin_count`, `pcie_12vhpwr` — sisi PSU ada, sisi GPU tidak.)

### hardware
`id, name, manufacturer, type, release_date, architecture, segment` — `type` bebas (VARCHAR 50), API memvalidasi 6 nilai (CATALOG_TYPES).

### Tabel baru M1 (kosong di produksi, terisi di preview M1)
- `ram_specifications`: `id, hardware_id UNIQUE, ddr_generation CHECK(DDR3|DDR4|DDR5|DDR6), capacity_gb, speed_mhz, modules, ecc, voltage_v, form_factor`
- `storage_specifications`: `id, hardware_id UNIQUE, storage_type CHECK(NVMe|SATA SSD|HDD), capacity_gb, interface VARCHAR(40), read_mb_s, write_mb_s, dram_cache, form_factor`
- `motherboard_specifications`: `id, hardware_id UNIQUE, socket, chipset, form_factor, ram_type VARCHAR(10), ram_slots, max_ram_gb, m2_slots, sata_ports, pcie_slots`
- `psu_specifications`: `id, hardware_id UNIQUE, wattage CHECK(>0), efficiency_rating CHECK(5 tier 80 Plus), modular, pcie_8pin_count, pcie_12vhpwr`

## 2. Aturan yang BISA diimplementasikan dari skema aktual

| # | Rule ID | Pair | Sinyal | Hasil bila data lengkap |
|---|---|---|---|---|
| R1 | `cpu-motherboard-socket` | CPU×Mobo | `cpu.socket` vs `mobo.socket` | COMPATIBLE / INCOMPATIBLE; UNKNOWN bila salah satu socket NULL |
| R2 | `ram-motherboard-generation` | RAM×Mobo | `ram.ddr_generation` vs `mobo.ram_type` | COMPATIBLE / INCOMPATIBLE; UNKNOWN bila salah satu NULL |
| R3 | `ram-motherboard-capacity` | RAM×Mobo | `ram.capacity_gb` vs `mobo.max_ram_gb` | INCOMPATIBLE bila capacity > max; UNKNOWN bila salah satu NULL |
| R4 | `ram-motherboard-slots` | RAM×Mobo | `ram.modules` vs `mobo.ram_slots` | INCOMPATIBLE bila modules > slots; UNKNOWN bila salah satu NULL |
| R5 | `storage-motherboard-interface` | Storage×Mobo | `storage.storage_type`+`interface` vs `mobo.m2_slots`/`sata_ports` | NVMe→butuh m2_slots>0; SATA SSD/HDD→butuh sata_ports>0; UNKNOWN bila field kosong |
| R6 | `psu-build-wattage` | PSU×(CPU+GPU) | Σ `tdp_w` CPU+GPU vs `psu.wattage` | INCOMPATIBLE bila PSU < kebutuhan (dengan headroom policy eksplisit); UNKNOWN bila tdp/wattage kosong |
| R7 | `gpu-motherboard-interface` | GPU×Mobo | GPU `interface` PCIe vs mobo `pcie_slots` | Mobo hanya punya *jumlah* slot, bukan *generasi* PCIe → hanya bisa cek pcie_slots>0; UNKNOWN lainnya |
| R8 | `ecc-unsupported` | — | — | **Tidak diimplementasikan**: CPU tidak punya kolom ECC support; mobo tidak punya kolom ECC support. ECC di RAM ada tapi tak ada pasangannya. → tidak dibuat (hindari aturan pura-pura) |

## 3. Field yang TIDAK ADA (dibutuhkan aturan penuh, tidak diimplementasikan)

- **BIOS support CPU↔Mobo** — tidak ada tabel/data. Aturan socket = kompatibilitas fisik-socket saja; jawaban "socket cocok tapi BIOS lama" selalu UNKNOWN.
- **GPU power connectors** — gpu_specifications tidak punya kolom. PSU↔GPU konektor = UNKNOWN; wattage tetap dievaluasi.
- **PCIe generation per slot mobo** — mobo hanya punya `pcie_slots` (jumlah). Aturan GPU = UNKNOWN di luar "ada slot".
- **Memory QVL / XMP / EXPO** — tidak ada. Kecepatan RAM nominal TIDAK dijadikan dasar inkompatibilitas.
- **M.2 protocol vs slot keying** — mobo hanya punya `m2_slots` (jumlah). "M.2 SATA di slot NVMe-only" tidak bisa dideteksi → hanya ketersediaan slot yang dicek.
- **Case / clearance / dimensi** — tidak ada model data → selalu UNKNOWN (di luar scope per instruksi).
- **ECC lintas kategori** — tidak ada lawan data.
- **Latency (CL) RAM** — tidak ada kolom (dicatat untuk M3 harga/spec enrichment).
- **PSU form factor** — tidak ada kolom.

**Keputusan:** tidak ada migrasi baru. Semua aturan di atas bisa dibangun dari skema M1 tanpa mengarang data. UNKNOWN jadi hasil first-class.

## 4. Kontrak API & pola yang diikuti

- Endpoint existing: `GET /hardware`, `/hardware/facets`, `/hardware/{id}`, `POST /auth/*`, `/comparison/*`, `/build/chat`, `/build/conversations`. Konvensi: `response_model=`, HTTPException 404/422, schemas Pydantic di `backend/app/schemas/`.
- Service layer: `backend/app/services/*_service.py`, diuji lewat monkeypatch `main.SessionLocal` + `hardware_catalog_service.SessionLocal` (pola `test_hardware_catalog_api.py` setup_method).
- Provenance: `FieldProvenance(hardware_id, table_name, field_name, evidenced_value, evidence_status...)`; `VALID_TABLES` = single source vocabulary.

## 5. Frontend architecture

- `frontend/src/buildConfig.js`: `BUILD_SLOTS = ["CPU","GPU"]`, `createBuildConfig()`, `setBuildCpu/Gpu`, `clearBuild*`, `getBuildSummary(state)` — **titik ekstensi alami untuk 6 slot**.
- `App.jsx`: `BuildConfigurationSection` render slot CPU/GPU; `CpuDetailView`/`GpuHardwareDetail` dipilih via ternary `type === "GPU"` (TODO(M2) comment dari M1 menandai titik ini).
- Katalog item datang dari API `GET /hardware?type=X` — untuk slot baru cukup panggil dengan type baru.
- Test: `node --test src/*.test.js` (637 pass), `buildConfig.test.js` existing.

## 6. Keputusan desain M2 (ruling)

1. **Engine murni + deterministik**: `backend/app/services/compatibility_service.py` — evaluasi dari objek spesifikasi (bukan query DB di dalam rule), tanpa DB writes, rule version statis `M2-RULES-v1`.
2. **UNKNOWN first-class**: tiga state `COMPATIBLE|INCOMPATIBLE|UNKNOWN`; `NOT_APPLICABLE` terpisah (pasangan komponen tak lengkap). Agregasi: ada INCOMPATIBLE → INCOMPATIBLE; tidak ada tapi ada UNKNOWN/not-applied → UNKNOWN; semua check applicable confirmed → COMPATIBLE.
3. **Endpoint**: `POST /build/compatibility/check` (konvensi prefix `/build/*`), body `BuildCompatibilityRequest` dengan 6 ID opsional, respons berisi per-rule result + agregat + explanation.
4. **Frontend**: perluas `BUILD_SLOTS` ke 6, tambah `setBuildComponent(type, hardware)`/`clearBuildComponent(type)` generic, `BuildConfigurationSection` render 6 slot, status kompatibilitas dari API baru; RAM/STORAGE/MOTHERBOARD/PSU detail view baru (relevan saja, tanpa field CPU).

## Phase 0 GATE: ✓ schema verified ✓ API contracts verified ✓ frontend verified ✓ missing fields didokumentasikan ✓ tanpa mutasi produksi
