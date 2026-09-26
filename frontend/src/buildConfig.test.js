import test from "node:test";
import assert from "node:assert/strict";

import {
  BUILD_CHAT_INTEGRATION_STATUS,
  BUILD_RESOLUTIONS,
  BUILD_SLOTS,
  BUILD_USE_CASES,
  buildBuildChatContext,
  calculateListedTdpSum,
  clearBuildConfig,
  clearBuildCpu,
  clearBuildGpu,
  createBuildConfig,
  createBuildDetailState,
  createBuildUserContext,
  getBuildComponentAction,
  getBuildComponentSpecs,
  getBuildComponentSummary,
  getBuildFacts,
  getBuildSelection,
  getBuildSlotDetail,
  getBuildSlotErrorMessage,
  getBuildSlotRequestState,
  getBuildSummary,
  isBuildComplete,
  isBuildSlotBusy,
  isBuildSlotErrored,
  setBuildCpu,
  setBuildGpu,
  setBuildResolution,
  setBuildUseCase,
  startBuildDetailRequest,
  completeBuildDetailRequest,
  failBuildDetailRequest,
  clearBuildSlotDetail,
} from "./buildConfig.js";

const cpuItem = (id = 1, name = "Ryzen 7 7800X3D") => ({
  id,
  name,
  manufacturer: "AMD",
  type: "CPU",
});

const gpuItem = (id = 2, name = "GeForce RTX 5070 Ti") => ({
  id,
  name,
  manufacturer: "NVIDIA",
  type: "GPU",
});

const cpuDetail = (overrides = {}) => ({
  id: 1,
  name: "Ryzen 7 7800X3D",
  manufacturer: "AMD",
  type: "CPU",
  architecture: "Zen 4",
  release_date: "2023-04-06",
  specifications: {
    cores: 8,
    threads: 16,
    base_clock_ghz: 4.2,
    boost_clock_ghz: 5.0,
    tdp_w: 120,
    socket: "AM5",
    process_node_nm: 5,
    ...overrides,
  },
});

const gpuDetail = (overrides = {}) => ({
  id: 2,
  name: "GeForce RTX 5070 Ti",
  manufacturer: "NVIDIA",
  type: "GPU",
  architecture: "Blackwell",
  release_date: "2025-02-27",
  specifications: {
    memory_gb: 16,
    memory_type: "GDDR7",
    core_clock_mhz: 2017,
    boost_clock_mhz: 2512,
    vram_bandwidth_gbps: 896,
    tdp_w: 300,
    interface: "PCIe 5.0 x16",
    length_mm: 300,
    ...overrides,
  },
});

test("build config initializes with no CPU and no GPU", () => {
  assert.deepEqual(createBuildConfig(), { cpu: null, gpu: null });
  assert.equal(BUILD_SLOTS.join(","), "CPU,GPU");
});

test("CPU selection stores a CPU in the cpu slot only", () => {
  const state = setBuildCpu(createBuildConfig(), cpuItem());

  assert.equal(state.cpu.id, 1);
  assert.equal(state.gpu, null);
  assert.equal(isBuildComplete(state), false);
});

test("GPU selection stores a GPU in the gpu slot only", () => {
  const state = setBuildGpu(createBuildConfig(), gpuItem());

  assert.equal(state.gpu.id, 2);
  assert.equal(state.cpu, null);
  assert.equal(isBuildComplete(state), false);
});

test("a GPU cannot be stored in the CPU slot and a CPU cannot be stored in the GPU slot", () => {
  const withGpuInCpu = setBuildCpu(createBuildConfig(), gpuItem());
  assert.deepEqual(withGpuInCpu, { cpu: null, gpu: null });

  const withCpuInGpu = setBuildGpu(createBuildConfig(), cpuItem());
  assert.deepEqual(withCpuInGpu, { cpu: null, gpu: null });
});

test("replacing the CPU keeps the GPU selection untouched", () => {
  const state = setBuildGpu(setBuildCpu(createBuildConfig(), cpuItem(1)), gpuItem(2));
  const replaced = setBuildCpu(state, cpuItem(9, "Ryzen 9 9950X"));

  assert.equal(replaced.cpu.id, 9);
  assert.equal(replaced.cpu.name, "Ryzen 9 9950X");
  assert.equal(replaced.gpu.id, 2);
});

