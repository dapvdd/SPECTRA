import test from "node:test";
import assert from "node:assert/strict";

import {
  BUILD_SLOTS,
  clearBuildComponent,
  clearBuildSlotDetail,
  completeBuildDetailRequest,
  createBuildConfig,
  createBuildDetailState,
  getBuildComponentAction,
  getBuildComponentSpecs,
  getBuildSelection,
  getBuildSlotDetail,
  getBuildSlotRequestState,
  getBuildSummary,
  setBuildComponent,
  startBuildDetailRequest,
} from "./buildConfig.js";

const items = {
  CPU: { id: 1, name: "Ryzen 7 7800X3D", manufacturer: "AMD", type: "CPU",
    specifications: { cores: 8, threads: 16, tdp_w: 120, socket: "AM5" } },
  GPU: { id: 2, name: "GeForce RTX 5070 Ti", manufacturer: "NVIDIA", type: "GPU",
    specifications: { memory_gb: 16, tdp_w: 300, interface: "PCIe 5.0 x16" } },
  RAM: { id: 3, name: "Vengeance 32GB", manufacturer: "Corsair", type: "RAM",
    specifications: { ddr_generation: "DDR5", capacity_gb: 32, speed_mhz: 5600, modules: 2 } },
  STORAGE: { id: 4, name: "980 Pro 1TB", manufacturer: "Samsung", type: "STORAGE",
    specifications: { storage_type: "NVMe", capacity_gb: 1024, interface: "PCIe 4.0 x4" } },
  MOTHERBOARD: { id: 5, name: "Z690-A", manufacturer: "ASUS", type: "MOTHERBOARD",
    specifications: { socket: "LGA1700", chipset: "Z690", ram_type: "DDR5",
      ram_slots: 4, max_ram_gb: 128, m2_slots: 3, sata_ports: 4, pcie_slots: 2 } },
  PSU: { id: 6, name: "RM750x", manufacturer: "Corsair", type: "PSU",
    specifications: { wattage: 750, efficiency_rating: "80 Plus Gold", modular: 1 } },
};

/* ---- six slots ---- */

test("BUILD_SLOTS covers the six build categories in order", () => {
  assert.deepEqual(BUILD_SLOTS, [
    "CPU", "GPU", "RAM", "STORAGE", "MOTHERBOARD", "PSU",
  ]);
});

test("createBuildConfig initializes all six slots to null", () => {
  assert.deepEqual(createBuildConfig(), {
    cpu: null, gpu: null, ram: null, storage: null, motherboard: null, psu: null,
  });
});

test("setBuildComponent stores each category in its own slot", () => {
  let state = createBuildConfig();
  for (const type of BUILD_SLOTS) {
    state = setBuildComponent(state, items[type]);
  }

  assert.equal(state.cpu.id, 1);
  assert.equal(state.gpu.id, 2);
  assert.equal(state.ram.id, 3);
  assert.equal(state.storage.id, 4);
  assert.equal(state.motherboard.id, 5);
  assert.equal(state.psu.id, 6);
});

test("setBuildComponent rejects hardware whose type does not match the slot", () => {
  let state = setBuildComponent(createBuildConfig(), items.GPU);
  // A GPU can only enter the gpu slot; the ram slot ignores it.
  state = setBuildComponent(state, items.GPU);
  assert.equal(state.gpu.id, 2);
  assert.equal(state.ram, null);

  // Unknown types are ignored entirely.
  const stray = setBuildComponent(createBuildConfig(), {
    id: 9, type: "MONITOR", name: "Odd", manufacturer: "X",
  });
  assert.deepEqual(stray, createBuildConfig());
});

test("setBuildComponent re-selecting the same item preserves state identity", () => {
  const state = setBuildComponent(createBuildConfig(), items.RAM);
  assert.equal(setBuildComponent(state, items.RAM), state);
});

test("setBuildComponent replaces a slot without touching other slots", () => {
  const state = setBuildComponent(
    setBuildComponent(createBuildConfig(), items.CPU),
    items.RAM,
  );
  const replaced = setBuildComponent(state, {
    ...items.RAM, id: 33, name: "Trident 32GB",
  });

  assert.equal(replaced.ram.id, 33);
  assert.equal(replaced.cpu.id, 1);
});

test("clearBuildComponent empties exactly the requested slot", () => {
  let state = createBuildConfig();
  for (const type of BUILD_SLOTS) {
    state = setBuildComponent(state, items[type]);
  }

  state = clearBuildComponent(state, "RAM");
  assert.equal(state.ram, null);
  assert.equal(state.cpu.id, 1);
  assert.equal(state.psu.id, 6);

  // Clearing an empty slot preserves state identity.
  assert.equal(clearBuildComponent(state, "RAM"), state);
});

