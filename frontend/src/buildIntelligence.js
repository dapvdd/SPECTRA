import { calculateListedTdpSum } from "./buildConfig.js";
import {
  BENCHMARK_COMPARISON_METRICS,
  normalizeBenchmarkResults,
} from "./performance.js";
import { formatReleaseDate } from "./hardwareCard.js";

export const BUILD_INTELLIGENCE_STATUS = {
  empty: "empty",
  loading: "loading",
  partial: "partial",
  ready: "ready",
  unavailable: "unavailable",
};

export const BUILD_INTELLIGENCE_STATUS_LABELS = {
  empty: "NO COMPONENTS SELECTED",
  loading: "LOADING VERIFIED DATA",
  partial: "PARTIAL DATA",
  ready: "VERIFIED DATA",
  unavailable: "NO VERIFIED DATA",
};

export const BUILD_SIGNAL_CATEGORIES = {
  performance: "performance",
  specification: "specification",
  power: "power",
  dataAvailability: "dataAvailability",
};

export const BUILD_SIGNAL_CATEGORY_ORDER = [
  BUILD_SIGNAL_CATEGORIES.performance,
  BUILD_SIGNAL_CATEGORIES.specification,
  BUILD_SIGNAL_CATEGORIES.power,
  BUILD_SIGNAL_CATEGORIES.dataAvailability,
];

export const BUILD_SIGNAL_CATEGORY_LABELS = {
  performance: "Performance data",
  specification: "Specification data",
  power: "Power signal",
  dataAvailability: "Data availability",
};

export const BUILD_SIGNAL_STATES = {
  available: "available",
  partial: "partial",
  loading: "loading",
  notLoaded: "notLoaded",
  notCollected: "notCollected",
  errored: "errored",
  unavailable: "unavailable",
  notSelected: "notSelected",
};

export const BUILD_SIGNAL_STATE_LABELS = {
  available: "Available",
  partial: "Partial data",
  loading: "Loading",
  notLoaded: "Not loaded",
  notCollected: "Not collected",
  errored: "Load failed",
  unavailable: "No data",
  notSelected: "Not selected",
};

export const BUILD_LIST_SECTIONS = [
  { key: "strengths", label: "Known strengths" },
  { key: "considerations", label: "Considerations" },
  { key: "dataGaps", label: "Data gaps" },
];

export const LISTED_TDP_LABEL = "Listed component TDP";
export const LISTED_TDP_NOTICE =
  "Listed component TDP values are manufacturer-listed ratings for the selected " +
  "components. They are not a measurement of system power draw and are not a " +
  "power supply requirement.";
export const SYSTEM_POWER_GAP = "No measured system power consumption data.";
export const GPU_BENCHMARK_NOTE =
  "GPU benchmark scores are not collected, so no verified GPU performance " +
  "description is produced.";
export const CACHE_GAP = "No verified CPU cache size data.";
export const THERMAL_GAP = "No thermal measurements.";
export const FRAME_RATE_GAP =
  "No frame rate or rendering performance estimate.";
export const BALANCE_GAP = "No component-balance or limiting-factor analysis.";
export const COMMERCIAL_GAP = "No price, value, or compatibility data.";
export const PLATFORM_GAP =
  "No motherboard, power supply, cooling, or case data.";
export const TDP_CONSIDERATION =
  "Listed component TDP should not be interpreted as total system power.";

const UNAVAILABLE_DISPLAY = "—";
const NOT_SELECTED_DISPLAY = "Not selected";

const CPU_SPEC_FIELDS = [
  { key: "cores", label: "Cores", unit: "", format: "integer" },
  { key: "threads", label: "Threads", unit: "", format: "integer" },
  { key: "base_clock_ghz", label: "Base Clock", unit: "GHz", format: "decimal" },
  { key: "boost_clock_ghz", label: "Boost Clock", unit: "GHz", format: "decimal" },
  { key: "tdp_w", label: "TDP", unit: "W", format: "integer" },
  { key: "socket", label: "Socket", unit: "", format: "text" },
  { key: "process_node_nm", label: "Process Node", unit: "nm", format: "decimal" },
];

