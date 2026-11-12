import test from "node:test";
import assert from "node:assert/strict";

import { apiUrl } from "./api.js";
import {
  HARDWARE_TYPES,
  createCatalogLoadGuard,
  deriveManufacturerOptions,
  getCatalogFilterState,
  getCatalogReadout,
  getCatalogResultSummary,
  getCatalogTypeLabel,
  getNextManufacturerFilter,
  getHardwareCatalogUrl,
  getHardwareFacetsUrl,
  mergeTypeFacetCounts,
  requestHardwareCatalog,
  requestHardwareCatalogPage,
  requestHardwareFacets,
} from "./catalog.js";
import { isComparisonSupported } from "./comparisonDecision.js";

const gpuItem = {
  id: 7,
  name: "GeForce RTX 5090",
  manufacturer: "NVIDIA",
  type: "GPU",
};

test("catalog exposes the Build Planner category filters in order", () => {
  // M1 Task 5: the four new categories join the existing filters in order.
  assert.deepEqual(HARDWARE_TYPES, [
    "All", "CPU", "GPU", "RAM", "STORAGE", "MOTHERBOARD", "PSU",
  ]);
});

test("new categories get human type labels", () => {
  assert.equal(getCatalogTypeLabel("RAM"), "RAM");
  assert.equal(getCatalogTypeLabel("STORAGE"), "Storage");
  assert.equal(getCatalogTypeLabel("MOTHERBOARD"), "Motherboards");
  assert.equal(getCatalogTypeLabel("PSU"), "PSUs");
});

test("getCatalogFilterState handles new category values", () => {
  const active = getCatalogFilterState("RAM", "RAM");
  assert.equal(active.isActive, true);
  assert.equal(active.pressed, true);
  assert.equal(active.className, "filter-button active");

  const inactive = getCatalogFilterState("PSU", "RAM");
  assert.equal(inactive.isActive, false);
  assert.equal(inactive.pressed, false);
  assert.equal(inactive.className, "filter-button");
});

test("manufacturer options derive from live facet data, All first", () => {
  // M2.5 Task 2: the static CPU/GPU-era list is gone; options must come
  // from the facets endpoint so a PSU catalog never shows Intel/NVIDIA.
  assert.deepEqual(
    deriveManufacturerOptions([
      { value: "Corsair", count: 12 },
      { value: "Seasonic", count: 7 },
    ]),
    ["All", "Corsair", "Seasonic"]
  );
});

test("manufacturer options fall back to All when no facet data", () => {
  assert.deepEqual(deriveManufacturerOptions([]), ["All"]);
  assert.deepEqual(deriveManufacturerOptions(null), ["All"]);
  assert.deepEqual(deriveManufacturerOptions(undefined), ["All"]);
});

test("manufacturer filter resets when the selection leaves the option set", () => {
  // Switching category (or data changing) can drop the active manufacturer;
  // a stale selection must fall back to All instead of silently emptying
  // the catalog.
  assert.equal(getNextManufacturerFilter("ATI", ["All", "Intel", "AMD"]), "All");
  assert.equal(getNextManufacturerFilter("AMD", ["All", "Intel", "AMD"]), "AMD");
  assert.equal(getNextManufacturerFilter("All", ["All"]), "All");
  assert.equal(getNextManufacturerFilter(undefined, ["All", "Corsair"]), "All");
});

