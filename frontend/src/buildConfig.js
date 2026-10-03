import { formatDetailValue } from "./detail.js";

export const BUILD_SLOTS = ["CPU", "GPU"];

export const BUILD_USE_CASES = [
  "Gaming",
  "Productivity",
  "AI / Compute",
  "General",
  "Not specified",
];

export const BUILD_RESOLUTIONS = ["Not specified", "1080p", "1440p", "4K"];

export const BUILD_USE_CASE_VALUES = {
  Gaming: "gaming",
  Productivity: "productivity",
  "AI / Compute": "ai_compute",
  General: "general",
  "Not specified": "unspecified",
};

export const BUILD_RESOLUTION_VALUES = {
  "Not specified": "unspecified",
  "1080p": "1080p",
  "1440p": "1440p",
  "4K": "4k",
};

export const BUILD_DETAIL_STATUS = {
  idle: "idle",
  loading: "loading",
  success: "success",
  error: "error",
};

const isFiniteNumber = (value) =>
  typeof value === "number" && Number.isFinite(value);

const isPositiveNumber = (value) => isFiniteNumber(value) && value > 0;

const roundForDisplay = (value) => Math.round(value * 100) / 100;

const isSupportedBuildType = (type) => BUILD_SLOTS.includes(type);

export const createBuildConfig = () => ({
  cpu: null,
  gpu: null,
});

const getSlot = (type) => (type === "GPU" ? "gpu" : "cpu");

export const setBuildCpu = (state, hardware) => {
  if (hardware?.type !== "CPU") {
    return state;
  }

  if (state.cpu?.id === hardware.id) {
    return state;
  }

  return { ...state, cpu: hardware };
};

export const setBuildGpu = (state, hardware) => {
  if (hardware?.type !== "GPU") {
    return state;
  }

  if (state.gpu?.id === hardware.id) {
    return state;
  }

  return { ...state, gpu: hardware };
};

export const clearBuildCpu = (state) =>
  state.cpu === null ? state : { ...state, cpu: null };

export const clearBuildGpu = (state) =>
  state.gpu === null ? state : { ...state, gpu: null };

export const clearBuildConfig = () => createBuildConfig();

export const getBuildSelection = (state, type) => {
  const slot = getSlot(type);
  return slot === "gpu" ? state.gpu : state.cpu;
};

export const isBuildComplete = (state) =>
  Boolean(state.cpu) && Boolean(state.gpu);

export const getBuildComponentAction = (state, hardware) => {
  if (!isSupportedBuildType(hardware?.type)) {
    return {
      isBuildSlot: false,
      alreadySelected: false,
      isSlotOccupied: false,
      actionLabel: "Add to Build",
      changeLabel: "Change CPU",
    };
  }

  const selected = getBuildSelection(state, hardware.type);
  const alreadySelected = selected?.id === hardware.id;
  const noun = hardware.type === "GPU" ? "GPU" : "CPU";

  return {
    isBuildSlot: true,
    alreadySelected,
    isSlotOccupied: Boolean(selected),
    actionLabel: alreadySelected
      ? `✓ ${noun} Selected`
      : selected
        ? `Change ${noun}`
        : "Add to Build",
    changeLabel: `Change ${noun}`,
  };
};

export const getBuildComponentSummary = (detail) => {
  const name = detail?.name || "N/A";
  const manufacturer = detail?.manufacturer || "N/A";

  if (!detail) {
    return { name: "Select hardware", manufacturer: "", subtitle: "" };
  }

  const specifications = detail.specifications || {};

  if (detail.type === "CPU") {
    const coreLabel = isPositiveNumber(specifications.cores)
      ? `${specifications.cores}C`
      : "";
    const threadLabel = isPositiveNumber(specifications.threads)
      ? `${specifications.threads}T`
      : "";
    const subtitle = [coreLabel, threadLabel].filter(Boolean).join(" / ");

    return { name, manufacturer, subtitle };
  }

  if (detail.type === "GPU") {
    const memoryLabel = isPositiveNumber(specifications.memory_gb)
      ? `${specifications.memory_gb} GB`
      : "";
    const typeLabel =
      typeof specifications.memory_type === "string" &&
      specifications.memory_type.trim() !== ""
        ? specifications.memory_type.trim()
        : "";
    const subtitle = [memoryLabel, typeLabel].filter(Boolean).join(" ");

    return { name, manufacturer, subtitle };
  }

  return { name, manufacturer, subtitle: "" };
};

