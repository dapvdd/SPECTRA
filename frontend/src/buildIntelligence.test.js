import test from "node:test";
import assert from "node:assert/strict";

import {
  BUILD_INTELLIGENCE_STATUS,
  BUILD_INTELLIGENCE_STATUS_LABELS,
  BUILD_SIGNAL_CATEGORIES,
  BUILD_SIGNAL_STATES,
  LISTED_TDP_LABEL,
  LISTED_TDP_NOTICE,
  buildBuildIntelligence,
} from "./buildIntelligence.js";
import { calculateListedTdpSum } from "./buildConfig.js";

const cpuDetail = (overrides = {}, specifications = {}) => ({
  id: 1,
  name: "Ryzen 7 7800X3D",
  type: "CPU",
  manufacturer: "AMD",
  architecture: "Zen 4",
  release_date: "2023-04-06",
  ...overrides,
  specifications: {
    cores: 8,
    threads: 16,
    base_clock_ghz: 4.2,
    boost_clock_ghz: 5,
    tdp_w: 120,
    socket: "AM5",
    process_node_nm: 5,
    ...specifications,
  },
});

const gpuDetail = (overrides = {}, specifications = {}) => ({
  id: 3361,
  name: "GeForce RTX 4070",
  type: "GPU",
  manufacturer: "NVIDIA",
  architecture: "Ada Lovelace",
  release_date: "2023-04-18",
  ...overrides,
  specifications: {
    memory_gb: 12,
    memory_type: "GDDR6X",
    core_clock_mhz: 1980,
    boost_clock_mhz: 2475,
    vram_bandwidth_gbps: 504,
    tdp_w: 200,
    interface: "PCIe 4.0 x16",
    length_mm: 244,
    ...specifications,
  },
});

const benchmark = (testType, score) => ({
  benchmark_name: "Geekbench 7",
  score,
  unit: "points",
  test_type: testType,
});

const cpuBenchmarks = (multiCore = 20000, singleCore = 1000) => ({
  status: "success",
  results: [benchmark("multi-core", multiCore), benchmark("single-core", singleCore)],
});

const findSignal = (model, key) =>
  model.signalList.find((signal) => signal.key === key) ?? null;

const collectStrings = (value, output = []) => {
  if (typeof value === "string") {
    output.push(value);
    return output;
  }

  if (Array.isArray(value)) {
    value.forEach((item) => collectStrings(item, output));
    return output;
  }

  if (value !== null && typeof value === "object") {
    Object.values(value).forEach((item) => collectStrings(item, output));
  }

  return output;
};

const FORBIDDEN_CLAIMS = [
  { pattern: /\d+(\.\d+)?\s*fps/i, reason: "frame rate claim" },
  { pattern: /\b\d+(\.\d+)?\s*%/, reason: "arbitrary percentage" },
  { pattern: /bottleneck/i, reason: "limiting-factor claim" },
  {
    pattern: /\b(consumes?|draws?|uses?)\s+\d+(\.\d+)?\s*(w|watts)\b/i,
    reason: "system power claim",
  },
  {
    pattern: /\b(best|optimal|excellent|superior|underpowered|overpowered|weak)\b/i,
    reason: "subjective ranking claim",
  },
  { pattern: /recommend/i, reason: "recommendation claim" },
  {
    pattern: /\b\d+(\.\d+)?\s*(w|watts)\b[^.]*\b(system|total|draw)\b/i,
    reason: "total system power claim",
  },
];

const FORBIDDEN_MODEL_KEYS = [
  "score",
  "scores",
  "rating",
  "ratings",
  "grade",
  "overall",
  "overallScore",
  "buildScore",
  "percent",
  "percentage",
  "scorePercent",
  "fps",
  "framesPerSecond",
  "bottleneck",
  "compatibility",
  "price",
  "value",
  "recommendation",
];

/* ---------- 1. empty build ---------- */

test("an empty build reports the empty state with no signals", () => {
  const model = buildBuildIntelligence(null, null);

  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.empty);
  assert.equal(model.statusLabel, BUILD_INTELLIGENCE_STATUS_LABELS.empty);
  assert.equal(model.isLoading, false);
  assert.equal(model.overview.hasCpu, false);
  assert.equal(model.overview.hasGpu, false);
  assert.equal(model.overview.populatedSlotCount, 0);
  assert.equal(model.overview.headline, "No components selected");
  assert.deepEqual(model.strengths, []);
  assert.deepEqual(model.known, []);
  assert.deepEqual(model.considerations, [
    "Select a CPU or a GPU to build verified intelligence for this build.",
  ]);
  assert.deepEqual(model.unknown.length > 0, true);
  assert.equal(model.completeness.expectedCount, 0);
  assert.equal(model.completeness.availableCount, 0);
  assert.equal(model.power.listedComponentTdp, null);
  assert.equal(model.benchmarkCoverage.cpu, null);
  assert.equal(model.benchmarkCoverage.gpu, null);
  assert.equal(model.signalList.length, 0);
  assert.deepEqual(
    Object.values(model.signals).flat(),
    [],
  );
  assert.ok(
    model.overview.headline.length > 0,
  );
});