test("replacing the GPU keeps the CPU selection untouched", () => {
  const state = setBuildGpu(setBuildCpu(createBuildConfig(), cpuItem(1)), gpuItem(2));
  const replaced = setBuildGpu(state, gpuItem(8, "Arc B580"));

  assert.equal(replaced.gpu.id, 8);
  assert.equal(replaced.cpu.id, 1);
});

test("re-selecting the same hardware is a no-op that preserves state identity", () => {
  const state = setBuildCpu(createBuildConfig(), cpuItem());
  assert.equal(setBuildCpu(state, cpuItem()), state);
});

test("clearing the CPU keeps the GPU and vice versa", () => {
  const full = setBuildGpu(setBuildCpu(createBuildConfig(), cpuItem()), gpuItem());

  const cpuCleared = clearBuildCpu(full);
  assert.equal(cpuCleared.cpu, null);
  assert.equal(cpuCleared.gpu.id, 2);

  const gpuCleared = clearBuildGpu(full);
  assert.equal(gpuCleared.gpu, null);
  assert.equal(gpuCleared.cpu.id, 1);

  assert.deepEqual(clearBuildConfig(), { cpu: null, gpu: null });
  assert.equal(clearBuildCpu(cpuCleared), cpuCleared);
  assert.equal(clearBuildGpu(gpuCleared), gpuCleared);
});

test("build selection reads back by hardware type", () => {
  const state = setBuildGpu(setBuildCpu(createBuildConfig(), cpuItem()), gpuItem());

  assert.equal(getBuildSelection(state, "CPU").id, 1);
  assert.equal(getBuildSelection(state, "GPU").id, 2);
});

test("build summary reports missing components with select prompts", () => {
  const empty = getBuildSummary(createBuildConfig());

  assert.equal(empty.cpu.name, "Select a CPU");
  assert.equal(empty.cpu.isSelected, false);
  assert.equal(empty.gpu.name, "Select a GPU");
  assert.equal(empty.gpu.isSelected, false);
  assert.equal(empty.isComplete, false);
  assert.equal(empty.relationshipLabel, "CPU + GPU configuration");

  const cpuOnly = getBuildSummary(setBuildCpu(createBuildConfig(), cpuItem()));
  assert.equal(cpuOnly.cpu.name, "Ryzen 7 7800X3D");
  assert.equal(cpuOnly.cpu.manufacturer, "AMD");
  assert.equal(cpuOnly.gpu.name, "Select a GPU");

  const both = getBuildSummary(
    setBuildGpu(setBuildCpu(createBuildConfig(), cpuItem()), gpuItem())
  );
  assert.equal(both.isComplete, true);
  assert.equal(both.gpu.name, "GeForce RTX 5070 Ti");
  assert.equal(both.gpu.manufacturer, "NVIDIA");
});

test("component action labels distinguish add, change, and already selected", () => {
  const empty = createBuildConfig();
  const cpuAdd = getBuildComponentAction(empty, cpuItem());
  assert.equal(cpuAdd.isBuildSlot, true);
  assert.equal(cpuAdd.alreadySelected, false);
  assert.equal(cpuAdd.isSlotOccupied, false);
  assert.equal(cpuAdd.actionLabel, "Add to Build");

  const occupied = setBuildCpu(empty, cpuItem(1));
  const cpuChange = getBuildComponentAction(occupied, cpuItem(7, "Core i9"));
  assert.equal(cpuChange.isSlotOccupied, true);
  assert.equal(cpuChange.actionLabel, "Change CPU");

  const same = getBuildComponentAction(occupied, cpuItem(1));
  assert.equal(same.alreadySelected, true);
  assert.equal(same.actionLabel, "✓ CPU Selected");

  const gpuOccupied = setBuildGpu(empty, gpuItem(2));
  assert.equal(getBuildComponentAction(gpuOccupied, gpuItem(3)).actionLabel, "Change GPU");
  assert.equal(
    getBuildComponentAction(gpuOccupied, gpuItem(2)).actionLabel,
    "✓ GPU Selected"
  );
});

test("component action reports non-build hardware types as out of scope", () => {
  const action = getBuildComponentAction(createBuildConfig(), {
    id: 5,
    type: "CPU",
    name: "x",
  });

  assert.equal(action.isBuildSlot, true);
  assert.equal(
    getBuildComponentAction(createBuildConfig(), { id: 5, type: "PSU" }).isBuildSlot,
    false
  );
  assert.equal(
    getBuildComponentAction(createBuildConfig(), { id: 5 }).isBuildSlot,
    false
  );
});