export const getBuildCpuSpecs = (detail) => {
  const specifications = detail?.specifications || {};

  return [
    { label: "Cores", value: formatDetailValue(specifications.cores) },
    { label: "Threads", value: formatDetailValue(specifications.threads) },
    {
      label: "Base Clock",
      value: formatDetailValue(specifications.base_clock_ghz, "GHz"),
    },
    {
      label: "Boost Clock",
      value: formatDetailValue(specifications.boost_clock_ghz, "GHz"),
    },
    { label: "TDP", value: formatDetailValue(specifications.tdp_w, "W") },
    { label: "Socket", value: formatDetailValue(specifications.socket) },
    {
      label: "Process Node",
      value: formatDetailValue(specifications.process_node_nm, "nm"),
    },
  ];
};

export const getBuildGpuSpecs = (detail) => {
  const specifications = detail?.specifications || {};

  return [
    { label: "VRAM", value: formatDetailValue(specifications.memory_gb, "GB") },
    {
      label: "Memory Type",
      value: formatDetailValue(specifications.memory_type),
    },
    {
      label: "Core Clock",
      value: formatDetailValue(specifications.core_clock_mhz, "MHz"),
    },
    {
      label: "Boost Clock",
      value: formatDetailValue(specifications.boost_clock_mhz, "MHz"),
    },
    {
      label: "Bandwidth",
      value: formatDetailValue(specifications.vram_bandwidth_gbps, "GB/s"),
    },
    { label: "TDP", value: formatDetailValue(specifications.tdp_w, "W") },
    { label: "Interface", value: formatDetailValue(specifications.interface) },
    { label: "Architecture", value: formatDetailValue(detail?.architecture) },
    { label: "Length", value: formatDetailValue(specifications.length_mm, "mm") },
  ];
};

export const getBuildComponentSpecs = (detail) => {
  if (detail?.type === "CPU") {
    return getBuildCpuSpecs(detail);
  }

  if (detail?.type === "GPU") {
    return getBuildGpuSpecs(detail);
  }

  return [];
};

const getListedTdp = (detail) => {
  const value = detail?.specifications?.tdp_w;
  return isPositiveNumber(value) ? value : null;
};

export const calculateListedTdpSum = (cpuDetail, gpuDetail) => {
  const cpuTdp = getListedTdp(cpuDetail);
  const gpuTdp = getListedTdp(gpuDetail);

  if (cpuTdp === null || gpuTdp === null) {
    return null;
  }

  return roundForDisplay(cpuTdp + gpuTdp);
};

const pushFact = (facts, id, label, value) => {
  if (value === null || value === undefined || value === "") {
    return;
  }

  facts.push({ id, label, value });
};

