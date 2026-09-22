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
