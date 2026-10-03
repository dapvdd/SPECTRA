import test from "node:test";
import assert from "node:assert/strict";

import { apiUrl } from "./api.js";
import {
  HARDWARE_TYPES,
  MANUFACTURER_FILTERS,
  createCatalogLoadGuard,
  getCatalogFilterState,
  getCatalogResultSummary,
  getCatalogTypeLabel,
  getHardwareCatalogUrl,
  requestHardwareCatalog,
} from "./catalog.js";

const gpuItem = {
  id: 7,
  name: "GeForce RTX 5090",
  manufacturer: "NVIDIA",
  type: "GPU",
};

test("catalog exposes All, CPU, and GPU type filters", () => {
  assert.deepEqual(HARDWARE_TYPES, ["All", "CPU", "GPU"]);
});

test("catalog exposes the All, Intel, and AMD manufacturer filters", () => {
  assert.deepEqual(MANUFACTURER_FILTERS, ["All", "Intel", "AMD"]);
});

test("catalog type labels pluralize known types and fall back generically", () => {
  assert.equal(getCatalogTypeLabel("CPU"), "CPUs");
  assert.equal(getCatalogTypeLabel("GPU"), "GPUs");
  assert.equal(getCatalogTypeLabel("All"), "hardware records");
});

test("catalog filter state marks only the active filter as pressed", () => {
  assert.deepEqual(getCatalogFilterState("GPU", "GPU"), {
    isActive: true,
    className: "filter-button active",
    pressed: true,
  });

  assert.deepEqual(getCatalogFilterState("CPU", "GPU"), {
    isActive: false,
    className: "filter-button",
    pressed: false,
  });
});

test("catalog result summary reports the loading and error states first", () => {
  assert.equal(
    getCatalogResultSummary({ loading: true, totalCount: 12 }),
    "Loading hardware catalog..."
  );

  assert.equal(
    getCatalogResultSummary({ error: "Hardware catalog could not be loaded." }),
    "Hardware catalog unavailable"
  );
});

test("catalog result summary counts visible results against the filtered total", () => {
  assert.equal(
    getCatalogResultSummary({ visibleCount: 12, totalCount: 40, typeFilter: "GPU" }),
    "Showing 12 of 40 GPUs"
  );

  assert.equal(
    getCatalogResultSummary({ visibleCount: 40, totalCount: 40 }),
    "Showing 40 of 40 hardware records"
  );
});

test("catalog result summary scopes the count to the manufacturer filter", () => {
  assert.equal(
    getCatalogResultSummary({
      visibleCount: 3,
      totalCount: 3,
      manufacturerFilter: "AMD",
      typeFilter: "CPU",
    }),
    "Showing 3 of 3 AMD CPUs"
  );
});

test("catalog result summary explains an empty filtered result set", () => {
  assert.equal(
    getCatalogResultSummary({
      visibleCount: 0,
      totalCount: 0,
      manufacturerFilter: "Intel",
      typeFilter: "GPU",
    }),
    "No Intel GPUs match the current filters"
  );
});

test("catalog URL defaults to the full hardware list", () => {
  assert.equal(getHardwareCatalogUrl(), apiUrl("/hardware"));
  assert.equal(getHardwareCatalogUrl("All"), apiUrl("/hardware"));
});

test("catalog URL reflects CPU and GPU type filters", () => {
  assert.equal(getHardwareCatalogUrl("CPU"), apiUrl("/hardware?type=CPU"));
  assert.equal(getHardwareCatalogUrl("GPU"), apiUrl("/hardware?type=GPU"));
});

test("catalog client requests the typed list and returns validated items", async () => {
  let receivedUrl;
  const items = await requestHardwareCatalog("GPU", async (url) => {
    receivedUrl = url;
    return { ok: true, json: async () => [gpuItem] };
  });

  assert.equal(receivedUrl, apiUrl("/hardware?type=GPU"));
  assert.deepEqual(items, [gpuItem]);
});

test("catalog client accepts an empty GPU catalog", async () => {
  const items = await requestHardwareCatalog("GPU", async () => ({
    ok: true,
    json: async () => [],
  }));

  assert.deepEqual(items, []);
});

test("catalog client surfaces API errors instead of an empty catalog", async () => {
  await assert.rejects(
    requestHardwareCatalog("GPU", async () => ({
      ok: false,
      status: 500,
    })),
    /HTTP error/
  );
});

test("catalog client rejects a malformed GPU payload", async () => {
  await assert.rejects(
    requestHardwareCatalog("GPU", async () => ({
      ok: true,
      json: async () => [
        { id: "not-an-id", name: 42, manufacturer: "NVIDIA", type: "GPU" },
      ],
    })),
    /id/
  );
});

test("catalog load guard drops stale responses after a type switch", async () => {
  const guard = createCatalogLoadGuard();
  const firstRequest = guard.begin();
  const secondRequest = guard.begin();

  assert.equal(guard.isCurrent(firstRequest), false);
  assert.equal(guard.isCurrent(secondRequest), true);

  let appliedCatalogs = [];
  if (guard.isCurrent(firstRequest)) {
    appliedCatalogs.push("generic");
  }
  if (guard.isCurrent(secondRequest)) {
    appliedCatalogs.push("gpu");
  }

  assert.deepEqual(appliedCatalogs, ["gpu"]);
});

test("invalidating a catalog load guard drops the pending request", () => {
  const guard = createCatalogLoadGuard();
  const requestId = guard.begin();

  guard.invalidate();

  assert.equal(guard.isCurrent(requestId), false);
});

test("catalog client CPU type requests the CPU-filtered list", async () => {
  let receivedUrl;
  const cpuItem = {
    id: 1,
    name: "AMD Ryzen 5 5600",
    manufacturer: "AMD",
    type: "CPU",
  };

  await requestHardwareCatalog("CPU", async (url) => {
    receivedUrl = url;
    return { ok: true, json: async () => [cpuItem] };
  });

  assert.equal(receivedUrl, apiUrl("/hardware?type=CPU"));
});