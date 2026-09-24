import test from "node:test";
import assert from "node:assert/strict";

import { apiUrl } from "./api.js";
import {
  createDetailRequestGuard,
  requestHardwareDetail,
} from "./detailRequest.js";

const gpuDetail = {
  id: 4031,
  name: "Radeon RX 7900 XTX",
  manufacturer: "AMD",
  type: "GPU",
  release_date: "2022-11-03",
  architecture: "RDNA 3.0",
  specifications: {
    memory_gb: 24,
    memory_type: "GDDR6",
    core_clock_mhz: null,
    boost_clock_mhz: 2498,
    vram_bandwidth_gbps: 960,
    tdp_w: 355,
    interface: "PCIe 4.0 x16",
    length_mm: 287,
  },
};

test("GPU detail request targets the requested hardware id", async () => {
  let receivedUrl;
  const detail = await requestHardwareDetail(4031, async (url) => {
    receivedUrl = url;
    return { ok: true, json: async () => gpuDetail };
  });

  assert.equal(receivedUrl, apiUrl("/hardware/4031"));
  assert.equal(detail.id, 4031);
  assert.equal(detail.type, "GPU");
});

test("detail request rejects a response id mismatch", async () => {
  await assert.rejects(
    requestHardwareDetail(4031, async () => ({
      ok: true,
      json: async () => ({ ...gpuDetail, id: 999 }),
    })),
    /does not match/
  );
});

test("detail request surfaces API errors", async () => {
  await assert.rejects(
    requestHardwareDetail(4031, async () => ({
      ok: false,
      status: 404,
    })),
    /HTTP error/
  );
});

test("detail request rejects a malformed GPU payload", async () => {
  await assert.rejects(
    requestHardwareDetail(4031, async () => ({
      ok: true,
      json: async () => ({
        ...gpuDetail,
        specifications: { memory_gb: ["nested", "array"] },
      }),
    })),
    /invalid specification value/
  );
});

test("detail request accepts nullable GPU specification fields", async () => {
  const detail = await requestHardwareDetail(4031, async () => ({
    ok: true,
    json: async () => ({
      ...gpuDetail,
      specifications: {
        memory_gb: null,
        memory_type: null,
        core_clock_mhz: null,
        boost_clock_mhz: null,
        vram_bandwidth_gbps: null,
        tdp_w: null,
        interface: null,
        length_mm: null,
      },
    }),
  }));

  assert.equal(detail.specifications.memory_gb, null);
  assert.equal(detail.specifications.length_mm, null);
});

test("detail guard drops stale responses after a newer request", async () => {
  const guard = createDetailRequestGuard();
  const firstRequest = guard.begin();
  const secondRequest = guard.begin();

  assert.equal(guard.isCurrent(firstRequest), false);
  assert.equal(guard.isCurrent(secondRequest), true);

  let rendered = null;
  if (guard.isCurrent(firstRequest)) {
    rendered = "stale";
  }
  if (guard.isCurrent(secondRequest)) {
    rendered = "latest";
  }

  assert.equal(rendered, "latest");
});

test("invalidating a detail guard drops the pending request", () => {
  const guard = createDetailRequestGuard();
  const requestId = guard.begin();

  guard.invalidate();

  assert.equal(guard.isCurrent(requestId), false);
});