test("undefined slots are treated exactly like an empty build", () => {
  assert.deepEqual(
    buildBuildIntelligence(undefined, undefined),
    buildBuildIntelligence(null, null),
  );
});

test("an empty build still names the data gaps it cannot fill", () => {
  const model = buildBuildIntelligence();

  assert.deepEqual(model.interpretations, [
    "No components are selected for this build yet.",
  ]);
  assert.deepEqual(model.dataGaps, [
    "No component data is loaded for this build.",
  ]);
  assert.ok(model.unknown.includes("No measured system power consumption data."));
});

/* ---------- 2. CPU only ---------- */

test("a CPU-only build reports the CPU slot and an empty GPU slot", () => {
  const model = buildBuildIntelligence(cpuDetail(), null, {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.equal(model.overview.hasCpu, true);
  assert.equal(model.overview.hasGpu, false);
  assert.equal(model.overview.isComplete, false);
  assert.equal(model.overview.populatedSlotCount, 1);
  assert.equal(model.overview.slotLabel, "CPU only · GPU slot empty");
  assert.equal(model.overview.headline, "CPU Ryzen 7 7800X3D");
  assert.equal(model.overview.cpuName, "Ryzen 7 7800X3D");
  assert.equal(model.overview.gpuName, null);
  assert.equal(findSignal(model, "gpu-benchmark").state, BUILD_SIGNAL_STATES.notSelected);
  assert.equal(
    findSignal(model, "gpu-benchmark-coverage").state,
    BUILD_SIGNAL_STATES.notSelected,
  );
  assert.ok(
    model.considerations.includes(
      "Only one build slot is populated, so this is a partial configuration.",
    ),
  );
  assert.equal(model.power.listedComponentTdp, null);
  assert.equal(model.power.isComplete, false);
});

/* ---------- 3. GPU only ---------- */

test("a GPU-only build reports the GPU slot and an empty CPU slot", () => {
  const model = buildBuildIntelligence(null, gpuDetail());

  assert.equal(model.overview.hasCpu, false);
  assert.equal(model.overview.hasGpu, true);
  assert.equal(model.overview.populatedSlotCount, 1);
  assert.equal(model.overview.slotLabel, "GPU only · CPU slot empty");
  assert.equal(model.overview.headline, "GPU GeForce RTX 4070");
  assert.equal(findSignal(model, "cpu-benchmark").state, BUILD_SIGNAL_STATES.notSelected);
  assert.equal(model.benchmarkCoverage.cpu, null);
  assert.ok(model.benchmarkCoverage.gpu);
  assert.equal(findSignal(model, "gpu-benchmark").state, BUILD_SIGNAL_STATES.notCollected);
  assert.equal(
    model.benchmarkCoverage.totalExpectedCount,
    0,
    "a GPU-only build must not imply a GPU benchmark target that SPECTRA does not collect",
  );
  assert.equal(model.benchmarkCoverage.totalAvailableCount, 0);
});

/* ---------- 4. CPU + GPU ---------- */

test("a complete build names both selections and both slots", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.equal(model.overview.isComplete, true);
  assert.equal(model.overview.populatedSlotCount, 2);
  assert.equal(model.overview.slotLabel, "CPU + GPU configuration");
  assert.equal(
    model.overview.headline,
    "CPU Ryzen 7 7800X3D + GPU GeForce RTX 4070",
  );
  assert.ok(
    model.interpretations.includes(
      "This build contains both CPU and GPU selections.",
    ),
  );
  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.ready);
  assert.equal(model.completeness.isComplete, true);
});

/* ---------- 5. CPU benchmark available ---------- */

test("available CPU benchmarks are reported as verified coverage", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(22050, 1100),
  });

  const signal = findSignal(model, "cpu-benchmark");

  assert.equal(signal.state, BUILD_SIGNAL_STATES.available);
  assert.equal(signal.stateLabel, "Available");
  assert.equal(signal.value, "2 of 2 verified metrics");
  assert.equal(model.benchmarkCoverage.cpu.availableCount, 2);
  assert.equal(model.benchmarkCoverage.cpu.expectedCount, 2);
  assert.equal(model.benchmarkCoverage.totalAvailableCount, 2);
  assert.deepEqual(
    model.benchmarkCoverage.cpu.metrics.map((metric) => metric.display),
    ["22,050 points", "1,100 points"],
  );
  assert.ok(
    model.interpretations.includes("CPU benchmark data is available for this build."),
  );
  assert.ok(model.strengths.includes("Verified CPU benchmark records are available."));
});

test("a partial CPU benchmark set is reported as partial, never as complete", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: { status: "success", results: [benchmark("multi-core", 22050)] },
  });

  assert.equal(findSignal(model, "cpu-benchmark").state, BUILD_SIGNAL_STATES.partial);
  assert.equal(model.benchmarkCoverage.cpu.availableCount, 1);
  assert.equal(model.benchmarkCoverage.cpu.stateLabel, "Partial data");
  assert.ok(
    model.considerations.includes(
      "CPU benchmark coverage is 1 of 2 verified Geekbench 7 metrics.",
    ),
  );
});

