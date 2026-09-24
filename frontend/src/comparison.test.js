import test from "node:test";
import assert from "node:assert/strict";

import {
  calculateComparisonInsights,
  buildComparisonFacts,
  COMPARISON_METRICS,
  GPU_METRICS,
  GPU_TABLE_SPECS,
  getComparisonMetrics,
  getComparisonWinner,
  getComparisonWinnerClass,
  isValidComparisonValue,
} from "./comparison.js";

const cpu = (name, specifications = {}, manufacturer = "Vendor") => ({
  id: name,
  name,
  manufacturer,
  specifications,
});

const gpu = (name, specifications = {}, manufacturer = "Vendor") => ({
  id: name,
  name,
  type: "GPU",
  manufacturer,
  specifications,
});

const benchmark = (testType, score) => ({
  benchmark_name: "Geekbench 7",
  score,
  unit: "points",
  test_type: testType,
});

const benchmarkState = (...results) => ({
  status: "success",
  results,
});

test("CPU A wins a higher-is-better metric", () => {
  assert.equal(getComparisonWinner(16, 12, "higher"), "cpuA");
});

test("CPU B wins a higher-is-better metric", () => {
  assert.equal(getComparisonWinner(3.6, 4.2, "higher"), "cpuB");
});

test("CPU A wins lower-is-better TDP", () => {
  assert.equal(getComparisonWinner(65, 105, "lower"), "cpuA");
});

test("CPU B wins lower-is-better TDP", () => {
  assert.equal(getComparisonWinner(125, 65, "lower"), "cpuB");
});

test("higher-is-better winner highlighting only marks CPU A", () => {
  const winner = getComparisonWinner(16, 12, "higher");

  assert.equal(getComparisonWinnerClass(winner, 0), "comparison-winner");
  assert.equal(getComparisonWinnerClass(winner, 1), "");
});

test("higher-is-better ties do not highlight either CPU", () => {
  const winner = getComparisonWinner(16, 16, "higher");

  assert.equal(getComparisonWinnerClass(winner, 0), "");
  assert.equal(getComparisonWinnerClass(winner, 1), "");
});

test("lower-is-better TDP winner highlighting only marks the lower value", () => {
  const winner = getComparisonWinner(65, 105, "lower");

  assert.equal(getComparisonWinnerClass(winner, 0), "comparison-winner");
  assert.equal(getComparisonWinnerClass(winner, 1), "");
});

test("lower-is-better TDP ties do not highlight either CPU", () => {
  const winner = getComparisonWinner(65, 65, "lower");

  assert.equal(getComparisonWinnerClass(winner, 0), "");
  assert.equal(getComparisonWinnerClass(winner, 1), "");
});

test("unavailable comparison values do not receive winner highlighting", () => {
  const winner = getComparisonWinner(undefined, 65, "lower");

  assert.equal(winner, null);
  assert.equal(getComparisonWinnerClass(winner, 0), "");
  assert.equal(getComparisonWinnerClass(winner, 1), "");
});

test("calculates higher-is-better percentage from the loser value", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A", { cores: 16 }),
    cpu("CPU B", { cores: 12 }),
  ]);

  assert.equal(result.insights[0].differencePercent, 33.3);
  assert.equal(result.insights[0].winnerValue, 16);
  assert.equal(result.insights[0].loserValue, 12);
});

test("calculates lower-is-better TDP percentage from the loser value", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A", { tdp_w: 65 }),
    cpu("CPU B", { tdp_w: 105 }),
  ]);

  assert.equal(result.insights[0].differencePercent, 38.1);
  assert.equal(result.insights[0].direction, "lower");
});

test("equal values produce a tie without a winner insight", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A", { base_clock_ghz: 3.8 }),
    cpu("CPU B", { base_clock_ghz: 3.8 }),
  ]);

  assert.equal(result.measurableCount, 1);
  assert.equal(result.ties, 1);
  assert.deepEqual(result.insights, []);
  assert.equal(result.tieDetails[0].value, 3.8);
});

