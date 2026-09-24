import test from "node:test";
import assert from "node:assert/strict";

import { apiUrl } from "./api.js";
import { parseMarkdown } from "./markdown.js";
import {
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  HardwareChatError,
  buildHardwareChatContext,
  completeHardwareChatRequest,
  createChatRequestGuard,
  createHardwareChatState,
  failHardwareChatRequest,
  requestHardwareChatAnswer,
  startHardwareChatRequest,
} from "./hardwareChat.js";

const detail = {
  id: 123,
  name: "AMD Ryzen 5 5600",
  manufacturer: "AMD",
  type: "CPU",
  specifications: { cores: 6, threads: 12 },
};

const context = buildHardwareChatContext(detail, []);

test("chat context whitelists only supported hardware fields", () => {
  const context = buildHardwareChatContext(
    {
      ...detail,
      release_date: "2022-04-04",
      architecture: "Zen 3",
      url: "https://example.invalid/secret",
    },
    []
  );

  assert.deepEqual(context, {
    id: 123,
    name: "AMD Ryzen 5 5600",
    manufacturer: "AMD",
    type: "CPU",
    specifications: { cores: 6, threads: 12 },
    benchmarks: [],
  });
});

test("chat context restricts benchmark records to allowed fields", () => {
  const context = buildHardwareChatContext(detail, [
    {
      id: 7,
      hardware_id: 123,
      benchmark_name: "Geekbench 7",
      test_type: "single-core",
      score: 2100,
      unit: "points",
      source: {
        id: 1,
        name: "Geekbench Browser - Geekbench 7 CPU",
        url: "https://example.test",
      },
      recorded_at: "2026-09-16T00:00:00Z",
      secret_token: "do-not-send",
    },
    {
      benchmark_name: "Cinebench",
      test_type: "multi-core",
      score: 9000,
      unit: "points",
    },
  ]);

  assert.deepEqual(context.benchmarks, [
    {
      id: 7,
      hardware_id: 123,
      benchmark_name: "Geekbench 7",
      test_type: "single-core",
      score: 2100,
      unit: "points",
      source: {
        id: 1,
        name: "Geekbench Browser - Geekbench 7 CPU",
        url: "https://example.test",
      },
      recorded_at: "2026-09-16T00:00:00Z",
    },
    {
      benchmark_name: "Cinebench",
      test_type: "multi-core",
      score: 9000,
      unit: "points",
    },
  ]);
});

test("chat context reads benchmarks from wrapped payload shapes", () => {
  for (const payload of [
    { benchmark_results: [{ score: 1, benchmark_name: "B", test_type: "t", unit: "u" }] },
    { benchmarks: [{ score: 2, benchmark_name: "B", test_type: "t", unit: "u" }] },
    { results: [{ score: 3, benchmark_name: "B", test_type: "t", unit: "u" }] },
    { performance: { results: [{ score: 4, benchmark_name: "B", test_type: "t", unit: "u" }] } },
  ]) {
    const context = buildHardwareChatContext(detail, payload);
    assert.equal(context.benchmarks.length, 1);
    assert.equal(context.benchmarks[0].score > 0, true);
  }
});

test("hardware chat client posts whitelisted context and returns the answer", async () => {
  let receivedRequest;
  const answer = await requestHardwareChatAnswer(
    context,
    "Kuat buat GTA V?",
    async (url, options) => {
      receivedRequest = { url, options };
      return {
        ok: true,
        json: async () => ({ answer: "Secara kualitatif, cukup mumpuni." }),
      };
    }
  );

  assert.equal(receivedRequest.url, apiUrl("/hardware/chat"));
  assert.equal(receivedRequest.options.method, "POST");
  assert.deepEqual(JSON.parse(receivedRequest.options.body), {
    hardware: context,
    question: "Kuat buat GTA V?",
  });
  assert.equal(answer, "Secara kualitatif, cukup mumpuni.");
});

test("starting a request moves the chat into a loading state", () => {
  const state = startHardwareChatRequest(
    createHardwareChatState(),
    "Kuat buat GTA V?"
  );

  assert.equal(state.status, CHAT_STATUS.loading);
  assert.equal(state.lastQuestion, "Kuat buat GTA V?");
  assert.equal(state.error, null);
});