/* ---------- 6. CPU benchmark unavailable ---------- */

test("a CPU without benchmark records is reported as no data", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: { status: "success", results: [] },
  });

  assert.equal(findSignal(model, "cpu-benchmark").state, BUILD_SIGNAL_STATES.unavailable);
  assert.equal(findSignal(model, "cpu-benchmark").stateLabel, "No data");
  assert.ok(
    model.interpretations.includes(
      "No verified CPU benchmark record is available for this build.",
    ),
  );
  assert.ok(model.dataGaps.includes("No verified CPU benchmark data for this build."));
  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.partial);
});

test("a CPU benchmark request that never ran is reported as not loaded", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail());

  assert.equal(findSignal(model, "cpu-benchmark").state, BUILD_SIGNAL_STATES.notLoaded);
  assert.equal(findSignal(model, "cpu-benchmark").stateLabel, "Not loaded");
  assert.ok(
    model.interpretations.includes(
      "CPU benchmark records have not been loaded for this build.",
    ),
  );
});

test("a failed CPU benchmark request is reported without inventing values", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: { status: "error", message: "boom", results: null },
  });

  assert.equal(findSignal(model, "cpu-benchmark").state, BUILD_SIGNAL_STATES.errored);
  assert.equal(findSignal(model, "cpu-benchmark").stateLabel, "Load failed");
  assert.equal(findSignal(model, "cpu-benchmark").value, null);
  assert.equal(model.benchmarkCoverage.cpu.availableCount, 0);
});

test("invalid benchmark scores are never counted as verified data", () => {
  const rejected = [
    { status: "success", results: [benchmark("multi-core", 0)] },
    { status: "success", results: [benchmark("multi-core", -5)] },
    { status: "success", results: [benchmark("multi-core", Number.NaN)] },
    {
      status: "success",
      results: [{ ...benchmark("multi-core", 100), unit: "fps" }],
    },
    {
      status: "success",
      results: [{ ...benchmark("multi-core", 100), benchmark_name: "Synthetic" }],
    },
    {
      status: "success",
      results: [{ ...benchmark("multi-core", 100), test_type: "gaming" }],
    },
  ];

  for (const cpuBenchmarkState of rejected) {
    const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
      cpuBenchmarkState,
    });

    assert.equal(model.benchmarkCoverage.cpu.availableCount, 0);
  }
});

/* ---------- 7. GPU benchmark unavailable ---------- */

test("GPU benchmarks are reported as not collected, never as absent hardware data", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail());

  const signal = findSignal(model, "gpu-benchmark");

  assert.equal(signal.state, BUILD_SIGNAL_STATES.notCollected);
  assert.equal(signal.stateLabel, "Not collected");
  assert.equal(signal.value, null);
  assert.equal(model.benchmarkCoverage.gpu.availableCount, 0);
  assert.equal(model.benchmarkCoverage.gpu.stateLabel, "Not collected");
  assert.ok(
    model.interpretations.includes("GPU benchmark data is not currently collected."),
  );
  assert.ok(model.dataGaps.includes("No verified GPU gaming benchmark data."));
  assert.ok(
    model.considerations.includes(
      "GPU benchmark coverage is not collected, so this build is not described in verified GPU performance terms.",
    ),
  );
});

test("GPU benchmarks are never inferred from CPU benchmarks or GPU specs", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(30000, 1500),
  });

  assert.equal(findSignal(model, "gpu-benchmark").state, BUILD_SIGNAL_STATES.notCollected);
  assert.equal(model.benchmarkCoverage.gpu.availableCount, 0);
  assert.equal(model.benchmarkCoverage.totalAvailableCount, 2);
});

test("verified GPU benchmark records would be reported instead of assumed missing", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    gpuBenchmarkState: cpuBenchmarks(9000, 450),
  });

  assert.equal(findSignal(model, "gpu-benchmark").state, BUILD_SIGNAL_STATES.available);
  assert.equal(model.benchmarkCoverage.gpu.availableCount, 2);
  assert.equal(
    findSignal(model, "gpu-benchmark-coverage").state,
    BUILD_SIGNAL_STATES.available,
  );
  assert.ok(
    model.interpretations.includes("GPU benchmark data is available for this build."),
  );
  assert.ok(model.strengths.includes("Verified GPU benchmark records are available."));
  assert.equal(
    model.dataGaps.includes("No verified GPU gaming benchmark data."),
    false,
  );
});

/* ---------- 8. partial TDP ---------- */