test("missing CPU A value is unavailable and not a winner", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A"),
    cpu("CPU B", { threads: 16 }),
  ]);

  assert.equal(result.measurableCount, 0);
  assert.deepEqual(result.wins, { cpuA: 0, cpuB: 0 });
  assert.equal(result.unavailableMetrics.length, COMPARISON_METRICS.length);
});

test("missing CPU B value is unavailable and not a winner", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A", { threads: 16 }),
    cpu("CPU B"),
  ]);

  assert.equal(result.measurableCount, 0);
  assert.deepEqual(result.wins, { cpuA: 0, cpuB: 0 });
});

test("both values missing are unavailable", () => {
  const result = calculateComparisonInsights([cpu("CPU A"), cpu("CPU B")]);

  assert.equal(result.measurableCount, 0);
  assert.equal(result.ties, 0);
  assert.equal(result.insights.length, 0);
});

test("zero is not used as a denominator or comparable CPU value", () => {
  assert.equal(getComparisonWinner(0, 10, "higher"), null);
  assert.equal(getComparisonWinner(10, 0, "lower"), null);

  const result = calculateComparisonInsights([
    cpu("CPU A", { cores: 0 }),
    cpu("CPU B", { cores: 10 }),
  ]);

  assert.equal(result.measurableCount, 0);
});

test("negative, NaN, Infinity, and non-number values are invalid", () => {
  for (const value of [-1, Number.NaN, Number.POSITIVE_INFINITY, "16", null]) {
    assert.equal(isValidComparisonValue(value), false);
  }
});

test("multiple metric wins produce deterministic counts and priority order", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A", {
      cores: 16,
      threads: 24,
      boost_clock_ghz: 5.2,
      tdp_w: 65,
    }),
    cpu("CPU B", {
      cores: 12,
      threads: 16,
      boost_clock_ghz: 4.8,
      tdp_w: 105,
    }),
  ]);

  assert.equal(result.measurableCount, 4);
  assert.deepEqual(result.wins, { cpuA: 4, cpuB: 0 });
  assert.deepEqual(
    result.insights.map((insight) => insight.metricKey),
    ["cores", "threads", "boost_clock_ghz", "tdp_w"]
  );
});

test("benchmark single-core and multi-core scores participate when available", () => {
  const result = calculateComparisonInsights(
    [cpu("CPU A"), cpu("CPU B")],
    {
      "CPU A": benchmarkState(
        benchmark("single-core", 6569),
        benchmark("multi-core", 12000)
      ),
      "CPU B": benchmarkState(
        benchmark("single-core", 5320),
        benchmark("multi-core", 10000)
      ),
    }
  );

  assert.equal(result.measurableCount, 2);
  assert.deepEqual(result.wins, { cpuA: 2, cpuB: 0 });
  assert.equal(result.insights[0].metricKey, "multi_core");
  assert.equal(result.insights[1].metricKey, "single_core");
  assert.equal(result.insights[1].differencePercent, 23.5);
});

test("partial benchmark data only compares metrics available for both CPUs", () => {
  const result = calculateComparisonInsights(
    [cpu("CPU A"), cpu("CPU B")],
    {
      "CPU A": benchmarkState(benchmark("single-core", 6569)),
      "CPU B": benchmarkState(benchmark("single-core", 5320)),
    }
  );

  assert.equal(result.measurableCount, 1);
  assert.equal(result.wins.cpuA, 1);
  assert.equal(result.insights[0].metricKey, "single_core");
});

test("benchmark loading is not reported as unavailable", () => {
  const result = calculateComparisonInsights(
    [cpu("CPU A"), cpu("CPU B")],
    {
      "CPU A": { status: "loading" },
      "CPU B": { status: "loading" },
    }
  );

  assert.equal(result.pendingMetrics.length, 2);
  assert.equal(result.unavailableMetrics.length, 5);
});

