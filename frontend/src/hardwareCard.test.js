import test from "node:test";
import assert from "node:assert/strict";

import {
  getGpuDetailViewModel,
  getGpuPrimarySpecRows,
  getHardwareCardPrimarySpecs,
} from "./hardwareCard.js";

const gpuSpecs = {
  memory_gb: 32,
  memory_type: "GDDR7",
  boost_clock_mhz: 2407,
  tdp_w: 575,
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

test("GPU detail view model renders overview and primary specs", () => {
  const viewModel = getGpuDetailViewModel({
    name: "GeForce RTX 5090",
    manufacturer: "NVIDIA",
    type: "GPU",
    release_date: "2025-01-30",
    architecture: "Blackwell 2.0",
    specifications: gpuSpecs,
  });

  assert.equal(viewModel.name, "GeForce RTX 5090");
  assert.equal(viewModel.type, "GPU");
  assert.deepEqual(viewModel.overview, [
    { label: "Manufacturer", value: "NVIDIA" },
    { label: "Type", value: "GPU" },
    { label: "Release Date", value: "2025-01-30" },
    { label: "Architecture", value: "Blackwell 2.0" },
  ]);
  assert.equal(viewModel.keySpecifications[0].value, "32 GB");
  assert.equal(viewModel.keySpecifications[3].value, "575 W");
});

test("GPU detail view model keeps missing fields as N/A", () => {
  const viewModel = getGpuDetailViewModel({
    name: "Arc A310",
    type: "GPU",
    specifications: {},
  });

  assert.equal(viewModel.keySpecifications[0].value, "N/A");
  assert.equal(
    viewModel.overview.find((row) => row.label === "Architecture").value,
    "N/A"
  );
  assert.equal(
    viewModel.overview.find((row) => row.label === "Manufacturer").value,
    "N/A"
  );
});