test("a missing CPU TDP keeps the listed TDP sum unavailable", () => {
  const model = buildBuildIntelligence(cpuDetail({}, { tdp_w: null }), gpuDetail());

  assert.equal(model.power.cpuListedTdp, null);
  assert.equal(model.power.gpuListedTdp, 200);
  assert.equal(model.power.listedComponentTdp, null);
  assert.equal(model.power.isComplete, false);
  assert.deepEqual(model.power.missingSlots, ["CPU"]);
  assert.equal(findSignal(model, "cpu-listed-tdp").state, BUILD_SIGNAL_STATES.unavailable);
  assert.equal(
    findSignal(model, "listed-component-tdp").state,
    BUILD_SIGNAL_STATES.unavailable,
  );
  assert.ok(
    model.interpretations.includes(
      "CPU listed TDP is unavailable, so the listed TDP sum is incomplete.",
    ),
  );
  assert.ok(
    model.considerations.includes(
      "CPU listed TDP is unavailable, so the listed TDP sum cannot be computed.",
    ),
  );
});

test("a missing GPU TDP keeps the listed TDP sum unavailable", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail({}, { tdp_w: null }));

  assert.equal(model.power.cpuListedTdp, 120);
  assert.equal(model.power.listedComponentTdp, null);
  assert.deepEqual(model.power.missingSlots, ["GPU"]);
  assert.ok(
    model.interpretations.includes(
      "GPU listed TDP is unavailable, so the listed TDP sum is incomplete.",
    ),
  );
});

test("both TDP values missing produces no sum at all", () => {
  const model = buildBuildIntelligence(
    cpuDetail({}, { tdp_w: null }),
    gpuDetail({}, { tdp_w: null }),
  );

  assert.equal(model.power.listedComponentTdp, null);
  assert.deepEqual(model.power.missingSlots, ["CPU", "GPU"]);
  assert.equal(model.strengths.includes("Both CPU and GPU have listed TDP values."), false);
});

test("a single selected component never produces a listed TDP sum", () => {
  assert.equal(buildBuildIntelligence(cpuDetail(), null).power.listedComponentTdp, null);
  assert.equal(buildBuildIntelligence(null, gpuDetail()).power.listedComponentTdp, null);
});

/* ---------- 9. complete TDP ---------- */

test("complete listed TDP matches the existing TDP calculation exactly", () => {
  const cpu = cpuDetail();
  const gpu = gpuDetail();
  const model = buildBuildIntelligence(cpu, gpu);

  assert.equal(model.power.listedComponentTdp, calculateListedTdpSum(cpu, gpu));
  assert.equal(model.power.listedComponentTdp, 320);
  assert.equal(model.power.isComplete, true);
  assert.deepEqual(model.power.missingSlots, []);
  assert.equal(findSignal(model, "cpu-listed-tdp").display, "120 W");
  assert.equal(findSignal(model, "gpu-listed-tdp").display, "200 W");
  assert.equal(findSignal(model, "listed-component-tdp").display, "320 W");
  assert.equal(findSignal(model, "listed-component-tdp").label, LISTED_TDP_LABEL);
  assert.ok(model.strengths.includes("Both CPU and GPU have listed TDP values."));
  assert.ok(
    model.interpretations.includes("Both listed component TDP values are available."),
  );
  assert.ok(model.interpretations.includes("The listed TDP sum covers both selected components."));
  assert.ok(model.known.includes("Listed component TDP sums to 320 W."));
});

/* ---------- 10. missing specification values ---------- */

test("a single selected component never claims both TDP values are available", () => {
  const cpuOnly = buildBuildIntelligence(cpuDetail(), null);
  const gpuOnly = buildBuildIntelligence(null, gpuDetail());

  for (const model of [cpuOnly, gpuOnly]) {
    assert.equal(
      model.interpretations.includes("Both listed component TDP values are available."),
      false,
    );
    assert.equal(
      model.interpretations.includes("The listed TDP sum covers both selected components."),
      false,
    );
    assert.ok(
      model.interpretations.includes(
        "A listed TDP sum requires both CPU and GPU slots to be populated.",
      ),
    );
    assert.equal(
      model.strengths.includes("Both CPU and GPU have listed TDP values."),
      false,
    );
  }
});

test("missing specification fields are counted, never substituted", () => {
  const model = buildBuildIntelligence(
    cpuDetail({}, { cores: null, threads: null, tdp_w: null, socket: "" }),
    gpuDetail({}, { memory_type: null, length_mm: null }),
    { cpuBenchmarkState: cpuBenchmarks() },
  );

  const cpuSignal = findSignal(model, "cpu-specification");
  const gpuSignal = findSignal(model, "gpu-specification");

  assert.equal(cpuSignal.state, BUILD_SIGNAL_STATES.partial);
  assert.equal(cpuSignal.value, "3 of 7 stored fields");
  assert.equal(gpuSignal.state, BUILD_SIGNAL_STATES.partial);
  assert.equal(gpuSignal.value, "6 of 8 stored fields");
  assert.ok(
    model.considerations.includes(
      "CPU specification data is missing 4 of 7 stored fields.",
    ),
  );
  assert.ok(
    model.considerations.includes(
      "GPU specification data is missing 2 of 8 stored fields.",
    ),
  );
  assert.ok(
    model.dataGaps.includes("No verified data is available for Listed CPU TDP."),
  );
});