test("component summary derives CPU core and thread labels from detail", () => {
  const summary = getBuildComponentSummary(cpuDetail());

  assert.equal(summary.name, "Ryzen 7 7800X3D");
  assert.equal(summary.manufacturer, "AMD");
  assert.equal(summary.subtitle, "8C / 16T");
});

test("component summary derives GPU memory subtitle from detail", () => {
  const summary = getBuildComponentSummary(gpuDetail());

  assert.equal(summary.name, "GeForce RTX 5070 Ti");
  assert.equal(summary.subtitle, "16 GB GDDR7");
});

test("component summary omits subtitles rather than inventing values", () => {
  const cpuNoCores = getBuildComponentSummary(cpuDetail({ cores: null, threads: null }));
  assert.equal(cpuNoCores.subtitle, "");

  const cpuThreadsOnly = getBuildComponentSummary(cpuDetail({ cores: null }));
  assert.equal(cpuThreadsOnly.subtitle, "16T");

  const gpuNoMemory = getBuildComponentSummary(gpuDetail({ memory_gb: null }));
  assert.equal(gpuNoMemory.subtitle, "GDDR7");

  const gpuNothing = getBuildComponentSummary(
    gpuDetail({ memory_gb: null, memory_type: null })
  );
  assert.equal(gpuNothing.subtitle, "");
});

test("CPU specification rows render N/A for missing values", () => {
  const rows = getBuildComponentSpecs(cpuDetail({ threads: null, socket: null }));
  const byLabel = Object.fromEntries(rows.map((row) => [row.label, row.value]));

  assert.equal(byLabel.Cores, "8");
  assert.equal(byLabel.Threads, "N/A");
  assert.equal(byLabel["Base Clock"], "4.2 GHz");
  assert.equal(byLabel["Boost Clock"], "5 GHz");
  assert.equal(byLabel.TDP, "120 W");
  assert.equal(byLabel.Socket, "N/A");
  assert.equal(byLabel["Process Node"], "5 nm");
});

test("GPU specification rows render all nine documented specifications", () => {
  const rows = getBuildComponentSpecs(gpuDetail());
  const byLabel = Object.fromEntries(rows.map((row) => [row.label, row.value]));

  assert.equal(rows.length, 9);
  assert.equal(byLabel.VRAM, "16 GB");
  assert.equal(byLabel["Memory Type"], "GDDR7");
  assert.equal(byLabel["Core Clock"], "2017 MHz");
  assert.equal(byLabel["Boost Clock"], "2512 MHz");
  assert.equal(byLabel.Bandwidth, "896 GB/s");
  assert.equal(byLabel.TDP, "300 W");
  assert.equal(byLabel.Interface, "PCIe 5.0 x16");
  assert.equal(byLabel.Architecture, "Blackwell");
  assert.equal(byLabel.Length, "300 mm");
});

test("GPU specification rows never convert missing values into zero", () => {
  const rows = getBuildComponentSpecs(
    gpuDetail({
      memory_gb: null,
      core_clock_mhz: null,
      vram_bandwidth_gbps: null,
      length_mm: null,
    })
  );
  const byLabel = Object.fromEntries(rows.map((row) => [row.label, row.value]));

  assert.equal(byLabel.VRAM, "N/A");
  assert.equal(byLabel["Core Clock"], "N/A");
  assert.equal(byLabel.Bandwidth, "N/A");
  assert.equal(byLabel.Length, "N/A");
  assert.equal(
    Object.values(byLabel).some((value) => value === "0"),
    false
  );
});

test("specification rows are empty for missing or unsupported detail", () => {
  assert.deepEqual(getBuildComponentSpecs(null), []);
  assert.deepEqual(getBuildComponentSpecs({ type: "PSU" }), []);
});

test("listed TDP sum adds CPU and GPU listed TDP values", () => {
  assert.equal(calculateListedTdpSum(cpuDetail(), gpuDetail()), 420);
  assert.equal(calculateListedTdpSum(cpuDetail({ tdp_w: 105 }), gpuDetail()), 405);
});

test("listed TDP sum is omitted when either TDP is missing or invalid", () => {
  assert.equal(calculateListedTdpSum(cpuDetail({ tdp_w: null }), gpuDetail()), null);
  assert.equal(calculateListedTdpSum(cpuDetail(), gpuDetail({ tdp_w: null })), null);
  assert.equal(calculateListedTdpSum(null, gpuDetail()), null);
  assert.equal(calculateListedTdpSum(cpuDetail(), null), null);
});