export const getBuildFacts = (cpuDetail, gpuDetail) => {
  const facts = [];
  const cpuSpecs = cpuDetail?.specifications || {};
  const gpuSpecs = gpuDetail?.specifications || {};

  const coreCount = isPositiveNumber(cpuSpecs.cores) ? cpuSpecs.cores : null;
  const threadCount = isPositiveNumber(cpuSpecs.threads)
    ? cpuSpecs.threads
    : null;

  if (coreCount !== null && threadCount !== null) {
    pushFact(
      facts,
      "cpu-core-thread",
      "CPU cores / threads",
      `${coreCount} / ${threadCount}`
    );
  } else {
    if (coreCount !== null) {
      pushFact(facts, "cpu-cores", "CPU cores", formatDetailValue(coreCount));
    }

    if (threadCount !== null) {
      pushFact(
        facts,
        "cpu-threads",
        "CPU threads",
        formatDetailValue(threadCount)
      );
    }
  }

  if (isPositiveNumber(gpuSpecs.memory_gb)) {
    pushFact(
      facts,
      "gpu-vram",
      "GPU memory",
      formatDetailValue(gpuSpecs.memory_gb, "GB")
    );
  }

  if (isPositiveNumber(gpuSpecs.vram_bandwidth_gbps)) {
    pushFact(
      facts,
      "gpu-bandwidth",
      "GPU memory bandwidth",
      formatDetailValue(gpuSpecs.vram_bandwidth_gbps, "GB/s")
    );
  }

  const cpuTdp = getListedTdp(cpuDetail);
  const gpuTdp = getListedTdp(gpuDetail);

  if (cpuTdp !== null) {
    pushFact(
      facts,
      "cpu-tdp",
      "CPU listed TDP",
      formatDetailValue(roundForDisplay(cpuTdp), "W")
    );
  }

  if (gpuTdp !== null) {
    pushFact(
      facts,
      "gpu-tdp",
      "GPU listed TDP",
      formatDetailValue(roundForDisplay(gpuTdp), "W")
    );
  }

  const tdpSum = calculateListedTdpSum(cpuDetail, gpuDetail);

  if (tdpSum !== null) {
    pushFact(
      facts,
      "listed-tdp-sum",
      "Listed CPU TDP + GPU TDP",
      formatDetailValue(tdpSum, "W")
    );
  }

  return facts;
};

export const getBuildSummary = (state) => ({
  cpu: state.cpu
    ? {
        id: state.cpu.id,
        name: state.cpu.name,
        manufacturer: state.cpu.manufacturer || "N/A",
        isSelected: true,
      }
    : { id: null, name: "Select a CPU", manufacturer: "", isSelected: false },
  gpu: state.gpu
    ? {
        id: state.gpu.id,
        name: state.gpu.name,
        manufacturer: state.gpu.manufacturer || "N/A",
        isSelected: true,
      }
    : { id: null, name: "Select a GPU", manufacturer: "", isSelected: false },
  isComplete: isBuildComplete(state),
  relationshipLabel: "CPU + GPU configuration",
});

export const getBuildSlotChecklistItem = (type, selection, requestState) => {
  const status = requestState?.status || BUILD_DETAIL_STATUS.idle;

  if (!selection) {
    return { type, state: "empty", label: `Select a ${type} to continue` };
  }

  if (status === BUILD_DETAIL_STATUS.loading || status === BUILD_DETAIL_STATUS.idle) {
    return {
      type,
      state: "pending",
      label: `Loading stored ${type} details`,
    };
  }

  if (status === BUILD_DETAIL_STATUS.error) {
    return { type, state: "error", label: `Retry the ${type} details` };
  }

  return { type, state: "ready", label: `${selection.name} is ready` };
};

export const createBuildUserContext = () => ({
  useCase: "Not specified",
  resolution: "Not specified",
});

const isAllowedValue = (value, allowed) =>
  typeof value === "string" && allowed.includes(value);

export const setBuildUseCase = (context, value) =>
  isAllowedValue(value, BUILD_USE_CASES)
    ? { ...context, useCase: value }
    : context;

export const setBuildResolution = (context, value) =>
  isAllowedValue(value, BUILD_RESOLUTIONS)
    ? { ...context, resolution: value }
    : context;

export const createBuildDetailState = () => ({
  detailsBySlot: { CPU: null, GPU: null },
  requestStatesBySlot: {
    CPU: { status: BUILD_DETAIL_STATUS.idle, requestId: 0, message: "" },
    GPU: { status: BUILD_DETAIL_STATUS.idle, requestId: 0, message: "" },
  },
});

const isCurrentSlotRequest = (state, slot, requestId) =>
  state.requestStatesBySlot[slot]?.requestId === requestId;

const assertSlot = (slot) => {
  if (!BUILD_SLOTS.includes(slot)) {
    throw new Error(`Unsupported build slot: ${slot}`);
  }
};

export const startBuildDetailRequest = (state, slot, requestId) => {
  assertSlot(slot);

  return {
    detailsBySlot: { ...state.detailsBySlot, [slot]: null },
    requestStatesBySlot: {
      ...state.requestStatesBySlot,
      [slot]: { status: BUILD_DETAIL_STATUS.loading, requestId, message: "" },
    },
  };
};