test("clearBuildComponent rejects unsupported slots", () => {
  assert.throws(
    () => clearBuildComponent(createBuildConfig(), "MONITOR"),
    /Unsupported build slot/,
  );
});

test("getBuildSelection reads back per type", () => {
  const state = setBuildComponent(createBuildConfig(), items.MOTHERBOARD);

  assert.equal(getBuildSelection(state, "MOTHERBOARD").id, 5);
  assert.equal(getBuildSelection(state, "PSU"), null);
});

test("getBuildSummary reports all six slots with select prompts", () => {
  const empty = getBuildSummary(createBuildConfig());

  assert.equal(empty.cpu.name, "Select a CPU");
  assert.equal(empty.ram.name, "Select a RAM");
  assert.equal(empty.storage.name, "Select a Storage");
  assert.equal(empty.motherboard.name, "Select a Motherboard");
  assert.equal(empty.psu.name, "Select a PSU");
  assert.equal(empty.isComplete, false);

  let full = createBuildConfig();
  for (const type of BUILD_SLOTS) {
    full = setBuildComponent(full, items[type]);
  }
  const summary = getBuildSummary(full);

  assert.equal(summary.cpu.isSelected, true);
  assert.equal(summary.gpu.isSelected, true);
  assert.equal(summary.ram.isSelected, true);
  assert.equal(summary.storage.isSelected, true);
  assert.equal(summary.motherboard.isSelected, true);
  assert.equal(summary.psu.isSelected, true);
  assert.equal(summary.isComplete, true);
});

test("component action labels work for every new slot", () => {
  const empty = createBuildConfig();

  const ramAdd = getBuildComponentAction(empty, items.RAM);
  assert.equal(ramAdd.isBuildSlot, true);
  assert.equal(ramAdd.actionLabel, "Add to Build");

  const occupied = setBuildComponent(empty, items.PSU);
  assert.equal(
    getBuildComponentAction(occupied, items.PSU).actionLabel,
    "✓ PSU Selected",
  );
  assert.equal(
    getBuildComponentAction(occupied, { ...items.PSU, id: 66 }).actionLabel,
    "Change PSU",
  );
});

/* ---- build spec strips per category ---- */

test("getBuildComponentSpecs returns memory specs for RAM", () => {
  const specs = getBuildComponentSpecs(items.RAM);
  const labels = specs.map((s) => s.label);

  assert.ok(labels.includes("Capacity"));
  assert.ok(labels.includes("DDR Generation"));
  assert.ok(!labels.includes("Cores"));
  assert.ok(!labels.includes("Threads"));
});

test("getBuildComponentSpecs returns storage specs without CPU fields", () => {
  const specs = getBuildComponentSpecs(items.STORAGE);
  const labels = specs.map((s) => s.label);

  assert.ok(labels.includes("Storage Type"));
  assert.ok(labels.includes("Interface"));
  assert.ok(!labels.includes("Socket"));
});

test("getBuildComponentSpecs returns motherboard specs without CPU fields", () => {
  const specs = getBuildComponentSpecs(items.MOTHERBOARD);
  const labels = specs.map((s) => s.label);

  assert.ok(labels.includes("Socket"));
  assert.ok(labels.includes("Chipset"));
  assert.ok(!labels.includes("Cores"));
});

test("getBuildComponentSpecs returns PSU specs without CPU fields", () => {
  const specs = getBuildComponentSpecs(items.PSU);
  const labels = specs.map((s) => s.label);

  assert.ok(labels.includes("Rated Wattage"));
  assert.ok(labels.includes("Efficiency Rating"));
  assert.ok(!labels.includes("Threads"));
});

/* ---- slot detail request state for all six slots ---- */

test("slot detail requests track each of the six slots independently", () => {
  let state = createBuildDetailState();
  state = startBuildDetailRequest(state, "RAM", 1);
  state = startBuildDetailRequest(state, "PSU", 2);
  state = completeBuildDetailRequest(state, "PSU", 2, items.PSU);

  assert.equal(isBusy(state, "RAM"), true);
  assert.equal(isBusy(state, "PSU"), false);
  assert.equal(getBuildSlotDetail(state, "PSU").id, 6);
  assert.equal(getBuildSlotDetail(state, "RAM"), null);

  state = clearBuildSlotDetail(state, "RAM");
  assert.equal(getBuildSlotRequestState(state, "RAM").status, "idle");
});

function isBusy(state, slot) {
  return getBuildSlotRequestState(state, slot).status === "loading";
}
