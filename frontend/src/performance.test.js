import test from "node:test";
import assert from "node:assert/strict";

import {
  getBenchmarkComparisonData,
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

const cpu = (id, name = `CPU ${id}`) => ({ id, name });

const comparisonStates = (scoreA, scoreB, shape = "results") => {
  const resultsA = [benchmark("multi-core", scoreA)];
  const resultsB = [benchmark("multi-core", scoreB)];
  const wrap = (results) =>
    shape === "benchmark_results"
      ? { benchmark_results: results }
      : shape === "benchmarks"
        ? { benchmarks: results }
        : shape === "performance"
          ? { performance: { results } }
          : results;

  return {
    1: { status: "success", results: wrap(resultsA) },
    2: { status: "success", results: wrap(resultsB) },
  };
};

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

test("normalizes two valid benchmark scores against the larger score", () => {
  const data = getBenchmarkComparisonData(
    [cpu(1, "CPU A"), cpu(2, "CPU B")],
    comparisonStates(12000, 9000)
  );

  const metric = data.metrics[0];
  assert.equal(data.status, "partial");
  assert.deepEqual(
    metric.rows.map((row) => row.width),
    [100, 75]
  );
  assert.deepEqual(
    metric.rows.map((row) => row.value),
    [12000, 9000]
  );
  assert.equal(metric.winner, "cpuA");
});

test("normalizes CPU B as the larger score", () => {
  const data = getBenchmarkComparisonData(
    [cpu(1), cpu(2)],
    comparisonStates(9000, 12000)
  );

  assert.deepEqual(
    data.metrics[0].rows.map((row) => row.width),
    [75, 100]
  );
  assert.equal(data.metrics[0].winner, "cpuB");
});

test("equal benchmark scores produce equal bars and a tie", () => {
  const data = getBenchmarkComparisonData(
    [cpu(1), cpu(2)],
    comparisonStates(10000, 10000)
  );

  assert.deepEqual(
    data.metrics[0].rows.map((row) => row.width),
    [100, 100]
  );
  assert.equal(data.metrics[0].winner, "tie");
});

test("only CPU A available renders CPU B as unavailable", () => {
  const data = getBenchmarkComparisonData(
    [cpu(1), cpu(2)],
    {
      1: { status: "success", results: [benchmark("multi-core", 12000)] },
      2: { status: "success", results: [] },
    }
  );

  assert.equal(data.status, "partial");
  assert.deepEqual(data.metrics[0].rows.map((row) => row.width), [100, null]);
  assert.deepEqual(data.metrics[0].rows.map((row) => row.value), [12000, null]);
  assert.equal(data.metrics[0].winner, null);
});

test("only CPU B available renders CPU A as unavailable", () => {
  const data = getBenchmarkComparisonData(
    [cpu(1), cpu(2)],
    {
      1: { status: "success", results: [] },
      2: { status: "success", results: [benchmark("multi-core", 9000)] },
    }
  );

  assert.deepEqual(data.metrics[0].rows.map((row) => row.width), [null, 100]);
  assert.deepEqual(data.metrics[0].rows.map((row) => row.value), [null, 9000]);
});

test("both benchmark scores unavailable produce an unavailable state", () => {
  const data = getBenchmarkComparisonData(
    [cpu(1), cpu(2)],
    {
      1: { status: "success", results: [] },
      2: { status: "success", results: [] },
    }
  );

  assert.equal(data.status, "unavailable");
  assert.deepEqual(data.metrics[0].rows.map((row) => row.width), [null, null]);
});

test("invalid, zero, negative, and non-finite scores are unavailable", () => {
  const invalid = [0, -10, Number.NaN, Number.POSITIVE_INFINITY];

  for (const score of invalid) {
    const data = getBenchmarkComparisonData(
      [cpu(1), cpu(2)],
      {
        1: { status: "success", results: [benchmark("multi-core", score)] },
        2: { status: "success", results: [] },
      }
    );

    assert.equal(data.metrics[0].rows[0].value, null);
    assert.equal(data.metrics[0].rows[0].width, null);
  }
});

test("loading benchmark data remains a loading visualization state", () => {
  const data = getBenchmarkComparisonData(
    [cpu(1), cpu(2)],
    {
      1: { status: "loading" },
      2: { status: "success", results: [] },
    }
  );

  assert.equal(data.status, "loading");
});

test("recognizes supported benchmark response wrapper shapes", () => {
  for (const shape of ["benchmark_results", "benchmarks", "performance"]) {
    const data = getBenchmarkComparisonData(
      [cpu(1), cpu(2)],
      comparisonStates(12000, 9000, shape)
    );

    assert.deepEqual(
      data.metrics[0].rows.map((row) => row.value),
      [12000, 9000]
    );
  }
});
