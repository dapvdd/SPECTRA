import test from "node:test";
import assert from "node:assert/strict";

import {
  AVAILABILITY_STATUS,
  CPU_TABLE_SPECS,
  DECISION_STATUS,
  buildComparisonAvailability,
  buildComparisonDecisionSummary,
  buildComparisonLeadGroups,
  buildComparisonOverview,
  buildComparisonSpecRows,
  getComparisonTableSpecs,
} from "./comparisonDecision.js";

const cpu = (name, specifications = {}, manufacturer = "Vendor", id = name) => ({
  id,
  name,
  type: "CPU",
  manufacturer,
  specifications,
});

const untyped = (name, specifications = {}) => ({
  id: name,
  name,
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
  process_node_nm: 7,
  socket: "LGA1700",
};

const fullCpuBenchmarks = (score = 20000) =>
  benchmarkState(
    benchmark("multi-core", score),
    benchmark("single-core", Math.round(score / 2))
  );

test("comparison overview is null for an empty comparison", () => {
  assert.equal(buildComparisonOverview([]), null);
  assert.equal(buildComparisonOverview(undefined), null);
  assert.equal(buildComparisonOverview([cpu("CPU A")]), null);
});

test("comparison overview names both sides, the type, and the manufacturers", () => {
  const overview = buildComparisonOverview([
    cpu("Ryzen 9", fullCpuSpecs, "AMD", 1),
    cpu("Core i9", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(overview.heading, "CPU Comparison");
  assert.equal(overview.noun, "CPU");
  assert.equal(overview.slotType, "CPU");
  assert.equal(overview.headline, "Ryzen 9 vs Core i9");
  assert.equal(overview.subhead, "CPU comparison · AMD vs Intel");
  assert.deepEqual(
    overview.participants.map((participant) => participant.side),
    ["cpuA", "cpuB"]
  );
  assert.deepEqual(
    overview.participants.map((participant) => participant.name),
    ["Ryzen 9", "Core i9"]
  );
  assert.deepEqual(
    overview.participants.map((participant) => participant.manufacturer),
    ["AMD", "Intel"]
  );
});

test("GPU comparison overview reports the GPU slot type", () => {
  const overview = buildComparisonOverview([
    gpu("Card A", { memory_gb: 16 }),
    gpu("Card B", { memory_gb: 8 }),
  ]);

  assert.equal(overview.heading, "GPU Comparison");
  assert.equal(overview.headline, "Card A vs Card B");
  assert.equal(overview.participants[0].type, "GPU");
});

test("comparison overview degrades to a generic noun without a type", () => {
  const overview = buildComparisonOverview([
    untyped("Part A", {}),
    untyped("Part B", {}),
  ]);

  assert.equal(overview.noun, "hardware");
  assert.equal(overview.heading, "Compare Hardware");
  assert.equal(overview.subhead, "hardware comparison");
  assert.equal(overview.participants[0].type, "N/A");
});

const findSource = (availability, source) => availability[source];
const findRow = (rows, key) => rows.find((row) => row.key === key);

test("availability is null for an empty comparison", () => {
  assert.equal(buildComparisonAvailability([]), null);
  assert.equal(buildComparisonAvailability([cpu("CPU A")]), null);
});

test("complete CPU data reports full availability with no limitations", () => {
  const availability = buildComparisonAvailability(
    [cpu("CPU A", fullCpuSpecs, "AMD", 1), cpu("CPU B", fullCpuSpecs, "Intel", 2)],
    { 1: fullCpuBenchmarks(), 2: fullCpuBenchmarks() }
  );

  assert.equal(availability.completeness, AVAILABILITY_STATUS.complete);
  assert.equal(availability.isLoading, false);
  assert.equal(availability.measurableCount, 7);
  assert.equal(availability.totalCount, 7);
  assert.equal(findSource(availability, "benchmark").status, AVAILABILITY_STATUS.complete);
  assert.equal(
    findSource(availability, "specification").status,
    AVAILABILITY_STATUS.complete
  );
  assert.deepEqual(availability.notes, [
    "Every supported metric has a verified value for both sides of this comparison.",
  ]);
});

test("specification-only data stays complete and marks benchmarks unavailable", () => {
  const availability = buildComparisonAvailability([
    cpu("CPU A", fullCpuSpecs, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(availability.completeness, AVAILABILITY_STATUS.partial);
  assert.equal(findSource(availability, "benchmark").status, AVAILABILITY_STATUS.unavailable);
  assert.deepEqual(findSource(availability, "benchmark").missingLabels, [
    "Geekbench 7 Multi-Core",
    "Geekbench 7 Single-Core",
  ]);
  assert.equal(
    findSource(availability, "specification").status,
    AVAILABILITY_STATUS.complete
  );
});

test("partial benchmark data reports a partial benchmark source", () => {
  const availability = buildComparisonAvailability(
    [
      cpu("CPU A", fullCpuSpecs, "AMD", 1),
      cpu("CPU B", fullCpuSpecs, "Intel", 2),
    ],
    {
      1: benchmarkState(benchmark("multi-core", 21000)),
      2: benchmarkState(benchmark("multi-core", 19000)),
    }
  );

  assert.equal(availability.completeness, AVAILABILITY_STATUS.partial);
  assert.equal(findSource(availability, "benchmark").status, AVAILABILITY_STATUS.partial);
  assert.equal(findSource(availability, "benchmark").presentCount, 1);
  assert.deepEqual(findSource(availability, "benchmark").missingLabels, [
    "Geekbench 7 Single-Core",
  ]);
  assert.equal(availability.notes.length, 1);
  assert.match(availability.notes[0], /^1 metric could not be compared/);
});

test("a metric missing on only one side is never counted as measurable", () => {
  const availability = buildComparisonAvailability([
    cpu("CPU A", { ...fullCpuSpecs, tdp_w: null }, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.deepEqual(findSource(availability, "specification").missingLabels, ["TDP"]);
  assert.equal(findSource(availability, "specification").presentCount, 4);
});

test("loading benchmark data is reported as an explicit loading state", () => {
  const availability = buildComparisonAvailability(
    [
      cpu("CPU A", fullCpuSpecs, "AMD", 1),
      cpu("CPU B", fullCpuSpecs, "Intel", 2),
    ],
    { 1: { status: "loading", results: null } }
  );

  assert.equal(availability.isLoading, true);
  assert.equal(availability.statusLabel, "LOADING VERIFIED DATA");
  assert.equal(availability.notes[0], "Verified benchmark data is still loading.");
});

test("GPU comparison reports that no GPU benchmark metrics exist", () => {
  const availability = buildComparisonAvailability([
    gpu("Card A", { memory_gb: 16, tdp_w: 300 }, "NVIDIA", 1),
    gpu("Card B", { memory_gb: 8, tdp_w: 250 }, "AMD", 2),
  ]);

  assert.equal(findSource(availability, "benchmark").expectedCount, 0);
  assert.equal(findSource(availability, "benchmark").status, AVAILABILITY_STATUS.unavailable);
  assert.equal(findSource(availability, "specification").presentCount, 2);
  assert.ok(
    availability.notes.includes(
      "GPU benchmark scores are not collected for these GPUs yet."
    )
  );
});

test("no usable values anywhere reports an unavailable completeness", () => {
  const availability = buildComparisonAvailability([
    cpu("CPU A", {}, "AMD", 1),
    cpu("CPU B", {}, "Intel", 2),
  ]);

  assert.equal(availability.completeness, AVAILABILITY_STATUS.unavailable);
  assert.equal(availability.statusLabel, "NOT COMPARABLE YET");
  assert.equal(availability.measurableCount, 0);
});

test("non-numeric and zero specification values are never treated as measurable", () => {
  const availability = buildComparisonAvailability([
    cpu("CPU A", { ...fullCpuSpecs, cores: 0, threads: "32" }, "AMD", 1),
    cpu("CPU B", { ...fullCpuSpecs, cores: 8, threads: 16 }, "Intel", 2),
  ]);

  assert.deepEqual(findSource(availability, "specification").missingLabels, [
    "Cores",
    "Threads",
  ]);
  assert.equal(findSource(availability, "specification").presentCount, 3);
});

test("lead groups attribute every measurable metric to exactly one side", () => {
  const insights = {
    insights: [
      {
        metric: "Cores",
        metricKey: "cores",
        winner: "cpuA",
        winnerName: "CPU A",
        direction: "higher",
        differencePercent: 33.3,
      },
      {
        metric: "TDP",
        metricKey: "tdp_w",
        winner: "cpuB",
        winnerName: "CPU B",
        direction: "lower",
        differencePercent: 20,
      },
      {
        metric: "Threads",
        metricKey: "threads",
        winner: "cpuA",
        winnerName: "CPU A",
        direction: "higher",
        differencePercent: 100,
      },
    ],
    ties: 1,
    tieDetails: [
      { metric: "Base Clock", metricKey: "base_clock_ghz", value: 3.2, format: "decimal", unit: "GHz" },
    ],
  };

  const lead = buildComparisonLeadGroups(insights, [
    cpu("CPU A"),
    cpu("CPU B"),
  ]);

  assert.equal(lead.groups.length, 2);
  assert.equal(lead.groups[0].winner, "cpuA");
  assert.equal(lead.groups[0].count, 2);
  assert.deepEqual(
    lead.groups[0].metrics.map((metric) => metric.label),
    ["Cores", "Threads"]
  );
  assert.equal(lead.groups[0].metrics[0].differenceLabel, "+33.3% higher");
  assert.equal(lead.groups[1].winner, "cpuB");
  assert.equal(lead.groups[1].metrics[0].differenceLabel, "20.0% lower");
  assert.equal(lead.tieCount, 1);
  assert.equal(lead.ties[0].label, "Base Clock");
  assert.equal(lead.ties[0].key, "base_clock_ghz");
  assert.equal(lead.ties[0].valueLabel.endsWith(" GHz"), true);
});

test("lead groups are empty when no metric is measurable", () => {
  const lead = buildComparisonLeadGroups(
    { insights: [], ties: 0, tieDetails: [] },
    [cpu("CPU A"), cpu("CPU B")]
  );

  assert.deepEqual(lead.groups, []);
  assert.equal(lead.tieCount, 0);
  assert.deepEqual(lead.ties, []);
});

test("lead groups tolerate a missing insights object", () => {
  const lead = buildComparisonLeadGroups(undefined, undefined);

  assert.deepEqual(lead.groups, []);
  assert.equal(lead.tieCount, 0);
});

test("decision summary reports the empty comparison state", () => {
  const summary = buildComparisonDecisionSummary([]);

  assert.equal(summary.status, DECISION_STATUS.empty);
  assert.equal(summary.overview, null);
  assert.equal(summary.availability, null);
  assert.equal(summary.benchmarkSupport, null);
  assert.equal(summary.canCompare, false);
  assert.deepEqual(summary.leadLines, []);
  assert.deepEqual(summary.limitations, []);
});

test("decision summary never declares an overall winner or a score", () => {
  const summary = buildComparisonDecisionSummary(
    [
      cpu("CPU A", { ...fullCpuSpecs, cores: 24, threads: 48 }, "AMD", 1),
      cpu("CPU B", fullCpuSpecs, "Intel", 2),
    ],
    { 1: fullCpuBenchmarks(24000), 2: fullCpuBenchmarks(18000) }
  );

  assert.equal("winner" in summary, false);
  assert.equal("bestHardware" in summary, false);
  assert.equal("score" in summary, false);
  assert.equal("ranking" in summary, false);
  assert.equal(summary.canCompare, true);
});

test("decision summary reports complete CPU data and verified benchmarks", () => {
  const summary = buildComparisonDecisionSummary(
    [
      cpu("CPU A", { ...fullCpuSpecs, cores: 24 }, "AMD", 1),
      cpu("CPU B", fullCpuSpecs, "Intel", 2),
    ],
    { 1: fullCpuBenchmarks(24000), 2: fullCpuBenchmarks(18000) }
  );

  assert.equal(summary.status, DECISION_STATUS.ready);
  assert.equal(summary.availability.completeness, AVAILABILITY_STATUS.complete);
  assert.equal(summary.benchmarkSupport.status, "available");
  assert.equal(summary.benchmarkSupport.label, "VERIFIED DATA");
  assert.equal(summary.benchmarkSupport.metrics.length, 2);
  assert.equal(summary.measurableCount, 7);
  assert.equal(summary.tieCount, 4);
  assert.equal(summary.unavailableCount, 0);
  assert.deepEqual(summary.leadLines, [
    "CPU A leads in 3 of 7 measurable metrics.",
  ]);
  assert.equal(summary.lead.groups[0].count, 3);
  assert.deepEqual(
    summary.lead.groups[0].metrics.map((metric) => metric.key),
    ["multi_core", "single_core", "cores"]
  );
});

test("decision summary keeps the benchmark section explicit when loading", () => {
  const summary = buildComparisonDecisionSummary(
    [
      cpu("CPU A", fullCpuSpecs, "AMD", 1),
      cpu("CPU B", fullCpuSpecs, "Intel", 2),
    ],
    { 1: { status: "loading", results: null } }
  );

  assert.equal(summary.status, DECISION_STATUS.loading);
  assert.equal(summary.benchmarkSupport.status, "loading");
  assert.equal(summary.benchmarkSupport.label, "LOADING");
  assert.ok(
    summary.limitations.includes("Verified benchmark data is still loading.")
  );
});

test("decision summary reports a tied comparison without inventing a winner", () => {
  const summary = buildComparisonDecisionSummary([
    cpu("CPU A", fullCpuSpecs, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);

  assert.equal(summary.canCompare, true);
  assert.deepEqual(summary.leadLines, [
    "All 5 measurable metrics are tied.",
  ]);
  assert.deepEqual(summary.lead.groups, []);
  assert.equal(summary.tieCount, 5);
  assert.equal(summary.benchmarkSupport.status, "unavailable");
  assert.equal(summary.benchmarkSupport.label, "NO DATA");
});

test("decision summary degrades gracefully when nothing is comparable", () => {
  const summary = buildComparisonDecisionSummary([
    cpu("CPU A", {}, "AMD", 1),
    cpu("CPU B", {}, "Intel", 2),
  ]);

  assert.equal(summary.canCompare, false);
  assert.equal(summary.measurableCount, 0);
  assert.deepEqual(summary.leadLines, []);
  assert.equal(summary.availability.completeness, AVAILABILITY_STATUS.unavailable);
  assert.equal(summary.limitations.length, 2);
});

test("decision summary keeps GPU comparisons explicit about missing benchmarks", () => {
  const summary = buildComparisonDecisionSummary([
    gpu("Card A", { memory_gb: 24, tdp_w: 320 }, "NVIDIA", 1),
    gpu("Card B", { memory_gb: 16, tdp_w: 260 }, "AMD", 2),
  ]);

  assert.equal(summary.status, DECISION_STATUS.ready);
  assert.equal(summary.overview.slotType, "GPU");
  assert.equal(summary.benchmarkSupport.status, "unavailable");
  assert.equal(summary.measurableCount, 2);
  assert.ok(
    summary.limitations.includes(
      "GPU benchmark scores are not collected for these GPUs yet."
    )
  );
});

test("GPU comparison never exposes benchmark metric rows", () => {
  const summary = buildComparisonDecisionSummary([
    gpu("Card A", { memory_gb: 24 }, "NVIDIA", 1),
    gpu("Card B", { memory_gb: 16 }, "AMD", 2),
  ]);

  assert.deepEqual(summary.benchmarkSupport.metrics, []);
});

test("comparison table specs are selected by hardware type", () => {
  assert.equal(getComparisonTableSpecs("GPU").length, 10);
  assert.equal(getComparisonTableSpecs("CPU").length, CPU_TABLE_SPECS.length);
  assert.deepEqual(
    getComparisonTableSpecs("GPU").map((spec) => spec.key),
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
    ]
  );
});

test("spec rows are empty for an incomplete comparison", () => {
  assert.deepEqual(buildComparisonSpecRows([]), []);
  assert.deepEqual(buildComparisonSpecRows([cpu("CPU A")]), []);
});

test("higher-is-better CPU rows mark only the leading cell", () => {
  const rows = buildComparisonSpecRows([
    cpu("CPU A", { ...fullCpuSpecs, cores: 24 }, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);
  const cores = findRow(rows, "cores");

  assert.equal(cores.state, "cpuA");
  assert.equal(cores.direction, "higher");
  assert.equal(cores.cells[0].className, "comparison-winner");
  assert.equal(cores.cells[1].className, "");
  assert.equal(cores.cells[0].marker, "Higher is better");
  assert.equal(cores.cells[1].marker, "");
  assert.equal(cores.cells[0].display, "24");
  assert.equal(cores.summary, "CPU A is higher");
});

test("lower-is-better rows mark the lower value with a text marker", () => {
  const rows = buildComparisonSpecRows([
    cpu("CPU A", { ...fullCpuSpecs, tdp_w: 65 }, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);
  const tdp = findRow(rows, "tdp_w");

  assert.equal(tdp.direction, "lower");
  assert.equal(tdp.state, "cpuA");
  assert.equal(tdp.cells[0].className, "comparison-winner");
  assert.equal(tdp.cells[1].className, "");
  assert.equal(tdp.cells[0].marker, "Lower is better");
  assert.equal(tdp.cells[0].display, "65 W");
  assert.equal(tdp.summary, "CPU A is lower");
});

test("equal values produce a tie row with no winner marker", () => {
  const rows = buildComparisonSpecRows([
    cpu("CPU A", { cores: 16 }, "AMD", 1),
    cpu("CPU B", { cores: 16 }, "Intel", 2),
  ]);
  const cores = findRow(rows, "cores");

  assert.equal(cores.state, "tie");
  assert.equal(cores.cells[0].className, "");
  assert.equal(cores.cells[1].className, "");
  assert.equal(cores.cells[0].marker, "");
  assert.equal(cores.summary, "Equal on both sides");
});

test("missing values stay explicit as unavailable cells", () => {
  const rows = buildComparisonSpecRows([
    cpu("CPU A", { cores: 16, tdp_w: null }, "AMD", 1),
    cpu("CPU B", { cores: null, tdp_w: 125 }, "Intel", 2),
  ]);

  assert.equal(findRow(rows, "cores").state, "unavailable");
  assert.equal(findRow(rows, "cores").summary, "Not comparable");
  assert.equal(findRow(rows, "cores").cells[1].state, "unavailable");
  assert.equal(findRow(rows, "cores").cells[1].display, "N/A");
  assert.equal(findRow(rows, "tdp_w").state, "unavailable");
});

test("informational CPU rows are never scored as a winner", () => {
  const rows = buildComparisonSpecRows([
    cpu("CPU A", { ...fullCpuSpecs, process_node_nm: 7, socket: "AM5" }, "AMD", 1),
    cpu("CPU B", fullCpuSpecs, "Intel", 2),
  ]);
  const process = findRow(rows, "process_node_nm");
  const socket = findRow(rows, "socket");

  assert.equal(process.direction, null);
  assert.equal(process.state, "informational");
  assert.equal(process.summary, "Informational only");
  assert.equal(process.cells[0].display, "7 nm");
  assert.equal(socket.state, "informational");
  assert.equal(socket.cells[0].display, "AM5");
});

test("GPU spec rows read hardware-level fields and format the release date", () => {
  const rows = buildComparisonSpecRows([
    {
      id: 1,
      name: "Card A",
      type: "GPU",
      manufacturer: "NVIDIA",
      architecture: "Ada Lovelace",
      release_date: "2025-01-30",
      specifications: { memory_gb: 24, memory_type: "GDDR6X" },
    },
    {
      id: 2,
      name: "Card B",
      type: "GPU",
      manufacturer: "AMD",
      architecture: "RDNA 3",
      release_date: "2023-12-12",
      specifications: { memory_gb: 16, memory_type: "GDDR6" },
    },
  ]);

  assert.equal(findRow(rows, "memory_gb").state, "cpuA");
  assert.equal(findRow(rows, "memory_gb").cells[0].display, "24 GB");
  assert.equal(findRow(rows, "memory_type").state, "informational");
  assert.equal(findRow(rows, "memory_type").cells[0].display, "GDDR6X");
  assert.equal(findRow(rows, "architecture").cells[0].display, "Ada Lovelace");
  assert.equal(findRow(rows, "release_date").cells[0].display, "Jan 30, 2025");
  assert.equal(findRow(rows, "release_date").cells[1].display, "Dec 12, 2023");
});

test("GPU lower-is-better rows mark length and TDP deterministically", () => {
  const rows = buildComparisonSpecRows([
    gpu("Card A", { tdp_w: 320, length_mm: 300 }, "NVIDIA", 1),
    gpu("Card B", { tdp_w: 260, length_mm: 267 }, "AMD", 2),
  ]);

  assert.equal(findRow(rows, "tdp_w").state, "cpuB");
  assert.equal(findRow(rows, "tdp_w").cells[1].marker, "Lower is better");
  assert.equal(findRow(rows, "length_mm").state, "cpuB");
});

test("the same hardware compared with itself is entirely tied", () => {
  const rows = buildComparisonSpecRows([
    cpu("Same", fullCpuSpecs, "AMD", 1),
    cpu("Same", fullCpuSpecs, "AMD", 2),
  ]);

  assert.deepEqual(
    rows.filter((row) => row.direction).map((row) => row.state),
    ["tie", "tie", "tie", "tie", "tie"]
  );
  assert.deepEqual(
    rows.map((row) => row.cells[0].className),
    rows.map(() => "")
  );
});