test("successful answers are stored and rendered through the markdown renderer", () => {
  const state = completeHardwareChatRequest(
    startHardwareChatRequest(createHardwareChatState(), "Bisa buat editing video?"),
    "## Ya\n\n**Solid** untuk beban kerja ini."
  );

  assert.equal(state.status, CHAT_STATUS.success);
  assert.equal(state.answeredQuestion, "Bisa buat editing video?");
  assert.equal(state.question, "");
  assert.equal(state.answer, "## Ya\n\n**Solid** untuk beban kerja ini.");
  assert.deepEqual(parseMarkdown(state.answer)[0], {
    type: "heading",
    level: 2,
    children: [{ type: "text", value: "Ya" }],
  });
});

test("422 validation failures are exposed to the UI", async () => {
  await assert.rejects(
    requestHardwareChatAnswer(context, "q", async () => ({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Unrecognized field." }),
    })),
    (error) =>
      error instanceof HardwareChatError &&
      error.kind === CHAT_ERROR_KIND.validation &&
      error.status === 422
  );
});

test("502 and 503 provider failures are exposed to the UI", async () => {
  for (const status of [502, 503]) {
    await assert.rejects(
      requestHardwareChatAnswer(context, "q", async () => ({
        ok: false,
        status,
        json: async () => ({ detail: "AI provider failed." }),
      })),
      (error) =>
        error instanceof HardwareChatError &&
        error.kind === CHAT_ERROR_KIND.provider &&
        error.status === status
    );
  }
});

test("other request failures are reported as request errors", async () => {
  await assert.rejects(
    requestHardwareChatAnswer(context, "q", async () => ({
      ok: false,
      status: 500,
      json: async () => ({}),
    })),
    (error) =>
      error instanceof HardwareChatError &&
      error.kind === CHAT_ERROR_KIND.request &&
      error.status === 500
  );
});

test("failed requests can be retried with the same question", () => {
  const failed = failHardwareChatRequest(
    startHardwareChatRequest(createHardwareChatState(), "Cocok buat Figma?"),
    new HardwareChatError("provider down", CHAT_ERROR_KIND.provider, 503)
  );

  assert.equal(failed.status, CHAT_STATUS.error);
  assert.equal(failed.error.kind, CHAT_ERROR_KIND.provider);

  const retried = startHardwareChatRequest(failed, failed.lastQuestion);
  assert.equal(retried.status, CHAT_STATUS.loading);
  assert.equal(retried.lastQuestion, "Cocok buat Figma?");
  assert.equal(retried.error, null);
});

test("stale responses never overwrite the latest answer", () => {
  const guard = createChatRequestGuard();
  const staleRequestId = guard.begin();
  const currentRequestId = guard.begin();

  assert.equal(guard.isCurrent(staleRequestId), false);
  assert.equal(guard.isCurrent(currentRequestId), true);

  let chatState = startHardwareChatRequest(
    createHardwareChatState(),
    "Question A"
  );
  chatState = startHardwareChatRequest(chatState, "Question B");

  if (guard.isCurrent(staleRequestId)) {
    chatState = completeHardwareChatRequest(chatState, "Answer A");
  }
  assert.equal(chatState.status, CHAT_STATUS.loading);

  if (guard.isCurrent(currentRequestId)) {
    chatState = completeHardwareChatRequest(chatState, "Answer B");
  }
  assert.equal(chatState.status, CHAT_STATUS.success);
  assert.equal(chatState.answer, "Answer B");
});

test("invalidating a guard drops pending requests", () => {
  const guard = createChatRequestGuard();
  const requestId = guard.begin();

  guard.invalidate();

  assert.equal(guard.isCurrent(requestId), false);
});

test("empty and malformed answers are rejected", async () => {
  for (const answer of ["", "   ", null, 42, undefined]) {
    await assert.rejects(
      requestHardwareChatAnswer(context, "q", async () => ({
        ok: true,
        json: async () => ({ answer }),
      })),
      (error) =>
        error instanceof HardwareChatError &&
        error.kind === CHAT_ERROR_KIND.empty
    );
  }
});