const GPU_SPEC_FIELDS = [
  { key: "memory_gb", label: "VRAM", unit: "GB", format: "decimal" },
  { key: "memory_type", label: "Memory Type", unit: "", format: "text" },
  { key: "core_clock_mhz", label: "Core Clock", unit: "MHz", format: "integer" },
  { key: "boost_clock_mhz", label: "Boost Clock", unit: "MHz", format: "integer" },
  {
    key: "vram_bandwidth_gbps",
    label: "Memory Bandwidth",
    unit: "GB/s",
    format: "decimal",
  },
  { key: "tdp_w", label: "TDP", unit: "W", format: "integer" },
  { key: "interface", label: "Interface", unit: "", format: "text" },
  { key: "length_mm", label: "Length", unit: "mm", format: "integer" },
];

const isFiniteNumber = (value) =>
  typeof value === "number" && Number.isFinite(value);

const isPositiveNumber = (value) => isFiniteNumber(value) && value > 0;

const isNonEmptyText = (value) =>
  typeof value === "string" && value.trim() !== "";

const roundForDisplay = (value) => Math.round(value * 100) / 100;

const groupThousands = (digits) => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

const formatNumber = (value, format) => {
  const maximumFractionDigits = format === "integer" ? 0 : 2;
  const rounded = Number(Math.abs(value).toFixed(maximumFractionDigits));
  const [whole, fraction = ""] = String(rounded).split(".");
  const sign = value < 0 ? "-" : "";

  return fraction
    ? `${sign}${groupThousands(whole)}.${fraction}`
    : `${sign}${groupThousands(whole)}`;
};

const formatUnitValue = (value, unit) => {
  const formatted = formatNumber(value, "decimal");

  return unit ? `${formatted} ${unit}` : formatted;
};

const isSpecFieldPresent = (value, format) =>
  format === "text" ? isNonEmptyText(value) : isPositiveNumber(value);

const pushUnique = (list, value) => {
  if (isNonEmptyText(value) && !list.includes(value)) {
    list.push(value);
  }
};

const buildCoverage = (detail, fields) => {
  const specifications = detail?.specifications || {};
  const values = fields.map((spec) => ({
    key: spec.key,
    label: spec.label,
    present: isSpecFieldPresent(specifications[spec.key], spec.format),
  }));
  const presentCount = values.filter((value) => value.present).length;

  return {
    expectedCount: fields.length,
    presentCount,
    missingCount: fields.length - presentCount,
    isEmpty: presentCount === 0,
    isComplete: presentCount === fields.length,
    fieldLabels: values.map((value) => value.label),
  };
};

const buildMetadataCoverage = (detail) => {
  const architecture = isNonEmptyText(detail?.architecture)
    ? detail.architecture
    : null;
  const releaseDate = isNonEmptyText(detail?.release_date)
    ? formatReleaseDate(detail.release_date)
    : null;
  const presentCount = [architecture, releaseDate].filter(
    (value) => value !== null,
  ).length;

  return {
    expectedCount: 2,
    presentCount,
    isEmpty: presentCount === 0,
    isComplete: presentCount === 2,
    architecture,
    releaseDate,
  };
};

const buildBenchmarkCoverage = (benchmarkState) => {
  const performanceState = normalizeBenchmarkResults(benchmarkState);
  const metrics = BENCHMARK_COMPARISON_METRICS.map((metric) => {
    const record = performanceState[metric.key] ?? null;
    const score = isPositiveNumber(record?.score) ? record.score : null;

    return {
      key: metric.key,
      label: metric.title,
      availableValueCount: score === null ? 0 : 1,
      isAvailable: score !== null,
      display:
        score === null
          ? UNAVAILABLE_DISPLAY
          : isNonEmptyText(record.unit)
            ? `${formatNumber(score, "decimal")} ${record.unit}`
            : formatNumber(score, "decimal"),
    };
  });
  const availableCount = metrics.filter((metric) => metric.isAvailable).length;

  return {
    expectedCount: metrics.length,
    availableCount,
    metrics,
    hasAnyValue: availableCount > 0,
    isEmpty: availableCount === 0,
    isComplete: availableCount === metrics.length,
  };
};

const getRequestStatus = (requestStatus) =>
  isNonEmptyText(requestStatus) ? requestStatus : "success";

