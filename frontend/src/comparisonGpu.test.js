import test from "node:test";
import assert from "node:assert/strict";

import { API_BASE_URL } from "./api.js";
import { requestGpuComparison } from "./comparisonGpu.js";

const validResponse = () => ({
  ok: true,
  json: async () => ({
    hardware_a: "GPU A",
    hardware_b: "GPU B",
    metrics: [
      { name: "memory_gb", value_a: 24, value_b: 16, unit: "GB", winner: "a", difference: 8 },
      { name: "tdp_w", value_a: 200, value_b: 300, unit: "W", winner: "a", difference: -100 },
    ],
  }),
});

test("requestGpuComparison posts both hardware ids to the endpoint", async () => {
  let received;

  await requestGpuComparison(7, 11, async (url, options) => {
    received = { url, options };
    return validResponse();
  });

  assert.equal(received.url, `${API_BASE_URL}/comparison/gpu`);
  assert.equal(received.options.method, "POST");
  const body = JSON.parse(received.options.body);
  assert.deepEqual(body, { hardware_id_a: 7, hardware_id_b: 11 });
});

test("requestGpuComparison returns the parsed result payload", async () => {
  const payload = await requestGpuComparison(7, 11, async () => validResponse());

  assert.equal(payload.hardware_a, "GPU A");
  assert.equal(payload.metrics.length, 2);
});

test("requestGpuComparison throws on non-ok HTTP", async () => {
  await assert.rejects(
    () =>
      requestGpuComparison(7, 11, async () => ({
        ok: false,
        status: 404,
      })),
    /status 404/
  );
});

test("requestGpuComparison forwards the abort signal to the transport", async () => {
  const controller = new AbortController();
  let receivedSignal = null;

  await requestGpuComparison(
    7,
    11,
    async (url, options) => {
      receivedSignal = options.signal;
      return validResponse();
    },
    controller.signal
  );

  assert.equal(receivedSignal, controller.signal);
});