test("non-numeric and non-positive specification values are never counted", () => {
  const model = buildBuildIntelligence(
    cpuDetail({}, { cores: 0, threads: "16", base_clock_ghz: 0, boost_clock_ghz: -3 }),
    null,
  );

  assert.equal(findSignal(model, "cpu-specification").value, "3 of 7 stored fields");
  assert.equal(findSignal(model, "cpu-listed-tdp").state, BUILD_SIGNAL_STATES.available);
});

test("a component with no specification values at all reports no data", () => {
  const model = buildBuildIntelligence(
    cpuDetail({}, {
      cores: null,
      threads: null,
      base_clock_ghz: null,
      boost_clock_ghz: null,
      tdp_w: null,
      socket: null,
      process_node_nm: null,
    }),
    null,
  );

  assert.equal(findSignal(model, "cpu-specification").state, BUILD_SIGNAL_STATES.unavailable);
  assert.equal(findSignal(model, "cpu-metadata").state, BUILD_SIGNAL_STATES.available);
  assert.ok(
    model.interpretations.includes(
      "The verified data for this build is specification-heavy rather than benchmark-heavy.",
    ),
  );
  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.partial);
});

test("missing metadata fields are reported as partial coverage", () => {
  const model = buildBuildIntelligence(
    cpuDetail({ architecture: null, release_date: null }),
    gpuDetail({ architecture: null, release_date: null }),
  );

  assert.equal(findSignal(model, "cpu-metadata").state, BUILD_SIGNAL_STATES.unavailable);
  assert.equal(findSignal(model, "cpu-metadata").value, "0 of 2 stored fields");
  assert.equal(findSignal(model, "gpu-metadata").state, BUILD_SIGNAL_STATES.unavailable);
});

test("recorded metadata is surfaced as a verified known fact", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail());

  assert.ok(model.known.includes("CPU architecture is recorded as Zen 4."));
  assert.ok(model.known.includes("CPU release date is recorded as Apr 6, 2023."));
  assert.ok(model.known.includes("GPU architecture is recorded as Ada Lovelace."));
  assert.ok(model.known.includes("GPU release date is recorded as Apr 18, 2023."));
  assert.ok(
    model.strengths.includes(
      "Architecture and release date are recorded for both components.",
    ),
  );
});

/* ---------- 11. loading state ---------- */

test("a selected slot with no loaded detail reports the loading state", () => {
  const model = buildBuildIntelligence(null, null, {
    cpuSelected: { id: 1, name: "Ryzen 7 7800X3D", type: "CPU" },
    cpuRequestStatus: "loading",
  });

  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.loading);
  assert.equal(model.statusLabel, BUILD_INTELLIGENCE_STATUS_LABELS.loading);
  assert.equal(model.isLoading, true);
  assert.equal(model.overview.hasCpu, true);
  assert.equal(model.overview.populatedSlotCount, 1);
  assert.equal(model.overview.headline, "CPU Ryzen 7 7800X3D");
  assert.equal(findSignal(model, "cpu-specification").state, BUILD_SIGNAL_STATES.loading);
  assert.equal(findSignal(model, "cpu-metadata").state, BUILD_SIGNAL_STATES.loading);
  assert.equal(findSignal(model, "cpu-listed-tdp").state, BUILD_SIGNAL_STATES.loading);
  assert.equal(findSignal(model, "gpu-benchmark").state, BUILD_SIGNAL_STATES.notSelected);
  assert.ok(
    model.interpretations.includes(
      "CPU detail data is still loading for this build.",
    ),
  );
});

test("an idle slot request is treated as pending rather than ready", () => {
  const model = buildBuildIntelligence(null, null, {
    gpuSelected: { id: 2, name: "GeForce RTX 4070", type: "GPU" },
    gpuRequestStatus: "idle",
  });

  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.loading);
});

test("an idle request with loaded detail still reports a loading state", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuRequestStatus: "idle",
  });

  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.loading);
  assert.equal(model.isLoading, true);
});

test("a loading benchmark request reports a loading performance signal", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: { status: "loading", results: null },
  });

  assert.equal(findSignal(model, "cpu-benchmark").state, BUILD_SIGNAL_STATES.loading);
  assert.equal(findSignal(model, "cpu-benchmark").stateLabel, "Loading");
  assert.equal(findSignal(model, "gpu-benchmark").state, BUILD_SIGNAL_STATES.notCollected);
});

/* ---------- 12. data gap generation ---------- */

test("data gaps describe measurement limits rather than hardware weakness", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.deepEqual(model.dataGaps, [
    "No measured system power data.",
    "No thermal measurements.",
    "No frame rate or rendering performance estimate.",
    "No component-balance or limiting-factor analysis.",
    "No price, value, or compatibility data.",
    "No verified GPU gaming benchmark data.",
    "No verified CPU cache size data.",
  ]);
});