const buildSlotView = ({
  type,
  detail,
  selection,
  requestStatus,
  benchmarkState,
  specFields,
}) => {
  const isSelected = Boolean(selection ?? detail);
  const hasDetail = Boolean(detail);
  const status = getRequestStatus(requestStatus);
  const isErrored = isSelected && status === "error";
  const isPending =
    isSelected &&
    !isErrored &&
    (status === "loading" || status === "idle" || !hasDetail);
  const specifications = detail?.specifications || {};
  const listedTdp = isPositiveNumber(specifications.tdp_w)
    ? roundForDisplay(specifications.tdp_w)
    : null;
  const benchmarkCoverage = buildBenchmarkCoverage(benchmarkState);
  const benchmarkRequested = Boolean(benchmarkState);

  return {
    type,
    isSelected,
    hasDetail,
    isPending,
    isErrored,
    status,
    name: isNonEmptyText(detail?.name)
      ? detail.name
      : isNonEmptyText(selection?.name)
        ? selection.name
        : null,
    manufacturer: isNonEmptyText(detail?.manufacturer)
      ? detail.manufacturer
      : isNonEmptyText(selection?.manufacturer)
        ? selection.manufacturer
        : null,
    specification: buildCoverage(detail, specFields),
    metadata: buildMetadataCoverage(detail),
    benchmark: benchmarkCoverage,
    benchmarkRequested,
    benchmarkFailed: benchmarkRequested && benchmarkState?.status === "error",
    benchmarkLoading: benchmarkRequested && benchmarkState?.status === "loading",
    listedTdp,
    detail,
  };
};

const resolveBenchmarkState = (slot, allowNotCollected) => {
  if (!slot.isSelected) {
    return BUILD_SIGNAL_STATES.notSelected;
  }

  if (slot.benchmarkLoading) {
    return BUILD_SIGNAL_STATES.loading;
  }

  if (slot.benchmark.isComplete) {
    return BUILD_SIGNAL_STATES.available;
  }

  if (slot.benchmark.hasAnyValue) {
    return BUILD_SIGNAL_STATES.partial;
  }

  if (allowNotCollected) {
    return BUILD_SIGNAL_STATES.notCollected;
  }

  if (slot.benchmarkFailed) {
    return BUILD_SIGNAL_STATES.errored;
  }

  return slot.benchmarkRequested
    ? BUILD_SIGNAL_STATES.unavailable
    : BUILD_SIGNAL_STATES.notLoaded;
};

const resolveDataState = (slot, coverage) => {
  if (!slot.isSelected) {
    return BUILD_SIGNAL_STATES.notSelected;
  }

  if (slot.isPending) {
    return BUILD_SIGNAL_STATES.loading;
  }

  if (slot.isErrored) {
    return BUILD_SIGNAL_STATES.errored;
  }

  if (coverage.isEmpty) {
    return BUILD_SIGNAL_STATES.unavailable;
  }

  return coverage.isComplete
    ? BUILD_SIGNAL_STATES.available
    : BUILD_SIGNAL_STATES.partial;
};

const buildSignal = ({
  key,
  label,
  category,
  state,
  value = null,
  unit = "",
  detail = "",
}) => ({
  key,
  label,
  category,
  state,
  stateLabel: BUILD_SIGNAL_STATE_LABELS[state],
  value,
  display:
    value === null
      ? state === BUILD_SIGNAL_STATES.notSelected
        ? NOT_SELECTED_DISPLAY
        : UNAVAILABLE_DISPLAY
      : isFiniteNumber(value)
        ? formatUnitValue(value, unit)
        : String(value),
  detail,
});

const coverageValue = (coverage) =>
  `${coverage.presentCount} of ${coverage.expectedCount} stored fields`;

const benchmarkValue = (coverage) =>
  `${coverage.availableCount} of ${coverage.expectedCount} verified metrics`;

const isSlotDataReadable = (slot) =>
  slot.isSelected && !slot.isPending && !slot.isErrored;

const createEmptyModel = () => ({
  status: BUILD_INTELLIGENCE_STATUS.empty,
  statusLabel: BUILD_INTELLIGENCE_STATUS_LABELS.empty,
  isLoading: false,
  overview: {
    headline: "No components selected",
    slotLabel: "No components selected",
    cpuName: null,
    gpuName: null,
    hasCpu: false,
    hasGpu: false,
    isComplete: false,
    populatedSlotCount: 0,
  },
  signals: {
    performance: [],
    specification: [],
    power: [],
    dataAvailability: [],
  },
  signalList: [],
  power: {
    label: LISTED_TDP_LABEL,
    notice: LISTED_TDP_NOTICE,
    cpuListedTdp: null,
    gpuListedTdp: null,
    listedComponentTdp: null,
    isComplete: false,
    missingSlots: [],
  },
  benchmarkCoverage: {
    label: "Verified benchmark coverage",
    cpu: null,
    gpu: null,
    totalAvailableCount: 0,
    totalExpectedCount: 0,
  },
  completeness: {
    label: "Verified data coverage",
    availableCount: 0,
    expectedCount: 0,
    missingLabels: [],
    isComplete: false,
  },
  interpretations: [],
  known: [],
  unknown: [],
  strengths: [],
  considerations: [],
  dataGaps: [],
});

