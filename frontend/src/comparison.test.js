import test from "node:test";
import assert from "node:assert/strict";

import {
  calculateComparisonInsights,
  buildComparisonFacts,
  COMPARISON_METRICS,
  getComparisonWinner,
  isValidComparisonValue,
} from "./comparison.js";

const cpu = (name, specifications = {}, manufacturer = "Vendor") => ({
  id: name,
  name,
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
