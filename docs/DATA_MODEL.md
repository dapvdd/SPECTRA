# SPECTRA Data Model

## 1. Hardware

Hardware adalah entitas utama SPECTRA.

Setiap produk hardware memiliki identitas dasar:

- id
- name
- manufacturer
- type
- release_date
- architecture

Contoh:

- AMD Ryzen 5 5600
- Intel Core i5-12400F

---

## 2. CPU Specifications

Data khusus CPU disimpan terpisah dari identitas hardware.

Fields:

- hardware_id
- cores
- threads
- base_clock_ghz
- boost_clock_ghz
- tdp_w
- process_node_nm
- socket

Contoh Ryzen 5 5600:

- 6 cores
- 12 threads
- 3.5 GHz base
- 4.4 GHz boost
- 65 W TDP
- 7 nm
- AM4

---

## 3. Benchmark Result

Satu hardware dapat memiliki banyak hasil benchmark.

Fields:

- id
- hardware_id
- benchmark_name
- score
- unit
- test_type
- source_id
- recorded_at

Contoh:

Ryzen 5 5600:
- Cinebench R23
- Geekbench
- Blender
- Gaming Benchmark

---

## 4. Source

Source menyimpan asal data.

Fields:

- id
- name
- url
- accessed_at

Setiap data benchmark harus dapat ditelusuri kembali ke sumbernya.

---

## 5. Relationships

Hardware memiliki satu kumpulan CPU Specifications.

Hardware dapat memiliki banyak Benchmark Results.

Satu Source dapat digunakan oleh banyak Benchmark Results.

Relationship:

Hardware → CPU Specifications

Hardware → Benchmark Results

Benchmark Results → Source

---

## 6. Design Principles

### Separation of Concerns

Identitas hardware, spesifikasi, benchmark, dan sumber data dipisahkan.

### Data Provenance

Data harus dapat ditelusuri ke sumber asalnya.

### Raw Data Before Computation

SPECTRA menyimpan data mentah terlebih dahulu.

Perhitungan dilakukan oleh comparison engine.

Flow:

RAW DATA → COMPARISON ENGINE → CALCULATED RESULT → AI ANALYSIS

### Extensibility

Model harus dapat dikembangkan untuk:

- CPU
- GPU
- Laptop
- Desktop
- RAM
- SSD
- Monitor

tanpa harus merombak seluruh database.

---

## 7. Initial Scope

SPECTRA v0.1 dimulai dengan CPU comparison.

Initial hardware:

1. AMD Ryzen 5 5600
2. Intel Core i5-12400F