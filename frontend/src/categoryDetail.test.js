import test from "node:test";
import assert from "node:assert/strict";

import {
  getRamDetailViewModel,
  getStorageDetailViewModel,
  getMotherboardDetailViewModel,
  getPsuDetailViewModel,
  getCategoryDetailViewModel,
} from "./detail.js";

const ramHardware = {
  id: 11,
  name: "Vengeance 32GB",
  manufacturer: "Corsair",
  type: "RAM",
  release_date: "2022-09-01",
  specifications: {
    ddr_generation: "DDR5",
    capacity_gb: 32,
    speed_mhz: 5600,
    modules: 2,
    ecc: 0,
    voltage_v: 1.25,
    form_factor: "UDIMM",
  },
};

const storageHardware = {
  id: 12,
  name: "980 Pro 1TB",
  manufacturer: "Samsung",
  type: "STORAGE",
  release_date: "2020-09-29",
  specifications: {
    storage_type: "NVMe",
    capacity_gb: 1024,
    interface: "PCIe 4.0 x4",
    read_mb_s: 7000,
    write_mb_s: 5000,
    dram_cache: 1,
    form_factor: "M.2 2280",
  },
};

const motherboardHardware = {
  id: 13,
  name: "Z690-A",
  manufacturer: "ASUS",
  type: "MOTHERBOARD",
  release_date: "2021-10-01",
  specifications: {
    socket: "LGA1700",
    chipset: "Z690",
    form_factor: "ATX",
    ram_type: "DDR5",
    ram_slots: 4,
    max_ram_gb: 128,
    m2_slots: 3,
    sata_ports: 4,
    pcie_slots: 2,
  },
};

const psuHardware = {
  id: 14,
  name: "RM750x",
  manufacturer: "Corsair",
  type: "PSU",
  release_date: "2020-06-01",
  specifications: {
    wattage: 750,
    efficiency_rating: "80 Plus Gold",
    modular: 1,
    pcie_8pin_count: 4,
    pcie_12vhpwr: 0,
  },
};

test("RAM detail view model shows memory specs and never CPU fields", () => {
  const viewModel = getRamDetailViewModel(ramHardware);

  assert.equal(viewModel.name, "Vengeance 32GB");
  const labels = viewModel.keySpecifications.map((item) => item.label);
  assert.ok(labels.includes("Capacity"));
  assert.ok(labels.includes("DDR Generation"));
  assert.ok(labels.includes("Speed"));
  assert.ok(labels.includes("Modules"));
  const all = JSON.stringify(viewModel);
  assert.ok(!all.includes("Cores"));
  assert.ok(!all.includes("Threads"));
  assert.ok(!all.includes("Socket"));
});

test("RAM detail view model renders N/A for missing values", () => {
  const viewModel = getRamDetailViewModel({
    ...ramHardware,
    specifications: { capacity_gb: 16 },
  });

  const byLabel = Object.fromEntries(
    viewModel.keySpecifications.map((item) => [item.label, item.value]),
  );
  assert.equal(byLabel["Capacity"], "16 GB");
  assert.equal(byLabel["DDR Generation"], "N/A");
  assert.equal(byLabel["Speed"], "N/A");
});

test("Storage detail view model shows interface and performance only", () => {
  const viewModel = getStorageDetailViewModel(storageHardware);

  const labels = viewModel.keySpecifications.map((item) => item.label);
  assert.ok(labels.includes("Capacity"));
  assert.ok(labels.includes("Storage Type"));
  assert.ok(labels.includes("Interface"));
  const all = JSON.stringify(viewModel);
  assert.ok(!all.includes("Cores"));
  assert.ok(!all.includes("Threads"));
  assert.ok(!all.includes("Socket"));
});

test("Storage detail view model shows sequential performance where sourced", () => {
  const viewModel = getStorageDetailViewModel(storageHardware);

  const byLabel = Object.fromEntries(
    viewModel.technicalSpecifications.map((item) => [item.label, item.value]),
  );
  assert.equal(byLabel["Sequential Read"], "7000 MB/s");
  assert.equal(byLabel["Sequential Write"], "5000 MB/s");
});

