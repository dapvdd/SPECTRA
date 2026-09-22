import test from "node:test";
import assert from "node:assert/strict";

import {
  AI_ANALYSIS_STATUS,
  requestComparisonExplanation,
} from "./comparisonExplanation.js";
import { apiUrl } from "./api.js";

const comparison = {
  cpu_a: { name: "CPU A", manufacturer: "Vendor A" },
  cpu_b: { name: "CPU B", manufacturer: "Vendor B" },
  metrics: [],
  ties: [],
  unavailable_metrics: [],
};

test("AI analysis starts idle", () => {
  assert.equal(AI_ANALYSIS_STATUS.idle, "idle");
});

test("comparison explanation client posts structured facts and returns text", async () => {
  let receivedRequest;
  const explanation = await requestComparisonExplanation(
    comparison,
    async (url, options) => {
      receivedRequest = { url, options };
      return {
        ok: true,
        json: async () => ({ explanation: "The supplied facts show a specification difference." }),
      };
    }
  );

  assert.equal(receivedRequest.url, apiUrl("/comparison/explanation"));
  assert.equal(receivedRequest.options.method, "POST");
  assert.deepEqual(JSON.parse(receivedRequest.options.body), { comparison });
  assert.equal(explanation, "The supplied facts show a specification difference.");
});

test("comparison explanation client exposes provider errors to the UI", async () => {
  await assert.rejects(
    requestComparisonExplanation(comparison, async () => ({
      ok: false,
      status: 503,
      json: async () => ({ detail: "AI provider is not configured." }),
    })),
    /status 503/
  );
});

test("comparison explanation client rejects empty successful responses", async () => {
  await assert.rejects(
    requestComparisonExplanation(comparison, async () => ({
      ok: true,
      json: async () => ({ explanation: "" }),
    })),
    /did not contain text/
  );
});
