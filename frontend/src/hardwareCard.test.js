import test from "node:test";
import assert from "node:assert/strict";

import {
  formatReleaseDate,
  getGpuDetailViewModel,
  getGpuPrimarySpecRows,
  getHardwareCardPrimarySpecs,
} from "./hardwareCard.js";

const gpuSpecs = {
  memory_gb: 32,
  memory_type: "GDDR7",
  core_clock_mhz: null,
  boost_clock_mhz: 2407,
  vram_bandwidth_gbps: 1790,
  tdp_w: 575,
  interface: "PCIe 5.0 x16",
  length_mm: 304,
};

test("GPU cards show primary spec rows with units", () => {
  assert.deepEqual(getHardwareCardPrimarySpecs("GPU", gpuSpecs), [
    { label: "VRAM", value: "32 GB" },
    { label: "Memory Type", value: "GDDR7" },
    { label: "Boost Clock", value: "2407 MHz" },
    { label: "TDP", value: "575 W" },
  ]);
});

test("nullable GPU specs render as N/A", () => {
  const rows = getGpuPrimarySpecRows({
    memory_gb: null,
    memory_type: null,
    boost_clock_mhz: null,
    tdp_w: null,
  });

  assert.equal(rows.length, 4);
  rows.forEach((row) => assert.equal(row.value, "N/A"));
});

test("GPU cards without spec details show no fabricated rows", () => {
  assert.deepEqual(getHardwareCardPrimarySpecs("GPU", undefined), []);
  assert.deepEqual(getHardwareCardPrimarySpecs("GPU", null), []);
});

test("CPU cards do not render GPU spec rows", () => {
  assert.deepEqual(
    getHardwareCardPrimarySpecs("CPU", { memory_gb: 32 }),
    []
  );
});

test("unknown hardware types fail gracefully without spec rows", () => {
  assert.deepEqual(
    getHardwareCardPrimarySpecs("SSD", { memory_gb: 32 }),
    []
  );
});

test("GPU detail view model renders grouped sections", () => {
  const viewModel = getGpuDetailViewModel({
    name: "GeForce RTX 5090",
    manufacturer: "NVIDIA",
    type: "GPU",
    release_date: "2025-01-30",
    architecture: "Blackwell 2.0",
    specifications: gpuSpecs,
  });

  assert.equal(viewModel.name, "GeForce RTX 5090");
  assert.equal(viewModel.manufacturer, "NVIDIA");
  assert.equal(viewModel.type, "GPU");

  assert.deepEqual(viewModel.overview, [
    { label: "Architecture", value: "Blackwell 2.0" },
    { label: "Release Date", value: "Jan 30, 2025" },
  ]);
  assert.deepEqual(viewModel.memory, [
    { label: "VRAM", value: "32 GB" },
    { label: "Memory Type", value: "GDDR7" },
    { label: "Bandwidth", value: "1790 GB/s" },
  ]);
  assert.deepEqual(viewModel.clocks, [
    { label: "Core Clock", value: "N/A" },
    { label: "Boost Clock", value: "2407 MHz" },
  ]);
  assert.deepEqual(viewModel.powerPhysical, [
    { label: "TDP", value: "575 W" },
    { label: "Length", value: "304 mm" },
  ]);
  assert.deepEqual(viewModel.interface, [
    { label: "Bus Interface", value: "PCIe 5.0 x16" },
  ]);
});

test("GPU detail view model covers every GPU specification field", () => {
  const viewModel = getGpuDetailViewModel({
    name: "GeForce RTX 5080",
    manufacturer: "NVIDIA",
    type: "GPU",
    specifications: {
      memory_gb: 16,
      memory_type: "GDDR7",
      core_clock_mhz: 2295,
      boost_clock_mhz: 2617,
      vram_bandwidth_gbps: 960,
      tdp_w: 360,
      interface: "PCIe 5.0 x16",
      length_mm: 304,
    },
  });

  const allValues = [
    ...viewModel.memory,
    ...viewModel.clocks,
    ...viewModel.powerPhysical,
    ...viewModel.interface,
  ].map((row) => row.value);

  assert.deepEqual(allValues, [
    "16 GB",
    "GDDR7",
    "960 GB/s",
    "2295 MHz",
    "2617 MHz",
    "360 W",
    "304 mm",
    "PCIe 5.0 x16",
  ]);
});

test("GPU detail view model keeps missing fields as N/A", () => {
  const viewModel = getGpuDetailViewModel({
    name: "Arc A310",
    type: "GPU",
    release_date: null,
    specifications: {},
  });

  assert.deepEqual(viewModel.overview, [
    { label: "Architecture", value: "N/A" },
    { label: "Release Date", value: "N/A" },
  ]);
  assert.equal(viewModel.memory[0].value, "N/A");
  assert.equal(viewModel.memory[2].value, "N/A");
  assert.equal(viewModel.clocks[0].value, "N/A");
  assert.equal(viewModel.clocks[1].value, "N/A");
  assert.equal(viewModel.powerPhysical[0].value, "N/A");
  assert.equal(viewModel.powerPhysical[1].value, "N/A");
  assert.equal(viewModel.interface[0].value, "N/A");
});

test("release date is formatted for humans and null stays N/A", () => {
  assert.equal(formatReleaseDate("2025-01-30"), "Jan 30, 2025");
  assert.equal(formatReleaseDate("2022-11-03"), "Nov 3, 2022");
  assert.equal(formatReleaseDate(null), "N/A");
  assert.equal(formatReleaseDate(undefined), "N/A");
  assert.equal(formatReleaseDate(""), "N/A");
  assert.equal(formatReleaseDate("2025-13-01"), "2025-13-01");
  assert.equal(formatReleaseDate("not-a-date"), "not-a-date");
});