test("listed TDP sum rejects zero, negative, and non-numeric TDP values", () => {
  assert.equal(calculateListedTdpSum(cpuDetail({ tdp_w: 0 }), gpuDetail()), null);
  assert.equal(calculateListedTdpSum(cpuDetail(), gpuDetail({ tdp_w: 0 })), null);
  assert.equal(calculateListedTdpSum(cpuDetail({ tdp_w: -5 }), gpuDetail()), null);
  assert.equal(calculateListedTdpSum(cpuDetail({ tdp_w: "120" }), gpuDetail()), null);
  assert.equal(
    calculateListedTdpSum(cpuDetail({ tdp_w: Number.NaN }), gpuDetail()),
    null
  );
  assert.equal(
    calculateListedTdpSum(cpuDetail({ tdp_w: Number.POSITIVE_INFINITY }), gpuDetail()),
    null
  );
});

test("listed TDP sum avoids floating point display artifacts", () => {
  assert.equal(calculateListedTdpSum(cpuDetail({ tdp_w: 0.1 }), gpuDetail({ tdp_w: 0.2 })), 0.3);
  assert.equal(calculateListedTdpSum(cpuDetail({ tdp_w: 120.005 }), gpuDetail({ tdp_w: 0.005 })), 120.01);
});

test("build facts report only factual component values", () => {
  const facts = getBuildFacts(cpuDetail(), gpuDetail());
  const byId = Object.fromEntries(facts.map((fact) => [fact.id, fact]));

  assert.equal(byId["cpu-core-thread"].value, "8 / 16");
  assert.equal(byId["cpu-core-thread"].label, "CPU cores / threads");
  assert.equal(byId["gpu-vram"].value, "16 GB");
  assert.equal(byId["gpu-bandwidth"].value, "896 GB/s");
  assert.equal(byId["cpu-tdp"].value, "120 W");
  assert.equal(byId["gpu-tdp"].value, "300 W");
  assert.equal(byId["listed-tdp-sum"].value, "420 W");
});

test("build facts label the TDP total as a sum of listed component values", () => {
  const facts = getBuildFacts(cpuDetail(), gpuDetail());
  const sum = facts.find((fact) => fact.id === "listed-tdp-sum");

  assert.equal(sum.label, "Listed CPU TDP + GPU TDP");

  const text = facts.map((fact) => `${fact.label} ${fact.value}`).join(" | ");
  assert.equal(/system power|psu|gaming power/i.test(text), false);
});

test("build facts omit the TDP total when either TDP is unusable", () => {
  const facts = getBuildFacts(cpuDetail({ tdp_w: 0 }), gpuDetail());
  const ids = facts.map((fact) => fact.id);

  assert.equal(ids.includes("listed-tdp-sum"), false);
  assert.equal(ids.includes("cpu-tdp"), false);
  assert.equal(ids.includes("gpu-tdp"), true);
});

test("build facts degrade to partial core and thread facts", () => {
  const coresOnly = getBuildFacts(cpuDetail({ threads: null }), null);
  const ids = coresOnly.map((fact) => fact.id);

  assert.equal(ids.includes("cpu-core-thread"), false);
  assert.equal(ids.includes("cpu-cores"), true);
  assert.equal(ids.includes("cpu-threads"), false);

  const threadsOnly = getBuildFacts(cpuDetail({ cores: null }), null);
  assert.equal(
    threadsOnly.map((fact) => fact.id).includes("cpu-threads"),
    true
  );
});

test("build facts are empty when neither component is selected", () => {
  assert.deepEqual(getBuildFacts(null, null), []);
  assert.deepEqual(getBuildFacts(undefined, undefined), []);
});

test("build facts never fabricate values for a single selected component", () => {
  const cpuOnly = getBuildFacts(cpuDetail(), null);
  const ids = cpuOnly.map((fact) => fact.id);

  assert.equal(ids.includes("gpu-vram"), false);
  assert.equal(ids.includes("gpu-bandwidth"), false);
  assert.equal(ids.includes("listed-tdp-sum"), false);
});