const buildBenchmarkCoverageBlock = (slot) =>
  slot.isSelected
    ? {
        availableCount: slot.benchmark.availableCount,
        expectedCount: slot.benchmark.expectedCount,
        metrics: slot.benchmark.metrics,
        stateLabel: slot.benchmark.isComplete
          ? BUILD_SIGNAL_STATE_LABELS.available
          : slot.benchmark.hasAnyValue
            ? BUILD_SIGNAL_STATE_LABELS.partial
            : BUILD_SIGNAL_STATE_LABELS.unavailable,
      }
    : null;

/* Geekbench 7 records are collected for CPUs only. A GPU slot contributes an
   expected count only once verified GPU benchmark records actually exist, so the
   aggregate never implies a GPU benchmark target that SPECTRA does not track. */
const expectedBenchmarkCount = (slot) => {
  if (!slot.isSelected) {
    return 0;
  }

  return slot.type === "CPU" || slot.benchmark.hasAnyValue
    ? slot.benchmark.expectedCount
    : 0;
};

export const buildBuildIntelligence = (cpuDetail = null, gpuDetail = null, options = {}) => {
  const {
    cpuSelected = null,
    gpuSelected = null,
    cpuRequestStatus = null,
    gpuRequestStatus = null,
    cpuBenchmarkState = null,
    gpuBenchmarkState = null,
  } = options ?? {};

  const cpu = buildSlotView({
    type: "CPU",
    detail: cpuDetail,
    selection: cpuSelected,
    requestStatus: cpuRequestStatus,
    benchmarkState: cpuBenchmarkState,
    specFields: CPU_SPEC_FIELDS,
  });
  const gpu = buildSlotView({
    type: "GPU",
    detail: gpuDetail,
    selection: gpuSelected,
    requestStatus: gpuRequestStatus,
    benchmarkState: gpuBenchmarkState,
    specFields: GPU_SPEC_FIELDS,
  });
  const model = createEmptyModel();
  const unknown = [];
  const interpretations = [];

  pushUnique(unknown, SYSTEM_POWER_GAP);
  pushUnique(unknown, THERMAL_GAP);
  pushUnique(unknown, FRAME_RATE_GAP);
  pushUnique(unknown, BALANCE_GAP);
  pushUnique(unknown, COMMERCIAL_GAP);
  pushUnique(unknown, PLATFORM_GAP);

  if (!cpu.isSelected && !gpu.isSelected) {
    model.unknown = unknown;
    model.interpretations = ["No components are selected for this build yet."];
    model.considerations = [
      "Select a CPU or a GPU to build verified intelligence for this build.",
    ];
    model.dataGaps = ["No component data is loaded for this build."];

    return model;
  }

  /* ---------- Overview ---------- */

  const describeSlot = (slot) =>
    isNonEmptyText(slot.name) ? `${slot.type} ${slot.name}` : `${slot.type} slot`;

  model.overview = {
    headline: [cpu, gpu]
      .filter((slot) => slot.isSelected)
      .map(describeSlot)
      .join(" + "),
    slotLabel:
      cpu.isSelected && gpu.isSelected
        ? "CPU + GPU configuration"
        : cpu.isSelected
          ? "CPU only · GPU slot empty"
          : "GPU only · CPU slot empty",
    cpuName: cpu.name,
    gpuName: gpu.name,
    hasCpu: cpu.isSelected,
    hasGpu: gpu.isSelected,
    isComplete: cpu.isSelected && gpu.isSelected,
    populatedSlotCount: (cpu.isSelected ? 1 : 0) + (gpu.isSelected ? 1 : 0),
  };

  /* ---------- Signals ---------- */

  const performanceSignals = [
    buildSignal({
      key: "cpu-benchmark",
      label: "CPU benchmark",
      category: BUILD_SIGNAL_CATEGORIES.performance,
      state: resolveBenchmarkState(cpu, false),
      value: cpu.isSelected && cpu.benchmark.hasAnyValue
        ? benchmarkValue(cpu.benchmark)
        : null,
      detail: "Verified Geekbench 7 records stored for the selected CPU.",
    }),
    buildSignal({
      key: "gpu-benchmark",
      label: "GPU benchmark",
      category: BUILD_SIGNAL_CATEGORIES.performance,
      state: resolveBenchmarkState(gpu, true),
      value: gpu.isSelected && gpu.benchmark.hasAnyValue
        ? benchmarkValue(gpu.benchmark)
        : null,
      detail: GPU_BENCHMARK_NOTE,
    }),
  ];

  const specificationSignals = [
    buildSignal({
      key: "cpu-specification",
      label: "CPU specification",
      category: BUILD_SIGNAL_CATEGORIES.specification,
      state: resolveDataState(cpu, cpu.specification),
      value: isSlotDataReadable(cpu) ? coverageValue(cpu.specification) : null,
      detail: `Stored CPU specification fields: ${cpu.specification.fieldLabels.join(", ")}.`,
    }),
    buildSignal({
      key: "cpu-metadata",
      label: "CPU metadata",
      category: BUILD_SIGNAL_CATEGORIES.specification,
      state: resolveDataState(cpu, cpu.metadata),
      value: isSlotDataReadable(cpu) ? coverageValue(cpu.metadata) : null,
      detail: "Architecture and release date recorded for the selected CPU.",
    }),
    buildSignal({
      key: "gpu-specification",
      label: "GPU specification",
      category: BUILD_SIGNAL_CATEGORIES.specification,
      state: resolveDataState(gpu, gpu.specification),
      value: isSlotDataReadable(gpu) ? coverageValue(gpu.specification) : null,
      detail: `Stored GPU specification fields: ${gpu.specification.fieldLabels.join(", ")}.`,
    }),
    buildSignal({
      key: "gpu-metadata",
      label: "GPU metadata",
      category: BUILD_SIGNAL_CATEGORIES.specification,
      state: resolveDataState(gpu, gpu.metadata),
      value: isSlotDataReadable(gpu) ? coverageValue(gpu.metadata) : null,
      detail: "Architecture and release date recorded for the selected GPU.",
    }),
  ];

  const powerSignals = [
    buildSignal({
      key: "cpu-listed-tdp",
      label: "Listed CPU TDP",
      category: BUILD_SIGNAL_CATEGORIES.power,
      state: resolveDataState(cpu, {
        isEmpty: cpu.listedTdp === null,
        isComplete: cpu.listedTdp !== null,
      }),
      value: cpu.listedTdp,
      unit: "W",
      detail: "Manufacturer-listed TDP rating for the selected CPU.",
    }),
    buildSignal({
      key: "gpu-listed-tdp",
      label: "Listed GPU TDP",
      category: BUILD_SIGNAL_CATEGORIES.power,
      state: resolveDataState(gpu, {
        isEmpty: gpu.listedTdp === null,
        isComplete: gpu.listedTdp !== null,
      }),
      value: gpu.listedTdp,
      unit: "W",
      detail: "Manufacturer-listed TDP rating for the selected GPU.",
    }),
  ];

  const listedComponentTdp = calculateListedTdpSum(cpu.detail, gpu.detail);
  const hasReportableTdpGap = (slot) =>
    slot.isSelected && !slot.isPending && !slot.isErrored && slot.listedTdp === null;
  const missingTdpSlots = [];

  if (hasReportableTdpGap(cpu)) {
    missingTdpSlots.push("CPU");
  }

  if (hasReportableTdpGap(gpu)) {
    missingTdpSlots.push("GPU");
  }

  powerSignals.push(
    buildSignal({
      key: "listed-component-tdp",
      label: LISTED_TDP_LABEL,
      category: BUILD_SIGNAL_CATEGORIES.power,
      state: !cpu.isSelected || !gpu.isSelected
        ? BUILD_SIGNAL_STATES.notSelected
        : listedComponentTdp === null
          ? BUILD_SIGNAL_STATES.unavailable
          : BUILD_SIGNAL_STATES.available,
      value: listedComponentTdp,
      unit: "W",
      detail:
        listedComponentTdp === null
          ? "A listed TDP sum requires a listed TDP value for both selected components."
          : LISTED_TDP_NOTICE,
    }),
  );

  const dataAvailabilitySignals = [
    buildSignal({
      key: "cpu-benchmark-coverage",
      label: "CPU benchmark coverage",
      category: BUILD_SIGNAL_CATEGORIES.dataAvailability,
      state: cpu.isSelected
        ? cpu.benchmark.isComplete
          ? BUILD_SIGNAL_STATES.available
          : cpu.benchmark.hasAnyValue
            ? BUILD_SIGNAL_STATES.partial
            : cpu.benchmarkFailed
              ? BUILD_SIGNAL_STATES.errored
              : cpu.benchmarkRequested
                ? BUILD_SIGNAL_STATES.unavailable
                : BUILD_SIGNAL_STATES.notLoaded
        : BUILD_SIGNAL_STATES.notSelected,
      value: isSlotDataReadable(cpu) ? benchmarkValue(cpu.benchmark) : null,
      detail: "Coverage is counted from stored Geekbench 7 records only.",
    }),
    buildSignal({
      key: "gpu-benchmark-coverage",
      label: "GPU benchmark coverage",
      category: BUILD_SIGNAL_CATEGORIES.dataAvailability,
      state: gpu.isSelected
        ? gpu.benchmark.isComplete
          ? BUILD_SIGNAL_STATES.available
          : gpu.benchmark.hasAnyValue
            ? BUILD_SIGNAL_STATES.partial
            : BUILD_SIGNAL_STATES.notCollected
        : BUILD_SIGNAL_STATES.notSelected,
      value: isSlotDataReadable(gpu) ? benchmarkValue(gpu.benchmark) : null,
      detail: GPU_BENCHMARK_NOTE,
    }),
  ];

  model.signals = {
    performance: performanceSignals,
    specification: specificationSignals,
    power: powerSignals,
    dataAvailability: dataAvailabilitySignals,
  };
  model.signalList = BUILD_SIGNAL_CATEGORY_ORDER.flatMap(
    (category) => model.signals[category],
  );

  /* ---------- Power ---------- */

  model.power = {
    label: LISTED_TDP_LABEL,
    notice: LISTED_TDP_NOTICE,
    cpuListedTdp: cpu.isSelected ? cpu.listedTdp : null,
    gpuListedTdp: gpu.isSelected ? gpu.listedTdp : null,
    listedComponentTdp,
    isComplete: listedComponentTdp !== null,
    missingSlots: missingTdpSlots,
  };

  /* ---------- Benchmark coverage ---------- */

  const gpuBenchmarkBlock = buildBenchmarkCoverageBlock(gpu);

  model.benchmarkCoverage = {
    label: "Verified benchmark coverage",
    cpu: buildBenchmarkCoverageBlock(cpu),
    gpu:
      gpuBenchmarkBlock === null
        ? null
        : {
            ...gpuBenchmarkBlock,
            stateLabel: gpu.benchmark.isEmpty
              ? BUILD_SIGNAL_STATE_LABELS.notCollected
              : gpuBenchmarkBlock.stateLabel,
          },
    totalAvailableCount:
      (cpu.isSelected ? cpu.benchmark.availableCount : 0) +
      (gpu.isSelected ? gpu.benchmark.availableCount : 0),
    totalExpectedCount:
      expectedBenchmarkCount(cpu) + expectedBenchmarkCount(gpu),
  };

  /* ---------- Completeness ---------- */

  const collectableSignals = model.signalList.filter(
    (signal) =>
      signal.state !== BUILD_SIGNAL_STATES.notSelected &&
      signal.state !== BUILD_SIGNAL_STATES.notCollected,
  );
  const availableSignals = collectableSignals.filter(
    (signal) =>
      signal.state === BUILD_SIGNAL_STATES.available ||
      signal.state === BUILD_SIGNAL_STATES.partial,
  );
  const missingSignals = collectableSignals.filter(
    (signal) =>
      signal.state !== BUILD_SIGNAL_STATES.available &&
      signal.state !== BUILD_SIGNAL_STATES.partial,
  );

  model.completeness = {
    label: "Verified data coverage",
    availableCount: availableSignals.length,
    expectedCount: collectableSignals.length,
    missingLabels: missingSignals.map((signal) => signal.label),
    isComplete:
      collectableSignals.length > 0 &&
      availableSignals.length === collectableSignals.length,
  };

  /* ---------- Status ---------- */

  let status;

  if (cpu.isPending || gpu.isPending) {
    status = BUILD_INTELLIGENCE_STATUS.loading;
  } else if (model.completeness.expectedCount === 0) {
    status = BUILD_INTELLIGENCE_STATUS.unavailable;
  } else if (model.completeness.availableCount === 0) {
    status = BUILD_INTELLIGENCE_STATUS.unavailable;
  } else if (model.completeness.isComplete) {
    status = BUILD_INTELLIGENCE_STATUS.ready;
  } else {
    status = BUILD_INTELLIGENCE_STATUS.partial;
  }

  model.status = status;
  model.statusLabel = BUILD_INTELLIGENCE_STATUS_LABELS[status];
  model.isLoading = status === BUILD_INTELLIGENCE_STATUS.loading;

  /* ---------- Interpretation ---------- */

  pushUnique(
    interpretations,
    cpu.isSelected && gpu.isSelected
      ? "This build contains both CPU and GPU selections."
      : cpu.isSelected
        ? "This build contains a CPU selection only; the GPU slot is empty."
        : "This build contains a GPU selection only; the CPU slot is empty.",
  );

  for (const slot of [cpu, gpu]) {
    if (!slot.isSelected) {
      continue;
    }

    if (slot.isPending) {
      pushUnique(
        interpretations,
        `${slot.type} detail data is still loading for this build.`,
      );
      continue;
    }

    if (slot.isErrored) {
      pushUnique(
        interpretations,
        `${slot.type} detail data could not be loaded for this build.`,
      );
      continue;
    }

    if (slot.type === "CPU") {
      pushUnique(
        interpretations,
        slot.benchmark.hasAnyValue
          ? "CPU benchmark data is available for this build."
          : slot.benchmarkRequested
            ? "No verified CPU benchmark record is available for this build."
            : "CPU benchmark records have not been loaded for this build.",
      );
    } else {
      pushUnique(
        interpretations,
        slot.benchmark.hasAnyValue
          ? "GPU benchmark data is available for this build."
          : "GPU benchmark data is not currently collected.",
      );
    }

    pushUnique(
      interpretations,
      `${slot.type} specification data covers ${slot.specification.presentCount} of ${slot.specification.expectedCount} stored ${slot.type} fields.`,
    );
  }

  const bothSlotsSelected = cpu.isSelected && gpu.isSelected;

  if (bothSlotsSelected && missingTdpSlots.length === 0) {
    pushUnique(interpretations, "Both listed component TDP values are available.");
    pushUnique(interpretations, "The listed TDP sum covers both selected components.");
  } else {
    for (const slot of missingTdpSlots) {
      pushUnique(
        interpretations,
        `${slot} listed TDP is unavailable, so the listed TDP sum is incomplete.`,
      );
    }

    if (!bothSlotsSelected) {
      pushUnique(
        interpretations,
        "A listed TDP sum requires both CPU and GPU slots to be populated.",
      );
    }
  }

  const countAvailable = (signals) =>
    signals.filter(
      (signal) =>
        signal.state === BUILD_SIGNAL_STATES.available ||
        signal.state === BUILD_SIGNAL_STATES.partial,
    ).length;

  if (countAvailable(performanceSignals) === 0 && countAvailable(specificationSignals) > 0) {
    pushUnique(
      interpretations,
      "The verified data for this build is specification-heavy rather than benchmark-heavy.",
    );
  }

  if (countAvailable(performanceSignals) > 0 && countAvailable(specificationSignals) === 0) {
    pushUnique(
      interpretations,
      "The verified data for this build is benchmark-heavy rather than specification-heavy.",
    );
  }

  model.interpretations = interpretations;

  /* ---------- Known ---------- */

  const known = [];

  for (const slot of [cpu, gpu]) {
    if (!slot.isSelected || slot.isPending) {
      continue;
    }

    if (!slot.specification.isEmpty) {
      pushUnique(
        known,
        `${slot.type} specification coverage is ${slot.specification.presentCount} of ${slot.specification.expectedCount} stored fields.`,
      );
    }

    if (slot.metadata.architecture !== null) {
      pushUnique(known, `${slot.type} architecture is recorded as ${slot.metadata.architecture}.`);
    }

    if (slot.metadata.releaseDate !== null) {
      pushUnique(
        known,
        `${slot.type} release date is recorded as ${slot.metadata.releaseDate}.`,
      );
    }

    if (slot.benchmark.hasAnyValue) {
      pushUnique(
        known,
        `${slot.type} benchmark coverage is ${slot.benchmark.availableCount} of ${slot.benchmark.expectedCount} verified metrics.`,
      );
    }

    if (slot.listedTdp !== null) {
      pushUnique(known, `Listed ${slot.type} TDP is ${formatUnitValue(slot.listedTdp, "W")}.`);
    }
  }

  if (listedComponentTdp !== null) {
    pushUnique(
      known,
      `${LISTED_TDP_LABEL} sums to ${formatUnitValue(listedComponentTdp, "W")}.`,
    );
  }

  model.known = known;

  /* ---------- Unknown ---------- */

  if (gpu.isSelected && !gpu.benchmark.hasAnyValue) {
    pushUnique(unknown, GPU_BENCHMARK_NOTE);
  }

  if (cpu.isSelected) {
    pushUnique(unknown, CACHE_GAP);
  }

  model.unknown = unknown;

  /* ---------- Strengths ---------- */

  const strengths = [];

  pushUnique(
    strengths,
    cpu.isSelected && gpu.isSelected
      ? "Both CPU and GPU slots are populated for this build."
      : cpu.isSelected
        ? "The CPU slot is populated for this build."
        : "The GPU slot is populated for this build.",
  );

  for (const slot of [cpu, gpu]) {
    if (!slot.isSelected) {
      continue;
    }

    if (slot.benchmark.hasAnyValue) {
      pushUnique(strengths, `Verified ${slot.type} benchmark records are available.`);
    }

    if (!slot.isPending && !slot.specification.isEmpty) {
      pushUnique(
        strengths,
        `${slot.type} specification data covers ${slot.specification.presentCount} of ${slot.specification.expectedCount} stored fields.`,
      );
    }
  }

  if (bothSlotsSelected && missingTdpSlots.length === 0) {
    pushUnique(strengths, "Both CPU and GPU have listed TDP values.");
  }

  if (
    cpu.hasDetail &&
    gpu.hasDetail &&
    cpu.metadata.isComplete &&
    gpu.metadata.isComplete
  ) {
    pushUnique(
      strengths,
      "Architecture and release date are recorded for both components.",
    );
  }

  model.strengths = strengths;

  /* ---------- Considerations ---------- */

  const considerations = [];

  if (!cpu.isSelected || !gpu.isSelected) {
    pushUnique(
      considerations,
      "Only one build slot is populated, so this is a partial configuration.",
    );
  }

  if (gpu.isSelected && !gpu.benchmark.hasAnyValue) {
    pushUnique(
      considerations,
      "GPU benchmark coverage is not collected, so this build is not described in verified GPU performance terms.",
    );
  }

  for (const slot of [cpu, gpu]) {
    if (!slot.isSelected) {
      continue;
    }

    if (slot.isErrored) {
      pushUnique(
        considerations,
        `${slot.type} detail data could not be loaded, so no verified signal is reported for that slot.`,
      );
      continue;
    }

    if (
      slot.type === "CPU" &&
      slot.benchmark.availableCount > 0 &&
      !slot.benchmark.isComplete
    ) {
      pushUnique(
        considerations,
        `CPU benchmark coverage is ${slot.benchmark.availableCount} of ${slot.benchmark.expectedCount} verified Geekbench 7 metrics.`,
      );
    }

    if (slot.type === "CPU" && !slot.benchmarkRequested && !slot.isPending) {
      pushUnique(
        considerations,
        "CPU benchmark records have not been loaded for this slot.",
      );
    }

    if (!slot.isPending && !slot.specification.isComplete) {
      pushUnique(
        considerations,
        `${slot.type} specification data is missing ${slot.specification.missingCount} of ${slot.specification.expectedCount} stored fields.`,
      );
    }
  }

  for (const slot of missingTdpSlots) {
    pushUnique(
      considerations,
      `${slot} listed TDP is unavailable, so the listed TDP sum cannot be computed.`,
    );
  }

  pushUnique(considerations, TDP_CONSIDERATION);

  if (model.completeness.expectedCount > 0 && !model.completeness.isComplete) {
    pushUnique(
      considerations,
      `Verified data coverage is ${model.completeness.availableCount} of ${model.completeness.expectedCount} reportable signals.`,
    );
  }

  model.considerations = considerations;

  /* ---------- Data gaps ---------- */

  const dataGaps = [
    "No measured system power data.",
    THERMAL_GAP,
    FRAME_RATE_GAP,
    BALANCE_GAP,
    COMMERCIAL_GAP,
  ];

  if (gpu.isSelected && !gpu.benchmark.hasAnyValue) {
    pushUnique(dataGaps, "No verified GPU gaming benchmark data.");
  }

  if (cpu.isSelected && !cpu.benchmark.hasAnyValue) {
    pushUnique(dataGaps, "No verified CPU benchmark data for this build.");
  }

  if (cpu.isSelected) {
    pushUnique(dataGaps, CACHE_GAP);
  }

  for (const label of model.completeness.missingLabels) {
    pushUnique(dataGaps, `No verified data is available for ${label}.`);
  }

  model.dataGaps = dataGaps;

  return model;
};