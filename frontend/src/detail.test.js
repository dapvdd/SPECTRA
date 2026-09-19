import test from "node:test";
import assert from "node:assert/strict";

import {
  formatDetailValue,
  getCpuDetailViewModel,
  getDetailComparisonAction,
} from "./detail.js";

const hardware = {
  id: 7,
  name: "AMD Ryzen 9 7940HS",
  manufacturer: "AMD",
  type: "Mobile Processor",
  release_date: "2023-01-01",
  architecture: "Zen 4",
  specifications: {
    cores: 8,
    threads: 16,
    base_clock_ghz: 4,
    boost_clock_ghz: 5.2,
    tdp_w: 35,
    process_node_nm: 4,
    socket: "FP8",
  },
};

test("CPU detail view model preserves name, manufacturer, and type", () => {
  const viewModel = getCpuDetailViewModel(hardware);

  assert.equal(viewModel.name, "AMD Ryzen 9 7940HS");
  assert.equal(viewModel.manufacturer, "AMD");
  assert.equal(viewModel.type, "Mobile Processor");
});

test("CPU detail view model formats available specification values", () => {
  const viewModel = getCpuDetailViewModel(hardware);

  assert.deepEqual(viewModel.keySpecifications, [
    { label: "Cores", value: "8" },
    { label: "Threads", value: "16" },
    { label: "Base Clock", value: "4 GHz" },
    { label: "Boost Clock", value: "5.2 GHz" },
    { label: "TDP", value: "35 W" },
  ]);
});

test("CPU detail view model represents missing values as N/A", () => {
  const viewModel = getCpuDetailViewModel({
    id: 8,
    name: "Incomplete CPU",
    specifications: { cores: 8, tdp_w: null },
  });

  assert.equal(viewModel.manufacturer, "N/A");
  assert.equal(viewModel.overview[2].value, "N/A");
  assert.equal(viewModel.keySpecifications[1].value, "N/A");
  assert.equal(viewModel.keySpecifications[4].value, "N/A");
  assert.equal(viewModel.technicalSpecifications[1].value, "N/A");
});

test("formatDetailValue preserves real zero values", () => {
  assert.equal(formatDetailValue(0), "0");
  assert.equal(formatDetailValue(0, "W"), "0 W");
});

test("detail comparison action assigns CPU 01 when no CPU is selected", () => {
  assert.deepEqual(getDetailComparisonAction([], 7), {
    alreadySelected: false,
    comparisonFull: false,
    comparisonSlot: 1,
    shouldNavigateToComparison: false,
  });
});

test("detail comparison action assigns CPU 02 and navigates when one CPU is selected", () => {
  const action = getDetailComparisonAction([{ id: 6 }], 7);

  assert.equal(action.comparisonSlot, 2);
  assert.equal(action.shouldNavigateToComparison, true);
  assert.equal(action.comparisonFull, false);
});

test("detail comparison action prevents duplicate selection", () => {
  const action = getDetailComparisonAction([{ id: 7 }], 7);

  assert.equal(action.alreadySelected, true);
  assert.equal(action.comparisonSlot, 1);
  assert.equal(action.shouldNavigateToComparison, false);
});

test("detail comparison action does not replace a full comparison", () => {
  const action = getDetailComparisonAction([{ id: 5 }, { id: 6 }], 7);

  assert.equal(action.comparisonFull, true);
  assert.equal(action.alreadySelected, false);
  assert.equal(action.shouldNavigateToComparison, false);
});