export const completeBuildDetailRequest = (state, slot, requestId, detail) => {
  assertSlot(slot);

  if (!isCurrentSlotRequest(state, slot, requestId)) {
    return state;
  }

  return {
    detailsBySlot: { ...state.detailsBySlot, [slot]: detail },
    requestStatesBySlot: {
      ...state.requestStatesBySlot,
      [slot]: { status: BUILD_DETAIL_STATUS.success, requestId, message: "" },
    },
  };
};

export const failBuildDetailRequest = (
  state,
  slot,
  requestId,
  message = "Unable to load hardware details.",
) => {
  assertSlot(slot);

  if (!isCurrentSlotRequest(state, slot, requestId)) {
    return state;
  }

  return {
    detailsBySlot: state.detailsBySlot,
    requestStatesBySlot: {
      ...state.requestStatesBySlot,
      [slot]: {
        status: BUILD_DETAIL_STATUS.error,
        requestId,
        message,
      },
    },
  };
};

export const clearBuildSlotDetail = (state, slot) => {
  assertSlot(slot);

  return {
    detailsBySlot: { ...state.detailsBySlot, [slot]: null },
    requestStatesBySlot: {
      ...state.requestStatesBySlot,
      [slot]: {
        status: BUILD_DETAIL_STATUS.idle,
        requestId: 0,
        message: "",
      },
    },
  };
};

export const getBuildSlotRequestState = (state, slot) =>
  state.requestStatesBySlot[slot] ??
  createBuildDetailState().requestStatesBySlot[slot];

export const getBuildSlotDetail = (state, slot) => state.detailsBySlot[slot];

export const isBuildSlotBusy = (state, slot) =>
  getBuildSlotRequestState(state, slot).status ===
  BUILD_DETAIL_STATUS.loading;

export const isBuildSlotErrored = (state, slot) =>
  getBuildSlotRequestState(state, slot).status === BUILD_DETAIL_STATUS.error;

export const getBuildSlotErrorMessage = (state, slot) =>
  getBuildSlotRequestState(state, slot).message || "";

export const BUILD_CHAT_INTEGRATION_STATUS = {
  ready: "ready-build-chat-endpoint",
};

export const BUILD_CHAT_ENDPOINT_PATH = "/build/chat";

const CPU_SPEC_FIELDS = [
  "cores",
  "threads",
  "base_clock_ghz",
  "boost_clock_ghz",
  "tdp_w",
  "process_node_nm",
  "socket",
];

const GPU_SPEC_FIELDS = [
  "memory_gb",
  "memory_type",
  "core_clock_mhz",
  "boost_clock_mhz",
  "vram_bandwidth_gbps",
  "tdp_w",
  "interface",
  "length_mm",
];

const BENCHMARK_FIELDS = [
  "id",
  "hardware_id",
  "benchmark_name",
  "test_type",
  "score",
  "unit",
  "source",
  "recorded_at",
];

const isScalarSpecValue = (value) =>
  value === null ||
  (typeof value === "number" && Number.isFinite(value)) ||
  typeof value === "string" ||
  typeof value === "boolean";

const isUsableHardwareId = (value) =>
  typeof value === "number" && Number.isInteger(value) && value > 0;

const isNonEmptyText = (value) =>
  typeof value === "string" && value.trim() !== "";

export const isBuildChatContextReady = (cpuDetail, gpuDetail) =>
  isUsableHardwareId(cpuDetail?.id) &&
  isNonEmptyText(cpuDetail?.name) &&
  isUsableHardwareId(gpuDetail?.id) &&
  isNonEmptyText(gpuDetail?.name);

