import test from "node:test";
import assert from "node:assert/strict";

import { apiUrl } from "./api.js";
import {
  HARDWARE_TYPES,
  createCatalogLoadGuard,
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