test("comparison support matrix covers only CPU and GPU", () => {
  // The comparison backend and metric tables are CPU/GPU-shaped; every
  // other category must report unsupported so the UI can hide the action.
  assert.equal(isComparisonSupported("CPU"), true);
  assert.equal(isComparisonSupported("GPU"), true);
  assert.equal(isComparisonSupported("RAM"), false);
  assert.equal(isComparisonSupported("STORAGE"), false);
  assert.equal(isComparisonSupported("MOTHERBOARD"), false);
  assert.equal(isComparisonSupported("PSU"), false);
  assert.equal(isComparisonSupported(undefined), false);
  assert.equal(isComparisonSupported("NOTACAT"), false);
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

test("catalog readout labels the count with the active type's record noun", () => {
  assert.deepEqual(getCatalogReadout({ totalCount: 5239 }), {
    value: 5239,
    label: "matching hardware records",
    meta: "",
  });

  assert.equal(getCatalogReadout({ totalCount: 40, typeFilter: "GPU" }).label, "matching GPU records");
  assert.equal(getCatalogReadout({ totalCount: 40, typeFilter: "CPU" }).label, "matching CPU records");
});

test("catalog readout scopes the meta line to the manufacturer filter", () => {
  assert.equal(
    getCatalogReadout({ totalCount: 12, manufacturerFilter: "AMD" }).meta,
    "AMD"
  );

  assert.deepEqual(getCatalogReadout({}), {
    value: 0,
    label: "matching hardware records",
    meta: "",
  });

  /* An unfiltered count says nothing about manufacturers: repeating "All"
     next to an already-unqualified number is the same fact twice. */
  assert.equal(
    getCatalogReadout({ totalCount: 12, manufacturerFilter: "All" }).meta,
    ""
  );
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

/* --- Phase 1.3 server pages + facets --- */

test("catalog URL includes server filters and pagination when provided", () => {
  assert.equal(
    getHardwareCatalogUrl("GPU", {
      q: "rtx",
      manufacturer: "NVIDIA",
      limit: 20,
      offset: 40,
    }),
    apiUrl("/hardware?type=GPU&q=rtx&manufacturer=NVIDIA&limit=20&offset=40")
  );

  assert.equal(
    getHardwareCatalogUrl("All", { manufacturer: "AMD", limit: 10 }),
    apiUrl("/hardware?manufacturer=AMD&limit=10")
  );
});

test("catalog URL omits default filter values", () => {
  assert.equal(getHardwareCatalogUrl("All", {}), apiUrl("/hardware"));
  assert.equal(
    getHardwareCatalogUrl("All", { manufacturer: "All", offset: 0, limit: null }),
    apiUrl("/hardware")
  );
  assert.equal(
    getHardwareCatalogUrl("All", { segment: "" }),
    apiUrl("/hardware")
  );
});

test("catalog page request sends server filters and returns items plus total", async () => {
  let receivedUrl;
  const { items, totalCount } = await requestHardwareCatalogPage(
    "GPU",
    { q: "rtx", manufacturer: "NVIDIA", limit: 20, offset: 0 },
    async (url) => {
      receivedUrl = url;
      return {
        ok: true,
        headers: { get: () => "35" },
        json: async () => [gpuItem],
      };
    }
  );

  assert.equal(
    receivedUrl,
    apiUrl("/hardware?type=GPU&q=rtx&manufacturer=NVIDIA&limit=20")
  );
  assert.deepEqual(items, [gpuItem]);
  assert.equal(totalCount, 35);
});

test("catalog page falls back to item count when header absent", async () => {
  const { items, totalCount } = await requestHardwareCatalogPage(
    "GPU",
    { limit: 20 },
    async () => ({
      ok: true,
      headers: { get: () => null },
      json: async () => [gpuItem, { ...gpuItem, id: 8 }],
    })
  );

  assert.deepEqual(items, [gpuItem, { ...gpuItem, id: 8 }]);
  assert.equal(totalCount, 2);
});

test("catalog page request validates payload shape", async () => {
  await assert.rejects(
    requestHardwareCatalogPage(
      "GPU",
      { limit: 20 },
      async () => ({
        ok: true,
        headers: { get: () => "1" },
        json: async () => [{ id: "bad", name: 42, type: "GPU" }],
      })
    ),
    /id/
  );
});

test("facet merge keeps last-known counts for types absent from a response", () => {
  /* The facets endpoint scopes to the active type filter, so a GPU-filtered
     response carries only {GPU: n}. The hero quick-paths read both counts
     unconditionally; merging (not overwriting) keeps the other type stable. */
  const previous = { CPU: 3501, GPU: 1879 };

  assert.deepEqual(
    mergeTypeFacetCounts(previous, [{ value: "GPU", count: 1879 }]),
    { CPU: 3501, GPU: 1879 }
  );

  assert.deepEqual(
    mergeTypeFacetCounts(previous, [{ value: "CPU", count: 3501 }]),
    { CPU: 3501, GPU: 1879 }
  );
});

test("facet merge updates counts that are present and tolerates empty state", () => {
  assert.deepEqual(
    mergeTypeFacetCounts({ CPU: 3501 }, [{ value: "CPU", count: 3502 }]),
    { CPU: 3502 }
  );

  assert.deepEqual(mergeTypeFacetCounts({}, []), {});
  assert.deepEqual(mergeTypeFacetCounts(undefined, [{ value: "CPU", count: 3 }]), {
    CPU: 3,
  });
  assert.deepEqual(mergeTypeFacetCounts({ CPU: 3 }, undefined), { CPU: 3 });
});

test("facets URL reflects active filters and omits defaults", () => {
  assert.equal(getHardwareFacetsUrl(), apiUrl("/hardware/facets"));
  assert.equal(getHardwareFacetsUrl({}), apiUrl("/hardware/facets"));
  assert.equal(
    getHardwareFacetsUrl({ type: "GPU", manufacturer: "NVIDIA" }),
    apiUrl("/hardware/facets?type=GPU&manufacturer=NVIDIA")
  );
  assert.equal(
    getHardwareFacetsUrl({ q: "ryzen", segment: "desktop" }),
    apiUrl("/hardware/facets?q=ryzen&segment=desktop")
  );
});

test("facets client requests and returns the facet payload", async () => {
  let receivedUrl;
  const payload = await requestHardwareFacets(
    { type: "GPU" },
    async (url) => {
      receivedUrl = url;
      return {
        ok: true,
        json: async () => ({ types: [], manufacturers: [], segments: [] }),
      };
    }
  );

  assert.equal(receivedUrl, apiUrl("/hardware/facets?type=GPU"));
  assert.deepEqual(payload, {
    types: [],
    manufacturers: [],
    segments: [],
  });
});

test("facets client surfaces API errors", async () => {
  await assert.rejects(
    requestHardwareFacets({}, async () => ({ ok: false, status: 500 })),
    /HTTP error/
  );
});