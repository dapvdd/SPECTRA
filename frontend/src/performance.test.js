import test from "node:test";
import assert from "node:assert/strict";

import {
  getPerformanceState,
  normalizeBenchmarkResults,
} from "./performance.js";

const benchmark = (testType, score, overrides = {}) => ({
  id: score,
  hardware_id: 1,
  benchmark_name: "Geekbench 7",
  score,
  unit: "points",
  test_type: testType,
  source: { id: 1, name: "Geekbench", url: "https://www.geekbench.com/" },
  recorded_at: "2026-09-16T00:00:00Z",
  ...overrides,
});

test("maps Geekbench 7 single-core to Single-Core Performance", () => {
  const results = normalizeBenchmarkResults([benchmark("single-core", 520)]);

  assert.equal(results.single_core.score, 520);
  assert.equal(results.multi_core, undefined);
  assert.equal(results.cpu, undefined);
  assert.equal(results.gaming, undefined);
});

test("maps Geekbench 7 multi-core to Multi-Core Performance", () => {
  const results = normalizeBenchmarkResults([benchmark("multi-core", 520)]);

  assert.equal(results.multi_core.score, 520);
  assert.equal(results.single_core, undefined);
});

test("ignores other benchmarks and invalid units", () => {
  const results = normalizeBenchmarkResults([
    benchmark("single-core", 700, { benchmark_name: "Geekbench 6" }),
    benchmark("multi-core", 800, { unit: "score" }),
    benchmark("single-core", 900, { test_type: "gaming" }),
  ]);

  assert.deepEqual(results, {});
});

test("keeps one deterministic result per Geekbench metric", () => {
  const results = normalizeBenchmarkResults([
    benchmark("single-core", 700, { id: 20 }),
    benchmark("single-core", 520, { id: 10 }),
    benchmark("multi-core", 1040),
  ]);

  assert.equal(results.single_core.score, 520);
  assert.equal(results.multi_core.score, 1040);
});

test("reports unavailable when a CPU has no benchmark", () => {
  assert.equal(
    getPerformanceState({ status: "success", results: [] }).status,
    "unavailable"
  );
});

test("reports partial when only one Geekbench metric is available", () => {
  const state = getPerformanceState({
    status: "success",
    results: [benchmark("single-core", 520)],
  });

  assert.equal(state.status, "partial");
  assert.equal(state.results.single_core.score, 520);
  assert.equal(state.results.multi_core, undefined);
});

test("reports available only when both Geekbench metrics are available", () => {
  const state = getPerformanceState({
    status: "success",
    results: [benchmark("single-core", 520), benchmark("multi-core", 1040)],
  });

  assert.equal(state.status, "available");
});

test("preserves benchmark API errors for the Performance section", () => {
  const state = getPerformanceState({
    status: "error",
    message: "Benchmark service unavailable",
  });

  assert.equal(state.status, "error");
  assert.equal(state.message, "Benchmark service unavailable");
  assert.deepEqual(state.results, {});
});

test("keeps benchmark state isolated for two CPUs", () => {
  const cpuA = getPerformanceState({
    status: "success",
    results: [benchmark("single-core", 520), benchmark("multi-core", 1040)],
  });
  const cpuB = getPerformanceState({
    status: "success",
    results: [benchmark("single-core", 480)],
  });

  assert.equal(cpuA.status, "available");
  assert.equal(cpuB.status, "partial");
  assert.equal(cpuA.results.multi_core.score, 1040);
  assert.equal(cpuB.results.multi_core, undefined);
});