test("user context initializes to not specified and accepts documented values", () => {
  assert.deepEqual(createBuildUserContext(), {
    useCase: "Not specified",
    resolution: "Not specified",
  });

  const gaming = setBuildUseCase(createBuildUserContext(), "Gaming");
  assert.equal(gaming.useCase, "Gaming");
  assert.equal(gaming.resolution, "Not specified");

  const qhd = setBuildResolution(gaming, "1440p");
  assert.equal(qhd.resolution, "1440p");
  assert.equal(qhd.useCase, "Gaming");
});

test("user context rejects undocumented values without mutating state", () => {
  const context = createBuildUserContext();

  assert.equal(setBuildUseCase(context, "Competitive Gaming"), context);
  assert.equal(setBuildResolution(context, "8K"), context);
  assert.equal(setBuildUseCase(context, null), context);
  assert.deepEqual(BUILD_USE_CASES, [
    "Gaming",
    "Productivity",
    "AI / Compute",
    "General",
    "Not specified",
  ]);
  assert.deepEqual(BUILD_RESOLUTIONS, ["Not specified", "1080p", "1440p", "4K"]);
});

test("changing user context never produces performance or estimate facts", () => {
  const context = setBuildResolution(
    setBuildUseCase(createBuildUserContext(), "AI / Compute"),
    "4K"
  );
  const facts = getBuildFacts(cpuDetail(), gpuDetail());

  assert.deepEqual(context, { useCase: "AI / Compute", resolution: "4K" });
  assert.equal(
    facts.some((fact) => /fps|estimate|prediction|bottleneck|score/i.test(fact.label)),
    false
  );
  assert.deepEqual(
    facts.map((fact) => fact.id),
    getBuildFacts(cpuDetail(), gpuDetail()).map((fact) => fact.id)
  );
});

test("build detail state initializes both slots to idle", () => {
  const state = createBuildDetailState();

  assert.equal(getBuildSlotRequestState(state, "CPU").status, "idle");
  assert.equal(getBuildSlotRequestState(state, "GPU").status, "idle");
  assert.equal(getBuildSlotDetail(state, "CPU"), null);
  assert.equal(getBuildSlotDetail(state, "GPU"), null);
});

test("a successful slot request stores the detail and clears loading", () => {
  const started = startBuildDetailRequest(createBuildDetailState(), "CPU", 1);
  assert.equal(isBuildSlotBusy(started, "CPU"), true);

  const done = completeBuildDetailRequest(started, "CPU", 1, cpuDetail());
  assert.equal(isBuildSlotBusy(done, "CPU"), false);
  assert.equal(isBuildSlotErrored(done, "CPU"), false);
  assert.equal(getBuildSlotDetail(done, "CPU").id, 1);
});

test("a failing slot request records an error message and no detail", () => {
  const started = startBuildDetailRequest(createBuildDetailState(), "GPU", 1);
  const failed = failBuildDetailRequest(started, "GPU", 1, "Failed to load GPU details.");

  assert.equal(isBuildSlotErrored(failed, "GPU"), true);
  assert.equal(isBuildSlotBusy(failed, "GPU"), false);
  assert.equal(getBuildSlotDetail(failed, "GPU"), null);
  assert.equal(getBuildSlotErrorMessage(failed, "GPU"), "Failed to load GPU details.");
});

test("a failed slot request allows a retry that reaches success", () => {
  let state = startBuildDetailRequest(createBuildDetailState(), "CPU", 1);
  state = failBuildDetailRequest(state, "CPU", 1, "boom");
  assert.equal(isBuildSlotErrored(state, "CPU"), true);

  state = startBuildDetailRequest(state, "CPU", 2);
  state = completeBuildDetailRequest(state, "CPU", 2, cpuDetail());

  assert.equal(isBuildSlotErrored(state, "CPU"), false);
  assert.equal(getBuildSlotDetail(state, "CPU").id, 1);
  assert.equal(getBuildSlotErrorMessage(state, "CPU"), "");
});

test("a stale CPU detail response is ignored", () => {
  const started = startBuildDetailRequest(createBuildDetailState(), "CPU", 1);
  const retried = startBuildDetailRequest(started, "CPU", 2);
  const stale = completeBuildDetailRequest(retried, "CPU", 1, {
    ...cpuDetail(),
    name: "Stale CPU",
  });

  assert.equal(stale, retried);
  assert.equal(getBuildSlotDetail(stale, "CPU"), null);
});