test("every data gap is a bounded absence statement", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail());
  const withMissingSignals = buildBuildIntelligence(
    cpuDetail({}, { tdp_w: null }),
    gpuDetail(),
  );

  for (const gap of [...model.dataGaps, ...withMissingSignals.dataGaps]) {
    assert.match(gap, /^No /);
  }
});

test("data gaps include every signal that cannot be reported", () => {
  const model = buildBuildIntelligence(cpuDetail({}, { tdp_w: null }), gpuDetail());

  for (const label of model.completeness.missingLabels) {
    assert.ok(
      model.dataGaps.includes(`No verified data is available for ${label}.`),
    );
  }
});

/* ---------- 13. strength generation ---------- */

test("strengths are generated only from verified populated data", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.deepEqual(model.strengths, [
    "Both CPU and GPU slots are populated for this build.",
    "Verified CPU benchmark records are available.",
    "CPU specification data covers 7 of 7 stored fields.",
    "GPU specification data covers 8 of 8 stored fields.",
    "Both CPU and GPU have listed TDP values.",
    "Architecture and release date are recorded for both components.",
  ]);
});

test("a CPU-only build never claims a populated GPU strength", () => {
  const model = buildBuildIntelligence(cpuDetail(), null, {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.ok(model.strengths.includes("The CPU slot is populated for this build."));
  assert.equal(model.strengths.includes("Both CPU and GPU slots are populated for this build."), false);
  assert.equal(model.strengths.includes("Both CPU and GPU have listed TDP values."), false);
});

test("a GPU-only build never claims a populated CPU strength", () => {
  const model = buildBuildIntelligence(null, gpuDetail());

  assert.ok(model.strengths.includes("The GPU slot is populated for this build."));
  assert.equal(model.strengths.includes("The CPU slot is populated for this build."), false);
});

/* ---------- 14. consideration generation ---------- */

test("considerations always separate listed TDP from system power", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail());

  assert.ok(
    model.considerations.includes(
      "Listed component TDP should not be interpreted as total system power.",
    ),
  );
  assert.equal(model.power.notice, LISTED_TDP_NOTICE);
  assert.ok(
    model.considerations.every(
      (consideration) => consideration.trim().length > 0,
    ),
  );
});

test("considerations report real coverage gaps without inventing severity", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail());

  assert.ok(
    model.considerations.includes(
      "Verified data coverage is 7 of 9 reportable signals.",
    ),
  );
  assert.deepEqual(model.completeness.missingLabels, [
    "CPU benchmark",
    "CPU benchmark coverage",
  ]);
});

test("a fully verified build still states its coverage boundary", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.equal(model.completeness.isComplete, true);
  assert.equal(model.completeness.expectedCount, 9);
  assert.equal(model.completeness.availableCount, 9);
  assert.deepEqual(model.completeness.missingLabels, []);
  assert.equal(
    model.considerations.includes(
      "Verified data coverage is 7 of 9 reportable signals.",
    ),
    false,
  );
  assert.ok(
    model.considerations.includes(
      "Listed component TDP should not be interpreted as total system power.",
    ),
  );
  assert.equal(model.benchmarkCoverage.totalExpectedCount, 2);
});

/* ---------- 15. no invented metrics ---------- */

test("no invented metric appears anywhere in the model", () => {
  const scenarios = [
    buildBuildIntelligence(),
    buildBuildIntelligence(cpuDetail(), null, { cpuBenchmarkState: cpuBenchmarks() }),
    buildBuildIntelligence(null, gpuDetail()),
    buildBuildIntelligence(cpuDetail(), gpuDetail(), { cpuBenchmarkState: cpuBenchmarks() }),
    buildBuildIntelligence(cpuDetail({}, { tdp_w: null }), gpuDetail()),
  ];

  for (const model of scenarios) {
    for (const text of collectStrings(model)) {
      for (const { pattern, reason } of FORBIDDEN_CLAIMS) {
        assert.equal(
          pattern.test(text),
          false,
          `${reason} found in: ${text}`,
        );
      }
    }
  }
});

test("no model exposes a score, rating, or percentage field", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  for (const key of FORBIDDEN_MODEL_KEYS) {
    assert.equal(key in model, false, `model must not expose ${key}`);
  }

  assert.deepEqual(
    Object.keys(model).sort(),
    [
      "benchmarkCoverage",
      "completeness",
      "considerations",
      "dataGaps",
      "interpretations",
      "isLoading",
      "known",
      "overview",
      "power",
      "signalList",
      "signals",
      "status",
      "statusLabel",
      "strengths",
      "unknown",
    ],
  );
});

test("the model exposes counts only, never a completion percentage", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.equal(
    Object.values(model.completeness).some(
      (value) => typeof value === "number" && !Number.isInteger(value),
    ),
    false,
  );
  assert.equal(model.completeness.availableCount, 9);
  assert.equal(model.completeness.expectedCount, 9);
});

