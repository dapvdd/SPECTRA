import test from "node:test";
import assert from "node:assert/strict";

import {
  assertSuccessfulResponse,
  validateBenchmarkPayload,
  validateCatalogPayload,
  validateComparisonDetailPayload,
  validateHardwareDetailPayload,
} from "./apiValidation.js";

const catalogCpu = (overrides = {}) => ({
  id: 1,
  name: "AMD Ryzen 9 7940HS",
  manufacturer: "AMD",
  type: "Mobile Processor",
  ...overrides,
});

const detailCpu = (overrides = {}) => ({
  id: 1,
  name: "AMD Ryzen 9 7940HS",
  manufacturer: "AMD",
  type: "Mobile Processor",
  specifications: {
    cores: 8,
    threads: 16,
  },
  ...overrides,
});

const detailGpu = (overrides = {}) => ({
  id: 4031,
  name: "Radeon RX 7900 XTX",
  manufacturer: "AMD",
  type: "GPU",
  release_date: "2022-11-03",
  architecture: "RDNA 3.0",
  specifications: {
    memory_gb: 24,
    memory_type: "GDDR6",
    core_clock_mhz: null,
    boost_clock_mhz: 2498,
    vram_bandwidth_gbps: 960,
    tdp_w: 355,
    interface: "PCIe 4.0 x16",
    length_mm: 287,
  },
  ...overrides,
});

const benchmark = {
  benchmark_name: "Geekbench 7",
  score: 520,
  unit: "points",
  test_type: "single-core",
};

test("accepts a valid catalog payload", () => {
  assert.deepEqual(validateCatalogPayload([catalogCpu()]), [catalogCpu()]);
});

test("rejects a non-array catalog payload", () => {
  assert.throws(() => validateCatalogPayload({ hardware: [] }), /must be an array/);
});

test("rejects a catalog item without a usable id", () => {
  assert.throws(
    () => validateCatalogPayload([catalogCpu({ id: 0 })]),
    /invalid id/,
  );
  assert.throws(
    () => validateCatalogPayload([catalogCpu({ id: "1" })]),
    /invalid id/,
  );
});

test("rejects a catalog item with an empty or non-string name", () => {
  assert.throws(
    () => validateCatalogPayload([catalogCpu({ name: "  " })]),
    /invalid name/,
  );
  assert.throws(
    () => validateCatalogPayload([catalogCpu({ name: 7940 })]),
    /invalid name/,
  );
});

test("accepts catalog items with optional fields omitted", () => {
  assert.doesNotThrow(() =>
    validateCatalogPayload([{ id: 1, name: "CPU without optional fields" }]),
  );
  assert.doesNotThrow(() =>
    validateCatalogPayload([
      catalogCpu({ manufacturer: null, type: null }),
    ]),
  );
});

test("accepts a valid hardware detail payload", () => {
  assert.deepEqual(
    validateHardwareDetailPayload(detailCpu(), 1),
    detailCpu(),
  );
});

test("HTTP errors are handled before payload validation", () => {
  assert.throws(
    () => assertSuccessfulResponse({ ok: false, status: 404 }),
    /HTTP error: 404/,
  );
  assert.equal(assertSuccessfulResponse({ ok: true }).ok, true);
});

test("rejects an explicit hardware error payload", () => {
  assert.throws(
    () => validateHardwareDetailPayload({ error: "Hardware not found" }, 1),
    /Hardware not found/,
  );
});

test("rejects a malformed hardware detail object", () => {
  assert.throws(
    () => validateHardwareDetailPayload({ id: 1, name: "CPU", specifications: [] }, 1),
    /invalid specifications/,
  );
  assert.throws(
    () => validateHardwareDetailPayload({ id: 1, name: "CPU", manufacturer: 7 }, 1),
    /invalid text field/,
  );
});

test("accepts valid detail data with optional fields omitted", () => {
  assert.doesNotThrow(() =>
    validateHardwareDetailPayload({ id: 1, name: "CPU" }, 1),
  );
  assert.doesNotThrow(() =>
    validateHardwareDetailPayload(
      { id: 1, name: "CPU", manufacturer: null, specifications: null },
      1,
    ),
  );
});

test("comparison detail validation requires specifications", () => {
  assert.throws(
    () => validateComparisonDetailPayload({ id: 1, name: "CPU" }, 1),
    /missing specifications/,
  );
  assert.doesNotThrow(() =>
    validateComparisonDetailPayload(detailCpu(), 1),
  );
});

test("accepts a valid direct benchmark array", () => {
  assert.deepEqual(validateBenchmarkPayload([benchmark]), [benchmark]);
});

test("accepts valid empty benchmark responses as no-data", () => {
  assert.doesNotThrow(() => validateBenchmarkPayload([]));
  assert.doesNotThrow(() =>
    validateBenchmarkPayload({ benchmark_results: [] }),
  );
});

test("rejects malformed benchmark payloads", () => {
  assert.throws(
    () => validateBenchmarkPayload({ unexpected: [] }),
    /invalid structure/,
  );
  assert.throws(
    () => validateBenchmarkPayload({ benchmarks: [null] }),
    /invalid record/,
  );
});

test("accepts existing benchmark wrapper shapes", () => {
  assert.doesNotThrow(() =>
    validateBenchmarkPayload({ benchmark_results: [benchmark] }),
  );
  assert.doesNotThrow(() => validateBenchmarkPayload({ benchmarks: [benchmark] }));
  assert.doesNotThrow(() =>
    validateBenchmarkPayload({ performance: { results: [benchmark] } }),
  );
});

test("accepts a valid GPU detail payload", () => {
  assert.deepEqual(validateHardwareDetailPayload(detailGpu(), 4031), detailGpu());
});

test("accepts GPU detail payloads with nullable specification fields", () => {
  assert.doesNotThrow(() =>
    validateHardwareDetailPayload(
      detailGpu({
        specifications: {
          memory_gb: null,
          memory_type: null,
          core_clock_mhz: null,
          boost_clock_mhz: null,
          vram_bandwidth_gbps: null,
          tdp_w: null,
          interface: null,
          length_mm: null,
        },
      }),
      4031,
    ),
  );
});

test("rejects GPU detail payloads with malformed specification values", () => {
  assert.throws(
    () =>
      validateHardwareDetailPayload(
        detailGpu({ specifications: { memory_gb: ["nested"] } }),
        4031,
      ),
    /invalid specification value/,
  );
  assert.throws(
    () =>
      validateHardwareDetailPayload(
        detailGpu({ specifications: { tdp_w: { watts: 300 } } }),
        4031,
      ),
    /invalid specification value/,
  );
});

test("GPU specification validation does not reject scalar strings and numbers", () => {
  assert.doesNotThrow(() =>
    validateHardwareDetailPayload(
      detailGpu({
        specifications: {
          memory_gb: 24,
          memory_type: "GDDR6",
          core_clock_mhz: 1405,
          boost_clock_mhz: 2498,
          vram_bandwidth_gbps: 960,
          tdp_w: 355,
          interface: "PCIe 4.0 x16",
          length_mm: 287,
        },
      }),
      4031,
    ),
  );
});

test("CPU detail validation is unaffected by GPU specification rules", () => {
  assert.doesNotThrow(() =>
    validateHardwareDetailPayload(detailCpu(), 1),
  );
  assert.doesNotThrow(() =>
    validateHardwareDetailPayload(
      detailCpu({ specifications: { cores: 8, extra_gpu_field: "ignored" } }),
      1,
    ),
  );
});
