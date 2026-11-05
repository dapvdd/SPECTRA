import test from "node:test";
import assert from "node:assert/strict";

import {
  buildEmptyGpuInsights,
  buildGpuInsightsFromBackend,
  buildGpuInsightsFromStatus,
} from "./comparisonGpuInsights.js";
import { GPU_METRICS } from "./comparison.js";

const gpu = (name, id) => ({ id, name, type: "GPU" });

const metric = (name, winner, valueA = null, valueB = null, difference = null) => ({
  name,
  value_a: valueA,
  value_b: valueB,
  winner,
  difference,
});

const payload = (metrics, hardwareA = "GPU A", hardwareB = "GPU B") => ({
  hardware_a: hardwareA,
  hardware_b: hardwareB,
  metrics,
});

test("empty backend payload maps to empty insights", () => {
  const insights = buildGpuInsightsFromBackend({ metrics: [] }, [gpu("GPU A", 1), gpu("GPU B", 2)]);

  assert.deepEqual(insights, buildEmptyGpuInsights());
});

test("backend winner 'a' maps to cpuA with a higher-is-better percentage", () => {
  const insights = buildGpuInsightsFromBackend(
    payload([metric("memory_gb", "a", 24, 16, 8)]),
    [gpu("GPU A", 1), gpu("GPU B", 2)]
  );

  assert.equal(insights.measurableCount, 1);
  assert.deepEqual(insights.wins, { cpuA: 1, cpuB: 0 });
  assert.equal(insights.insights[0].metricKey, "memory_gb");
  assert.equal(insights.insights[0].winner, "cpuA");
  assert.equal(insights.insights[0].winnerName, "GPU A");
  assert.equal(insights.insights[0].differencePercent, 50);
  assert.equal(insights.insights[0].direction, "higher");
});

test("backend winner 'b' maps to cpuB", () => {
  const insights = buildGpuInsightsFromBackend(
    payload([metric("memory_gb", "b", 16, 32, -16)]),
    [gpu("GPU A", 1), gpu("GPU B", 2)]
  );

  assert.deepEqual(insights.wins, { cpuA: 0, cpuB: 1 });
  assert.equal(insights.insights[0].winner, "cpuB");
  assert.equal(insights.insights[0].winnerName, "GPU B");
  assert.equal(insights.insights[0].differencePercent, 100);
});

test("lower-is-better tdp winner reports the 'lower' direction", () => {
  const insights = buildGpuInsightsFromBackend(
    payload([metric("tdp_w", "a", 200, 300, -100)]),
    [gpu("GPU A", 1), gpu("GPU B", 2)]
  );

  assert.equal(insights.insights[0].direction, "lower");
  assert.equal(insights.insights[0].winner, "cpuA");
  assert.equal(insights.insights[0].metricKey, "tdp_w");
  assert.equal(insights.insights[0].differencePercent, 33.3);
});

test("tie metrics are collected as tie details without a winner", () => {
  const insights = buildGpuInsightsFromBackend(
    payload([metric("memory_gb", "tie", 16, 16, 0)]),
    [gpu("GPU A", 1), gpu("GPU B", 2)]
  );

  assert.equal(insights.measurableCount, 1);
  assert.equal(insights.ties, 1);
  assert.deepEqual(insights.insights, []);
  assert.equal(insights.tieDetails[0].metricKey, "memory_gb");
  assert.equal(insights.tieDetails[0].value, 16);
});

test("unavailable metrics are reported as unavailable, never as losses", () => {
  const insights = buildGpuInsightsFromBackend(
    payload([metric("memory_gb", "unavailable", 24, null, null)]),
    [gpu("GPU A", 1), gpu("GPU B", 2)]
  );

  assert.equal(insights.measurableCount, 0);
  assert.equal(insights.unavailableMetrics.length, 1);
  assert.equal(insights.unavailableMetrics[0].key, "memory_gb");
});

test("unknown metric names are ignored rather than rendered", () => {
  const insights = buildGpuInsightsFromBackend(
    payload([metric("not_a_real_gpu_metric", "a", 10, 5, 5)]),
    [gpu("GPU A", 1), gpu("GPU B", 2)]
  );

  assert.equal(insights.measurableCount, 0);
  assert.deepEqual(insights.insights, []);
});

test("non-payload input maps to empty insights", () => {
  assert.deepEqual(buildGpuInsightsFromBackend(null), buildEmptyGpuInsights());
  assert.deepEqual(buildGpuInsightsFromBackend({}), buildEmptyGpuInsights());
});

test("idle status maps to empty insights without pending metrics", () => {
  const insights = buildGpuInsightsFromStatus("idle", null, [gpu("GPU A", 1), gpu("GPU B", 2)], GPU_METRICS);

  assert.deepEqual(insights.pendingMetrics, []);
  assert.deepEqual(insights, buildEmptyGpuInsights());
});

test("loading status flags every GPU metric as pending, never unavailable", () => {
  const insights = buildGpuInsightsFromStatus("loading", null, [gpu("GPU A", 1), gpu("GPU B", 2)], GPU_METRICS);

  assert.equal(insights.pendingMetrics.length, GPU_METRICS.length);
  assert.equal(insights.unavailableMetrics.length, 0);
  assert.equal(insights.measurableCount, 0);
});

test("error status maps to empty insights without fabricating data", () => {
  const insights = buildGpuInsightsFromStatus("error", null, [gpu("GPU A", 1), gpu("GPU B", 2)], GPU_METRICS);

  assert.deepEqual(insights, buildEmptyGpuInsights());
});

test("success status maps the backend verdict into insights", () => {
  const insights = buildGpuInsightsFromStatus(
    "success",
    payload([metric("memory_gb", "a", 24, 16, 8)]),
    [gpu("GPU A", 1), gpu("GPU B", 2)],
    GPU_METRICS,
  );

  assert.equal(insights.measurableCount, 1);
  assert.deepEqual(insights.wins, { cpuA: 1, cpuB: 0 });
});
