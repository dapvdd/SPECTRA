import test from "node:test";
import assert from "node:assert/strict";

import { buildComparisonEvidence } from "./comparisonEvidence.js";

const cpu = (name, specifications = {}, manufacturer = "Vendor", id = name) => ({
  id,
  name,
  type: "CPU",
  manufacturer,
  specifications,
});

const gpu = (name, specifications = {}, manufacturer = "Vendor", id = name) => ({
  id,
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

const fullCpuSpecs = {
  cores: 16,
  threads: 32,
  base_clock_ghz: 3.2,
  boost_clock_ghz: 5.1,
  tdp_w: 125,
};

test("returns null for invalid input", () => {
  assert.equal(buildComparisonEvidence([]), null);
  assert.equal(buildComparisonEvidence([cpu("CPU A")]), null);
  assert.equal(buildComparisonEvidence(null), null);
  assert.equal(buildComparisonEvidence(undefined), null);
});

test("separates benchmark wins from spec wins when both sides have benchmark data", () => {
  const evidence = buildComparisonEvidence(
    [
      cpu("CPU A", { ...fullCpuSpecs, cores: 24, threads: 48 }, "AMD", 1),
      cpu("CPU B", fullCpuSpecs, "Intel", 2),
    ],
    {
      1: benchmarkState(benchmark("multi-core", 24000), benchmark("single-core", 12000)),
      2: benchmarkState(benchmark("multi-core", 18000), benchmark("single-core", 9000)),
    }
  );

  assert.equal(evidence.benchmark.wins.cpuA, 2);
  assert.equal(evidence.benchmark.wins.cpuB, 0);
  assert.equal(evidence.benchmark.measurableCount, 2);
  assert.equal(evidence.benchmark.metrics.length, 2);

  assert.equal(evidence.specification.wins.cpuA, 2);
  assert.equal(evidence.specification.wins.cpuB, 0);
  assert.equal(evidence.specification.measurableCount, 5);
  assert.equal(evidence.specification.ties, 3);
});

test("benchmark group is empty when neither side has benchmark data", () => {
  const evidence = buildComparisonEvidence([
    cpu("CPU A", { ...fullCpuSpecs, cores: 24 }, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(evidence.benchmark.wins.cpuA, 0);
  assert.equal(evidence.benchmark.wins.cpuB, 0);
  assert.equal(evidence.benchmark.measurableCount, 0);
  assert.equal(evidence.benchmark.metrics.length, 0);

  assert.equal(evidence.specification.wins.cpuA, 1);
  assert.equal(evidence.specification.ties, 4);
  assert.equal(evidence.specification.measurableCount, 5);
});

test("partial benchmark data is detected and reported", () => {
  const evidence = buildComparisonEvidence(
    [cpu("CPU A", fullCpuSpecs, "AMD", 1), cpu("CPU B", fullCpuSpecs, "Intel", 2)],
    {
      1: benchmarkState(benchmark("multi-core", 24000)),
    }
  );

  assert.equal(evidence.benchmark.coverage.isPartial, true);
  assert.equal(evidence.benchmark.coverage.withData, 1);
  assert.equal(evidence.benchmark.coverage.total, 2);
});

test("GPU comparison has no benchmark metrics and all spec wins", () => {
  const evidence = buildComparisonEvidence([
    gpu("Card A", { memory_gb: 24, tdp_w: 320 }, "NVIDIA", 1),
    gpu("Card B", { memory_gb: 16, tdp_w: 260 }, "AMD", 2),
  ]);

  assert.equal(evidence.benchmark.metricCount, 0);
  assert.equal(evidence.benchmark.measurableCount, 0);
  assert.equal(evidence.specification.wins.cpuA, 1);
  assert.equal(evidence.specification.wins.cpuB, 1);
  assert.equal(evidence.specification.measurableCount, 2);
});

test("missing spec values are never counted as measurable", () => {
  const evidence = buildComparisonEvidence([
    cpu("CPU A", { ...fullCpuSpecs, cores: null }, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(evidence.specification.wins.cpuA, 0);
  assert.equal(evidence.specification.wins.cpuB, 0);
  assert.equal(evidence.specification.ties, 4);
  assert.equal(evidence.specification.measurableCount, 4);
  assert.ok(
    evidence.specification.unavailable.some((m) => m.key === "cores")
  );
});

test("zero spec values are never counted as measurable", () => {
  const evidence = buildComparisonEvidence([
    cpu("CPU A", { ...fullCpuSpecs, cores: 0 }, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(evidence.specification.ties, 4);
  assert.equal(evidence.specification.measurableCount, 4);
  assert.ok(
    evidence.specification.unavailable.some((m) => m.key === "cores")
  );
});

test("benchmark ties are separated from spec ties", () => {
  const evidence = buildComparisonEvidence(
    [cpu("CPU A", { cores: 16 }, "AMD", 1), cpu("CPU B", { cores: 16 }, "Intel", 2)],
    {
      1: benchmarkState(benchmark("multi-core", 20000), benchmark("single-core", 10000)),
      2: benchmarkState(benchmark("multi-core", 20000), benchmark("single-core", 10000)),
    }
  );

  assert.equal(evidence.benchmark.ties, 2);
  assert.equal(evidence.benchmark.measurableCount, 2);
  assert.equal(evidence.specification.ties, 1);
  assert.equal(evidence.specification.measurableCount, 1);
});

test("benchmark coverage is complete when both sides have data", () => {
  const evidence = buildComparisonEvidence(
    [cpu("CPU A", fullCpuSpecs, "AMD", 1), cpu("CPU B", fullCpuSpecs, "Intel", 2)],
    {
      1: benchmarkState(benchmark("multi-core", 24000), benchmark("single-core", 12000)),
      2: benchmarkState(benchmark("multi-core", 18000), benchmark("single-core", 9000)),
    }
  );

  assert.equal(evidence.benchmark.coverage.isComplete, true);
  assert.equal(evidence.benchmark.coverage.isPartial, false);
  assert.equal(evidence.benchmark.coverage.isNone, false);
});

test("benchmark coverage is none when no side has data", () => {
  const evidence = buildComparisonEvidence([
    cpu("CPU A", fullCpuSpecs, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(evidence.benchmark.coverage.isNone, true);
  assert.equal(evidence.benchmark.coverage.isComplete, false);
  assert.equal(evidence.benchmark.coverage.isPartial, false);
});

test("evidence groups have correct labels", () => {
  const evidence = buildComparisonEvidence([
    cpu("CPU A", fullCpuSpecs, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(evidence.benchmark.label, "Measured benchmarks");
  assert.equal(evidence.specification.label, "Specifications");
});

test("benchmark loading state is handled gracefully", () => {
  const evidence = buildComparisonEvidence(
    [cpu("CPU A", fullCpuSpecs, "AMD", 1), cpu("CPU B", fullCpuSpecs, "Intel", 2)],
    {
      1: { status: "loading" },
      2: { status: "loading" },
    }
  );

  assert.equal(evidence.benchmark.measurableCount, 0);
  assert.equal(evidence.specification.measurableCount, 5);
});