test("only supported metrics are generated; no CPU or gaming aggregate is invented", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A", { cores: 16, threads: 24 }),
    cpu("CPU B", { cores: 12, threads: 16 }),
  ]);

  assert.equal(result.insights.some((insight) => insight.metricKey === "cpu"), false);
  assert.equal(
    result.insights.some((insight) => insight.metricKey === "gaming"),
    false
  );
  assert.equal(result.insights.some((insight) => insight.metricKey === "socket"), false);
});

test("builds AI facts from deterministic metrics and preserves unavailable data", () => {
  const facts = buildComparisonFacts([
    cpu("CPU A", { cores: 8 }),
    cpu("CPU B", { cores: 6 }),
  ]);

  assert.deepEqual(facts.cpu_a, {
    name: "CPU A",
    manufacturer: "Vendor",
  });
  assert.equal(facts.metrics[0].name, "Cores");
  assert.equal(facts.metrics[0].value_a, 8);
  assert.equal(facts.metrics[0].value_b, 6);
  assert.equal(facts.metrics[0].winner, "cpu_a");
  assert.equal(facts.metrics[0].difference_percent, 33.3);
  assert.equal(facts.unavailable_metrics.some((metric) => metric.metric_key === "multi_core"), true);
});

test("does not build AI facts until two CPUs are selected", () => {
  assert.equal(buildComparisonFacts([cpu("CPU A")]), null);
});

test("GPU metric definitions cover exactly the six deterministic metrics", () => {
  assert.deepEqual(
    GPU_METRICS.map((metric) => metric.key),
    [
      "memory_gb",
      "vram_bandwidth_gbps",
      "core_clock_mhz",
      "boost_clock_mhz",
      "tdp_w",
      "length_mm",
    ],
  );
  assert.equal(
    GPU_METRICS.filter((metric) => metric.direction === "higher").length,
    4,
  );
  assert.equal(
    GPU_METRICS.filter((metric) => metric.direction === "lower").length,
    2,
  );
  for (const key of [
    "shader",
    "texture",
    "tensor",
    "transistor",
    "gaming",
    "ray",
  ]) {
    assert.equal(GPU_METRICS.some((metric) => metric.key.includes(key)), false);
  }
});

test("comparison metrics are selected by hardware type", () => {
  assert.strictEqual(getComparisonMetrics("GPU"), GPU_METRICS);
  assert.strictEqual(getComparisonMetrics("CPU"), COMPARISON_METRICS);
  assert.strictEqual(getComparisonMetrics(undefined), COMPARISON_METRICS);
});

test("GPU higher-is-better VRAM winner", () => {
  assert.equal(getComparisonWinner(24, 16, "higher"), "cpuA");
  assert.equal(getComparisonWinner(16, 24, "higher"), "cpuB");
});

test("GPU lower-is-better TDP winner", () => {
  assert.equal(getComparisonWinner(300, 575, "lower"), "cpuA");
  assert.equal(getComparisonWinner(575, 300, "lower"), "cpuB");
});

test("GPU equal metric values produce a tie", () => {
  assert.equal(getComparisonWinner(16, 16, "higher"), "tie");
});

test("GPU missing and invalid values are unavailable, never zero", () => {
  assert.equal(getComparisonWinner(undefined, 16, "higher"), null);
  assert.equal(getComparisonWinner(0, 16, "higher"), null);
  assert.equal(getComparisonWinner(null, 24, "higher"), null);
  assert.equal(getComparisonWinner(Number.NaN, 24, "higher"), null);
});

test("GPU percentage difference uses the loser value", () => {
  const result = calculateComparisonInsights([
    gpu("GPU A", { memory_gb: 32 }),
    gpu("GPU B", { memory_gb: 16 }),
  ]);

  assert.equal(result.insights[0].metricKey, "memory_gb");
  assert.equal(result.insights[0].differencePercent, 100);
});