test("a stale GPU detail response is ignored", () => {
  const started = startBuildDetailRequest(createBuildDetailState(), "GPU", 1);
  const retried = startBuildDetailRequest(started, "GPU", 2);
  const stale = completeBuildDetailRequest(retried, "GPU", 1, {
    ...gpuDetail(),
    name: "Stale GPU",
  });

  assert.equal(stale, retried);
  assert.equal(getBuildSlotDetail(stale, "GPU"), null);
});

test("a stale failure response does not overwrite a newer success", () => {
  let state = startBuildDetailRequest(createBuildDetailState(), "GPU", 1);
  state = startBuildDetailRequest(state, "GPU", 2);
  state = completeBuildDetailRequest(state, "GPU", 2, gpuDetail());

  const stale = failBuildDetailRequest(state, "GPU", 1, "late failure");

  assert.equal(stale, state);
  assert.equal(getBuildSlotDetail(stale, "GPU").id, 2);
  assert.equal(isBuildSlotErrored(stale, "GPU"), false);
});

test("CPU and GPU slot requests are independent", () => {
  let state = startBuildDetailRequest(createBuildDetailState(), "CPU", 1);
  state = startBuildDetailRequest(state, "GPU", 1);
  state = completeBuildDetailRequest(state, "CPU", 1, cpuDetail());

  assert.equal(isBuildSlotBusy(state, "CPU"), false);
  assert.equal(isBuildSlotBusy(state, "GPU"), true);
  assert.equal(getBuildSlotDetail(state, "CPU").id, 1);
  assert.equal(getBuildSlotDetail(state, "GPU"), null);
});

test("clearing a slot resets its detail and request state", () => {
  let state = startBuildDetailRequest(createBuildDetailState(), "CPU", 1);
  state = completeBuildDetailRequest(state, "CPU", 1, cpuDetail());

  const cleared = clearBuildSlotDetail(state, "CPU");

  assert.equal(getBuildSlotDetail(cleared, "CPU"), null);
  assert.equal(getBuildSlotRequestState(cleared, "CPU").status, "idle");
});

test("starting a new slot request discards the previous detail", () => {
  let state = startBuildDetailRequest(createBuildDetailState(), "GPU", 1);
  state = completeBuildDetailRequest(state, "GPU", 1, gpuDetail());
  state = startBuildDetailRequest(state, "GPU", 2);

  assert.equal(getBuildSlotDetail(state, "GPU"), null);
  assert.equal(isBuildSlotBusy(state, "GPU"), true);
});

test("unsupported build slots are rejected", () => {
  assert.throws(
    () => startBuildDetailRequest(createBuildDetailState(), "PSU", 1),
    /Unsupported build slot/
  );
  assert.throws(
    () => clearBuildSlotDetail(createBuildDetailState(), "RAM"),
    /Unsupported build slot/
  );
});

test("build chat context is prepared but explicitly not transmittable", () => {
  const context = buildBuildChatContext(cpuDetail(), gpuDetail(), {
    useCase: "Gaming",
    resolution: "1440p",
  });

  assert.equal(context.isTransmittable, false);
  assert.equal(context.integrationStatus, BUILD_CHAT_INTEGRATION_STATUS.blocked);
  assert.equal(context.cpu.id, 1);
  assert.equal(context.gpu.id, 2);
  assert.equal(context.cpu.specifications.cores, 8);
  assert.equal(context.gpu.specifications.memory_gb, 16);
  assert.deepEqual(context.userContext, {
    useCase: "Gaming",
    resolution: "1440p",
  });
  assert.match(context.limitation, /single HardwareContext/);
});

test("build chat context tolerates missing components and context", () => {
  const context = buildBuildChatContext(null, gpuDetail(), null);

  assert.equal(context.cpu, null);
  assert.equal(context.gpu.id, 2);
  assert.deepEqual(context.userContext, {
    useCase: "Not specified",
    resolution: "Not specified",
  });
});

test("build configuration state is independent from comparison state", () => {
  const compareList = [cpuItem(1), cpuItem(3)];
  let build = setBuildCpu(createBuildConfig(), cpuItem(1));

  build = setBuildGpu(build, gpuItem(2));

  assert.equal(compareList.length, 2);
  assert.equal(compareList.every((item) => item.type === "CPU"), true);
  assert.equal(build.cpu.id, 1);
  assert.equal(build.gpu.id, 2);
  assert.equal(getBuildSelection(build, "GPU").type, "GPU");

  build = clearBuildCpu(build);
  assert.equal(compareList.length, 2);
  assert.equal(build.cpu, null);
});
