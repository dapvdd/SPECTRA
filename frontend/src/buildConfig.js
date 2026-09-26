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
  blocked: "blocked-single-hardware-context",
};

export const BUILD_CHAT_CONTEXT_LIMITATION =
  "POST /hardware/chat accepts HardwareChatRequest{hardware, question} with a " +
  "single HardwareContext and extra='forbid'. A CPU + GPU + user-context " +
  "payload cannot be transmitted without a backend contract change.";

const toChatComponentContext = (detail) => {
  if (!detail) {
    return null;
  }

  return {
    id: detail.id,
    name: detail.name,
    manufacturer: detail.manufacturer ?? null,
    type: detail.type ?? null,
    architecture: detail.architecture ?? null,
    release_date: detail.release_date ?? null,
    specifications: detail.specifications ?? {},
  };
};

export const buildBuildChatContext = (cpuDetail, gpuDetail, userContext) => ({
  integrationStatus: BUILD_CHAT_INTEGRATION_STATUS.blocked,
  isTransmittable: false,
  limitation: BUILD_CHAT_CONTEXT_LIMITATION,
  cpu: toChatComponentContext(cpuDetail),
  gpu: toChatComponentContext(gpuDetail),
  userContext: {
    useCase: userContext?.useCase ?? "Not specified",
    resolution: userContext?.resolution ?? "Not specified",
  },
});