test("GPU lower-is-better percentage uses the loser value", () => {
  const result = calculateComparisonInsights([
    gpu("GPU A", { tdp_w: 300 }),
    gpu("GPU B", { tdp_w: 575 }),
  ]);

  assert.equal(result.insights[0].metricKey, "tdp_w");
  assert.equal(result.insights[0].direction, "lower");
  assert.equal(result.insights[0].differencePercent, 47.8);
});

test("GPU comparison insights are deterministic and metric-by-metric", () => {
  const result = calculateComparisonInsights([
    gpu("GPU A", {
      memory_gb: 24,
      vram_bandwidth_gbps: 960,
      core_clock_mhz: 2155,
      boost_clock_mhz: 2498,
      tdp_w: 355,
      length_mm: 287,
    }),
    gpu("GPU B", {
      memory_gb: 12,
      vram_bandwidth_gbps: 448,
      core_clock_mhz: 1860,
      boost_clock_mhz: 2430,
      tdp_w: 220,
      length_mm: 242,
    }),
  ]);

  assert.equal(result.measurableCount, 6);
  assert.deepEqual(result.wins, { cpuA: 4, cpuB: 2 });
  assert.deepEqual(
    result.insights.map((insight) => insight.metricKey),
    [
      "memory_gb",
      "vram_bandwidth_gbps",
      "core_clock_mhz",
      "boost_clock_mhz",
      "tdp_w",
      "length_mm",
    ],
  );
});

test("GPU null fields are unavailable, never treated as zero", () => {
  const result = calculateComparisonInsights([
    gpu("GPU A", { memory_gb: null }),
    gpu("GPU B", { memory_gb: 24 }),
  ]);

  assert.equal(result.measurableCount, 0);
  assert.deepEqual(result.wins, { cpuA: 0, cpuB: 0 });
  assert.equal(result.unavailableMetrics.length, GPU_METRICS.length);
});

test("GPU ties are reported without a universal winner", () => {
  const result = calculateComparisonInsights([
    gpu("GPU A", { tdp_w: 300 }),
    gpu("GPU B", { tdp_w: 300 }),
  ]);

  assert.equal(result.ties, 1);
  assert.deepEqual(result.insights, []);
  assert.equal(result.tieDetails[0].metricKey, "tdp_w");
});

test("GPU buildComparisonFacts uses specification source without inventing data", () => {
  const facts = buildComparisonFacts([
    gpu("GPU A", { memory_gb: 32 }),
    gpu("GPU B", { memory_gb: 16 }),
  ]);

  assert.equal(facts.metrics[0].name, "VRAM");
  assert.equal(facts.metrics[0].source, "specification");
  assert.equal(facts.metrics[0].difference_percent, 100);
});

test("GPU comparison table specs separate winner metrics from informational rows", () => {
  assert.deepEqual(
    GPU_TABLE_SPECS.map((spec) => spec.key),
    [
      "memory_gb",
      "memory_type",
      "vram_bandwidth_gbps",
      "core_clock_mhz",
      "boost_clock_mhz",
      "tdp_w",
      "length_mm",
      "interface",
      "architecture",
      "release_date",
    ],
  );
  assert.equal(GPU_TABLE_SPECS.filter((spec) => spec.direction).length, 6);
  assert.deepEqual(
    GPU_TABLE_SPECS.filter((spec) => !spec.direction).map((spec) => spec.key),
    ["memory_type", "interface", "architecture", "release_date"],
  );
});

test("CPU comparison remains CPU-metric based even with GPU fields present", () => {
  const result = calculateComparisonInsights([
    cpu("CPU A", { cores: 8, memory_gb: 32 }),
    cpu("CPU B", { cores: 6, memory_gb: 16 }),
  ]);

  assert.equal(result.insights.some((insight) => insight.metricKey === "memory_gb"), false);
  assert.equal(result.insights.some((insight) => insight.metricKey === "cores"), true);
});