test("signals are grouped into the documented categories", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.deepEqual(Object.keys(model.signals).sort(), [
    "dataAvailability",
    "performance",
    "power",
    "specification",
  ]);

  for (const category of Object.keys(model.signals)) {
    assert.ok(
      Object.hasOwn(BUILD_SIGNAL_CATEGORIES, category),
      `${category} must be a declared signal category`,
    );
  }

  assert.equal(model.signalList.length, Object.values(model.signals).flat().length);
});

test("every signal carries a readable state label for non-color reading", () => {
  const model = buildBuildIntelligence(cpuDetail({}, { tdp_w: null }), gpuDetail());

  for (const signal of model.signalList) {
    assert.ok(signal.stateLabel.length > 0);
    assert.ok(signal.label.length > 0);
    assert.ok(signal.detail.length > 0);
    assert.equal(
      model.signals[signal.category].some((item) => item.key === signal.key),
      true,
    );
  }
});

/* ---------- 16. no numeric build score ---------- */

test("build intelligence never produces a single overall number", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  const allowed = new Set([
    -1, 0, 1, 2, 7, 8, 9, 12, 16, 120, 200, 320, 20000, 1000, 22050, 1100,
  ]);
  const numbers = collectNumbers(model);

  assert.ok(numbers.length > 0);

  for (const value of numbers) {
    assert.equal(
      allowed.has(value),
      true,
      `unexpected numeric value in the model: ${value}`,
    );
  }

  assert.equal(
    numbers.some((value) => !Number.isInteger(value)),
    false,
    "the model must not contain fractional aggregate values",
  );
});

const collectNumbers = (value, output = []) => {
  if (typeof value === "number") {
    output.push(value);
    return output;
  }

  if (Array.isArray(value)) {
    value.forEach((item) => collectNumbers(item, output));
    return output;
  }

  if (value !== null && typeof value === "object") {
    Object.values(value).forEach((item) => collectNumbers(item, output));
  }

  return output;
};

/* ---------- 17. no limiting-factor claim ---------- */

test("build intelligence never claims a component limits the other", () => {
  const model = buildBuildIntelligence(
    cpuDetail({}, { cores: 8, threads: 16 }),
    gpuDetail({}, { memory_gb: 24, core_clock_mhz: 3000 }),
    { cpuBenchmarkState: cpuBenchmarks(22050, 1100) },
  );

  assert.equal(
    collectStrings(model).some((text) => /bottleneck|too weak|underpowered|too strong/i.test(text)),
    false,
  );
  assert.ok(
    model.unknown.includes("No component-balance or limiting-factor analysis."),
  );
});

test("a stronger GPU never changes the reported CPU signals", () => {
  const weakGpu = buildBuildIntelligence(cpuDetail(), gpuDetail({}, { memory_gb: 8 }));
  const strongGpu = buildBuildIntelligence(cpuDetail(), gpuDetail({}, { memory_gb: 24 }));

  assert.deepEqual(weakGpu.signals.performance, strongGpu.signals.performance);
  assert.deepEqual(
    weakGpu.signals.specification.find((signal) => signal.key === "cpu-specification"),
    strongGpu.signals.specification.find((signal) => signal.key === "cpu-specification"),
  );
});

/* ---------- 18. no frame rate claim ---------- */

test("build intelligence never reports or estimates a frame rate", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.equal(collectStrings(model).some((text) => /fps|frame ?rate|frames per/i.test(text) && !/No frame rate/i.test(text)), false);
  assert.ok(
    model.dataGaps.includes("No frame rate or rendering performance estimate."),
  );
});

test("the recorded use case never produces a performance estimate", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.deepEqual(Object.keys(model).includes("useCase"), false);
  assert.deepEqual(Object.keys(model).includes("resolution"), false);
});

/* ---------- 19. listed TDP is not system power ---------- */

test("listed TDP is explicitly distinguished from measured system power", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail());

  assert.equal(model.power.label, LISTED_TDP_LABEL);
  assert.equal(model.power.notice, LISTED_TDP_NOTICE);
  assert.match(model.power.notice, /not a measurement of system power draw/i);
  assert.match(model.power.notice, /not a power supply requirement/i);
  assert.ok(
    collectStrings(model).includes(
      "Listed component TDP should not be interpreted as total system power.",
    ),
  );
  assert.equal(
    findSignal(model, "listed-component-tdp").detail,
    LISTED_TDP_NOTICE,
  );
});

test("the listed TDP sum is only produced when both ratings are numeric", () => {
  const pairs = [
    [cpuDetail(), gpuDetail(), 320],
    [cpuDetail({}, { tdp_w: 0 }), gpuDetail(), null],
    [cpuDetail({}, { tdp_w: -10 }), gpuDetail(), null],
    [cpuDetail({}, { tdp_w: "120" }), gpuDetail(), null],
    [cpuDetail(), gpuDetail({}, { tdp_w: 0 }), null],
    [cpuDetail({}, { tdp_w: 105 }), gpuDetail({}, { tdp_w: 200.5 }), 305.5],
  ];

  for (const [cpu, gpu, expected] of pairs) {
    assert.equal(
      buildBuildIntelligence(cpu, gpu).power.listedComponentTdp,
      expected,
      `unexpected listed TDP sum for ${JSON.stringify(cpu.specifications.tdp_w)} / ${JSON.stringify(gpu.specifications.tdp_w)}`,
    );
  }
});