const pickBenchmarkRecords = (benchmarkPayload) => {
  if (Array.isArray(benchmarkPayload)) {
    return benchmarkPayload;
  }

  if (!benchmarkPayload || typeof benchmarkPayload !== "object") {
    return [];
  }

  if (Array.isArray(benchmarkPayload.benchmark_results)) {
    return benchmarkPayload.benchmark_results;
  }

  if (Array.isArray(benchmarkPayload.benchmarks)) {
    return benchmarkPayload.benchmarks;
  }

  if (Array.isArray(benchmarkPayload.results)) {
    return benchmarkPayload.results;
  }

  if (
    benchmarkPayload.performance &&
    Array.isArray(benchmarkPayload.performance.results)
  ) {
    return benchmarkPayload.performance.results;
  }

  return [];
};

const toBenchmarkContext = (records) =>
  pickBenchmarkRecords(records)
    .filter((record) => record !== null && typeof record === "object")
    .map((record) => {
      const benchmark = {};
      for (const field of BENCHMARK_FIELDS) {
        if (record[field] !== undefined) {
          benchmark[field] = record[field];
        }
      }
      return benchmark;
    });

const toSpecificationsContext = (detail, fields) => {
  const specifications = detail?.specifications || {};
  const context = {};

  for (const field of fields) {
    const value = specifications[field];

    if (value === undefined) {
      continue;
    }

    if (!isScalarSpecValue(value)) {
      continue;
    }

    context[field] = value;
  }

  return context;
};

const toBuildComponentContext = (detail, type, specFields, benchmarks) => {
  if (!detail) {
    return null;
  }

  return {
    id: detail.id,
    name: detail.name,
    manufacturer: detail.manufacturer ?? null,
    type,
    architecture: detail.architecture ?? null,
    release_date: detail.release_date ?? null,
    specifications: toSpecificationsContext(detail, specFields),
    benchmarks: toBenchmarkContext(benchmarks),
  };
};

export const toBuildCpuContext = (detail, benchmarks) =>
  toBuildComponentContext(detail, "CPU", CPU_SPEC_FIELDS, benchmarks);

export const toBuildGpuContext = (detail, benchmarks) =>
  toBuildComponentContext(detail, "GPU", GPU_SPEC_FIELDS, benchmarks);

const toUserContextValue = (value, allowedValues) =>
  typeof value === "string" && Object.hasOwn(allowedValues, value)
    ? allowedValues[value]
    : allowedValues["Not specified"];

export const toBuildUserContext = (userContext) => ({
  use_case: toUserContextValue(
    userContext?.useCase,
    BUILD_USE_CASE_VALUES
  ),
  resolution: toUserContextValue(
    userContext?.resolution,
    BUILD_RESOLUTION_VALUES
  ),
});

export const buildBuildChatContext = (
  cpuDetail,
  gpuDetail,
  userContext,
  benchmarksBySlot = {}
) => {
  if (!isBuildChatContextReady(cpuDetail, gpuDetail)) {
    throw new Error(
      "Build chat context requires a CPU and a GPU with usable detail data."
    );
  }

  return {
    cpu: toBuildCpuContext(cpuDetail, benchmarksBySlot.CPU),
    gpu: toBuildGpuContext(gpuDetail, benchmarksBySlot.GPU),
    context: toBuildUserContext(userContext),
  };
};

export const getBuildChatSnapshot = (cpuDetail, gpuDetail, userContext) => ({
  cpuId: cpuDetail?.id ?? null,
  gpuId: gpuDetail?.id ?? null,
  useCase: userContext?.useCase ?? "Not specified",
  resolution: userContext?.resolution ?? "Not specified",
});

const UNSPECIFIED_CONTEXT_LABEL = "Not specified";

export const getBuildChatContextSummary = (
  cpuDetail,
  gpuDetail,
  userContext
) => {
  const useCase = userContext?.useCase ?? UNSPECIFIED_CONTEXT_LABEL;
  const resolution = userContext?.resolution ?? UNSPECIFIED_CONTEXT_LABEL;
  const contextLabel = [useCase, resolution]
    .filter((value) => value !== UNSPECIFIED_CONTEXT_LABEL)
    .join(" · ");

  return {
    cpuName: getBuildComponentSummary(cpuDetail).name,
    gpuName: getBuildComponentSummary(gpuDetail).name,
    useCase,
    resolution,
    contextLabel: contextLabel || "No use case or resolution selected",
  };
};