test("Motherboard detail view model shows socket, chipset, memory, expansion", () => {
  const viewModel = getMotherboardDetailViewModel(motherboardHardware);

  const labels = viewModel.keySpecifications.map((item) => item.label);
  assert.ok(labels.includes("Socket"));
  assert.ok(labels.includes("Chipset"));
  assert.ok(labels.includes("Memory Type"));
  const labels2 = viewModel.technicalSpecifications.map((item) => item.label);
  assert.ok(labels2.includes("M.2 Slots"));
  assert.ok(labels2.includes("SATA Ports"));
  assert.ok(labels2.includes("PCIe Slots"));
  const all = JSON.stringify(viewModel);
  assert.ok(!all.includes("Cores"));
  assert.ok(!all.includes("Threads"));
});

test("Motherboard detail view model renders N/A for missing expansion data", () => {
  const viewModel = getMotherboardDetailViewModel({
    ...motherboardHardware,
    specifications: { socket: "AM5" },
  });

  const byLabel = Object.fromEntries(
    [
      ...viewModel.keySpecifications,
      ...viewModel.technicalSpecifications,
    ].map((item) => [item.label, item.value]),
  );
  assert.equal(byLabel["Socket"], "AM5");
  assert.equal(byLabel["Chipset"], "N/A");
  assert.equal(byLabel["M.2 Slots"], "N/A");
});

test("PSU detail view model shows wattage, efficiency, connectors, form factor", () => {
  const viewModel = getPsuDetailViewModel(psuHardware);

  const labels = viewModel.keySpecifications.map((item) => item.label);
  assert.ok(labels.includes("Rated Wattage"));
  assert.ok(labels.includes("Efficiency Rating"));
  const byLabel = Object.fromEntries(
    [
      ...viewModel.keySpecifications,
      ...viewModel.technicalSpecifications,
    ].map((item) => [item.label, item.value]),
  );
  assert.equal(byLabel["Rated Wattage"], "750 W");
  assert.equal(byLabel["Efficiency Rating"], "80 Plus Gold");
  assert.equal(byLabel["Modular"], "Yes");
  assert.equal(byLabel["PCIe 8-pin Connectors"], "4");
  const all = JSON.stringify(viewModel);
  assert.ok(!all.includes("Cores"));
  assert.ok(!all.includes("Threads"));
});

test("PSU detail view model renders N/A for missing connector data", () => {
  const viewModel = getPsuDetailViewModel({
    ...psuHardware,
    specifications: { wattage: 650 },
  });

  const byLabel = Object.fromEntries(
    [
      ...viewModel.keySpecifications,
      ...viewModel.technicalSpecifications,
    ].map((item) => [item.label, item.value]),
  );
  assert.equal(byLabel["Rated Wattage"], "650 W");
  assert.equal(byLabel["Efficiency Rating"], "N/A");
  assert.equal(byLabel["PCIe 8-pin Connectors"], "N/A");
  assert.equal(byLabel["12VHPWR Connectors"], "N/A");
});

test("getCategoryDetailViewModel routes each category to its view model", () => {
  assert.equal(
    getCategoryDetailViewModel(ramHardware).keySpecifications.length,
    getRamDetailViewModel(ramHardware).keySpecifications.length,
  );
  assert.equal(
    getCategoryDetailViewModel(storageHardware).keySpecifications.length,
    getStorageDetailViewModel(storageHardware).keySpecifications.length,
  );
  assert.equal(
    getCategoryDetailViewModel(motherboardHardware).keySpecifications.length,
    getMotherboardDetailViewModel(motherboardHardware).keySpecifications.length,
  );
  assert.equal(
    getCategoryDetailViewModel(psuHardware).keySpecifications.length,
    getPsuDetailViewModel(psuHardware).keySpecifications.length,
  );
});

test("getCategoryDetailViewModel falls back to CPU view model for CPU type", () => {
  const cpuHardware = {
    id: 7,
    name: "Ryzen 9",
    manufacturer: "AMD",
    type: "CPU",
    specifications: { cores: 8, threads: 16 },
  };
  const viewModel = getCategoryDetailViewModel(cpuHardware);
  const labels = viewModel.keySpecifications.map((item) => item.label);
  assert.ok(labels.includes("Cores"));
});