test("a pending slot never reports a listed TDP gap", () => {
  const model = buildBuildIntelligence(null, null, {
    cpuSelected: { id: 1, name: "Ryzen 7 7800X3D", type: "CPU" },
    cpuRequestStatus: "loading",
  });

  assert.deepEqual(model.power.missingSlots, []);
  assert.equal(
    model.considerations.some((line) => line.includes("listed TDP is unavailable")),
    false,
  );
  assert.equal(
    model.interpretations.some((line) => line.includes("listed TDP sum is incomplete")),
    false,
  );
  assert.equal(findSignal(model, "cpu-specification").value, null);
  assert.equal(findSignal(model, "cpu-metadata").value, null);
  assert.equal(findSignal(model, "cpu-listed-tdp").value, null);
});

test("an errored slot reports the load failure instead of missing data", () => {
  const model = buildBuildIntelligence(null, null, {
    gpuSelected: { id: 2, name: "GeForce RTX 4070", type: "GPU" },
    gpuRequestStatus: "error",
  });

  assert.equal(model.status, BUILD_INTELLIGENCE_STATUS.unavailable);
  assert.deepEqual(model.power.missingSlots, []);
  assert.ok(
    model.considerations.includes(
      "GPU detail data could not be loaded, so no verified signal is reported for that slot.",
    ),
  );
  assert.ok(
    model.interpretations.includes(
      "GPU detail data could not be loaded for this build.",
    ),
  );
  assert.equal(findSignal(model, "gpu-specification").state, BUILD_SIGNAL_STATES.errored);
  assert.equal(findSignal(model, "gpu-specification").value, null);
  assert.equal(findSignal(model, "gpu-metadata").value, null);
  assert.equal(findSignal(model, "gpu-listed-tdp").value, null);
  assert.equal(
    model.considerations.some((line) => line.includes("listed TDP is unavailable")),
    false,
  );
});

test("a readable slot still reports a real TDP gap", () => {
  const model = buildBuildIntelligence(
    cpuDetail(),
    gpuDetail({}, { tdp_w: null }),
  );

  assert.deepEqual(model.power.missingSlots, ["GPU"]);
  assert.ok(
    model.considerations.includes(
      "GPU listed TDP is unavailable, so the listed TDP sum cannot be computed.",
    ),
  );
});

/* ---------- 20. deterministic output ---------- */

test("identical inputs produce byte-identical output", () => {
  const inputs = [
    [null, null, {}],
    [cpuDetail(), null, { cpuBenchmarkState: cpuBenchmarks() }],
    [null, gpuDetail(), {}],
    [
      cpuDetail(),
      gpuDetail(),
      { cpuBenchmarkState: cpuBenchmarks(), cpuRequestStatus: "success" },
    ],
    [cpuDetail({}, { tdp_w: null }), gpuDetail(), {}],
  ];

  for (const [cpu, gpu, options] of inputs) {
    const first = JSON.stringify(buildBuildIntelligence(cpu, gpu, options));
    const second = JSON.stringify(buildBuildIntelligence(cpu, gpu, options));

    assert.equal(first, second);
    assert.deepEqual(buildBuildIntelligence(cpu, gpu, options), buildBuildIntelligence(cpu, gpu, options));
  }
});

test("the model is JSON serializable without loss", () => {
  const model = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  assert.deepEqual(JSON.parse(JSON.stringify(model)), model);
});

test("option objects are never mutated by the builder", () => {
  const options = { cpuBenchmarkState: cpuBenchmarks() };
  const snapshot = JSON.stringify(options);

  buildBuildIntelligence(cpuDetail(), gpuDetail(), options);
  buildBuildIntelligence(cpuDetail(), gpuDetail(), options);

  assert.equal(JSON.stringify(options), snapshot);
});

test("input details are never mutated by the builder", () => {
  const cpu = cpuDetail();
  const gpu = gpuDetail();
  const cpuSnapshot = JSON.stringify(cpu);
  const gpuSnapshot = JSON.stringify(gpu);

  buildBuildIntelligence(cpu, gpu, { cpuBenchmarkState: cpuBenchmarks() });

  assert.equal(JSON.stringify(cpu), cpuSnapshot);
  assert.equal(JSON.stringify(gpu), gpuSnapshot);
});

test("repeated builds over time never change the reported values", () => {
  const first = buildBuildIntelligence(cpuDetail(), gpuDetail(), {
    cpuBenchmarkState: cpuBenchmarks(),
  });

  for (let index = 0; index < 25; index += 1) {
    assert.deepEqual(
      buildBuildIntelligence(cpuDetail(), gpuDetail(), {
        cpuBenchmarkState: cpuBenchmarks(),
      }),
      first,
    );
  }
});