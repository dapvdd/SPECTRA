import test from "node:test";
import assert from "node:assert/strict";
import { setImmediate as scheduleImmediate } from "node:timers/promises";

import {
  BUILD_CHAT_CONVERSATION_ERROR_KIND,
  BUILD_CHAT_CONVERSATION_STATUS,
  BUILD_CHAT_HISTORY_MAX_MESSAGES,
  BUILD_CHAT_MESSAGE_ROLE,
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  buildBuildChatHistory,
  completeBuildChatConversationLoad,
  completeBuildChatConversationSave,
  completeBuildChatRequest,
  createBuildChatState,
  createChatRequestGuard,
  createEmptyBuildChatAnalysis,
  createEmptyBuildChatEvidence,
  failBuildChatConversationLoad,
  failBuildChatConversationReset,
  failBuildChatConversationSave,
  getBuildChatConversationError,
  getBuildChatConversationId,
  getBuildChatHistory,
  getLastBuildChatTurn,
  getBuildChatToken,
  isBuildChatRestoringConversation,
  isSameBuildChatToken,
  requestBuildChatAnswer,
  startBuildChatConversationLoad,
  startBuildChatRequest,
} from "./buildChat.js";
import {
  BuildConversationError,
  appendBuildConversationTurn,
  buildBuildTurnPayload,
  ensureBuildConversation,
  getBuildConversationErrorKindFromError,
  requestBuildConversation,
  requestBuildConversationMessages,
  resetBuildConversationMessages,
  restoreBuildConversationMessages,
} from "./buildConversation.js";
import { getBuildChatSnapshot } from "./buildConfig.js";

const CPU_ID = 41;
const GPU_ID = 77;
const CONVERSATION_ID = 9;

const BUILD_TOKEN = "41:77:gaming:1440p";
const OTHER_BUILD_TOKEN = "41:78:gaming:1440p";

const jsonResponse = (payload, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => payload,
});

const conversationPayload = (overrides = {}) => ({
  id: CONVERSATION_ID,
  cpu_hardware_id: CPU_ID,
  gpu_hardware_id: GPU_ID,
  created_at: "2026-09-30T10:00:00",
  updated_at: "2026-09-30T10:05:00",
  ...overrides,
});

const storedMessage = (index, overrides = {}) => ({
  id: index + 1,
  conversation_id: CONVERSATION_ID,
  role: index % 2 === 0 ? "user" : "assistant",
  content: index % 2 === 0 ? `Pertanyaan ${index}?` : `Jawaban ${index}.`,
  evidence: index % 2 === 0 ? null : { known_facts: [], interpretation: [], unknown: [] },
  analysis:
    index % 2 === 0
      ? null
      : { strengths: [], considerations: [], data_gaps: [] },
  created_at: `2026-09-30T10:0${index}:00`,
  ...overrides,
});

const storedTurn = (index) => [
  storedMessage(index),
  storedMessage(index + 1),
];

const createFetchLog = (responses) => {
  const calls = [];
  const queue = [...responses];

  const fetchImplementation = async (url, options = {}) => {
    calls.push({
      url,
      method: options.method ?? "GET",
      body: options.body ? JSON.parse(options.body) : null,
    });

    const next = queue.length > 1 ? queue.shift() : queue[0];

    if (typeof next === "function") {
      return next(url, options);
    }

    return next;
  };

  return { calls, fetchImplementation };
};

/* ---------- stored message normalization ---------- */

test("a stored conversation is restored with evidence and analysis", () => {
  const messages = restoreBuildConversationMessages([
    storedMessage(0),
    storedMessage(1, {
      content: "Karikernya didominasi komponen yang tersedia.",
      evidence: {
        known_facts: ["CPU 6 cores / 12 threads."],
        interpretation: ["Kapasitas multi-core tersimpan."],
        unknown: ["FPS pada 1440p."],
      },
      analysis: {
        strengths: ["Multi-core tersimpan."],
        considerations: ["Data FPS tidak tersedia."],
        data_gaps: ["Benchmark GPU."],
      },
    }),
  ]);

  assert.deepEqual(messages, [
    {
      id: "build-chat-message-1",
      role: BUILD_CHAT_MESSAGE_ROLE.user,
      content: "Pertanyaan 0?",
    },
    {
      id: "build-chat-message-2",
      role: BUILD_CHAT_MESSAGE_ROLE.assistant,
      content: "Karikernya didominasi komponen yang tersedia.",
      evidence: {
        knownFacts: ["CPU 6 cores / 12 threads."],
        interpretation: ["Kapasitas multi-core tersimpan."],
        unknown: ["FPS pada 1440p."],
      },
      analysis: {
        strengths: ["Multi-core tersimpan."],
        considerations: ["Data FPS tidak tersedia."],
        dataGaps: ["Benchmark GPU."],
      },
    },
  ]);
});

test("a stored assistant message without evidence restores empty sections", () => {
  const messages = restoreBuildConversationMessages([
    storedMessage(1, { evidence: null, analysis: null }),
  ]);

  assert.deepEqual(messages[0].evidence, createEmptyBuildChatEvidence());
  assert.deepEqual(messages[0].analysis, createEmptyBuildChatAnalysis());
});

test("an empty stored conversation restores no messages", () => {
  assert.deepEqual(restoreBuildConversationMessages([]), []);
});

test("an unreadable stored history is rejected instead of guessed", () => {
  const invalidPayloads = [
    null,
    {},
    [{ ...storedMessage(0), role: "system" }],
    [{ ...storedMessage(0), content: "   " }],
    [{ ...storedMessage(0), id: 0 }],
    [{ ...storedMessage(0), conversation_id: null }],
    [{ ...storedMessage(1), evidence: { known_facts: "bukan array" } }],
    [{ ...storedMessage(1), analysis: { strengths: ["x".repeat(501)] } }],
  ];

  for (const payload of invalidPayloads) {
    assert.throws(
      () => restoreBuildConversationMessages(payload),
      (error) =>
        error instanceof BuildConversationError &&
        error.kind === CHAT_ERROR_KIND.provider
    );
  }
});

/* ---------- conversation identity ---------- */

test("a conversation is created for the requested CPU and GPU", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload()),
  ]);

  const conversation = await requestBuildConversation(
    CPU_ID,
    GPU_ID,
    fetchImplementation
  );

  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/build\/conversations$/);
  assert.equal(calls[0].method, "POST");
  assert.deepEqual(calls[0].body, {
    cpu_hardware_id: CPU_ID,
    gpu_hardware_id: GPU_ID,
  });
  assert.deepEqual(conversation, {
    id: CONVERSATION_ID,
    cpuHardwareId: CPU_ID,
    gpuHardwareId: GPU_ID,
  });
});

test("a conversation for a different build identity is rejected", async () => {
  const { fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload({ gpu_hardware_id: GPU_ID + 1 })),
  ]);

  await assert.rejects(
    () => requestBuildConversation(CPU_ID, GPU_ID, fetchImplementation),
    (error) =>
      error instanceof BuildConversationError &&
      error.kind === CHAT_ERROR_KIND.provider
  );
});

test("a conversation request needs a CPU and a GPU id", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload()),
  ]);

  for (const [cpuId, gpuId] of [
    [null, GPU_ID],
    [CPU_ID, null],
    [0, GPU_ID],
    [CPU_ID, "77"],
  ]) {
    await assert.rejects(
      () => requestBuildConversation(cpuId, gpuId, fetchImplementation),
      (error) =>
        error instanceof BuildConversationError &&
        error.kind === CHAT_ERROR_KIND.validation
    );
  }

  assert.equal(calls.length, 0);
});

test("an unusable conversation response is rejected", async () => {
  for (const payload of [null, {}, { id: 0 }, conversationPayload({ id: "9" })]) {
    const { fetchImplementation } = createFetchLog([jsonResponse(payload)]);

    await assert.rejects(
      () => requestBuildConversation(CPU_ID, GPU_ID, fetchImplementation),
      (error) =>
        error instanceof BuildConversationError &&
        error.kind === CHAT_ERROR_KIND.provider
    );
  }
});

test("a failed conversation request reports the http failure", async () => {
  const { fetchImplementation } = createFetchLog([jsonResponse({}, 500)]);

  await assert.rejects(
    () => requestBuildConversation(CPU_ID, GPU_ID, fetchImplementation),
    (error) => {
      assert.equal(error.kind, CHAT_ERROR_KIND.request);
      assert.equal(error.status, 500);
      assert.equal(
        getBuildConversationErrorKindFromError(error),
        CHAT_ERROR_KIND.request
      );
      return true;
    }
  );
});

test("an unreachable api reports a request failure", async () => {
  const fetchImplementation = async () => {
    throw new Error("network down");
  };

  await assert.rejects(
    () => requestBuildConversation(CPU_ID, GPU_ID, fetchImplementation),
    (error) =>
      error instanceof BuildConversationError &&
      error.kind === CHAT_ERROR_KIND.request &&
      error.message === "network down"
  );
});

test("a known conversation is reused instead of created again", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload()),
  ]);

  const conversationId = await ensureBuildConversation(
    CONVERSATION_ID,
    CPU_ID,
    GPU_ID,
    fetchImplementation
  );

  assert.equal(conversationId, CONVERSATION_ID);
  assert.equal(calls.length, 0);
});

test("an unknown conversation is created on the first interaction", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload()),
  ]);

  const conversationId = await ensureBuildConversation(
    null,
    CPU_ID,
    GPU_ID,
    fetchImplementation
  );

  assert.equal(conversationId, CONVERSATION_ID);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].method, "POST");
});

/* ---------- history loading ---------- */

test("a stored history is loaded in chronological order", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse([...storedTurn(0), ...storedTurn(2)]),
  ]);

  const messages = await requestBuildConversationMessages(
    CONVERSATION_ID,
    fetchImplementation
  );

  assert.match(calls[0].url, new RegExp(`/build/conversations/${CONVERSATION_ID}/messages$`));
  assert.equal(calls[0].method, "GET");
  assert.deepEqual(
    messages.map((message) => [message.role, message.content]),
    [
      ["user", "Pertanyaan 0?"],
      ["assistant", "Jawaban 1."],
      ["user", "Pertanyaan 2?"],
      ["assistant", "Jawaban 3."],
    ]
  );
});

test("loading a history needs a conversation id", async () => {
  const { calls, fetchImplementation } = createFetchLog([jsonResponse([])]);

  for (const conversationId of [null, 0, "9"]) {
    await assert.rejects(
      () => requestBuildConversationMessages(conversationId, fetchImplementation),
      (error) => error.kind === CHAT_ERROR_KIND.validation
    );
  }

  assert.equal(calls.length, 0);
});

/* ---------- turn persistence ---------- */

test("a build turn is stored with the evidence and analysis of the answer", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse({
      conversation_id: CONVERSATION_ID,
      user_message: storedMessage(0, { content: "Bagaimana karakter build ini?" }),
      assistant_message: storedMessage(1, {
        content: "Karikernya didominasi komponen yang tersedia.",
        evidence: { known_facts: ["CPU 6 cores / 12 threads."], interpretation: [], unknown: [] },
        analysis: { strengths: ["Multi-core tersimpan."], considerations: [], data_gaps: [] },
      }),
    }, 201),
  ]);

  const turn = buildBuildTurnPayload("  Bagaimana karakter build ini?  ", {
    answer: "  Karikernya didominasi komponen yang tersedia.  ",
    evidence: {
      knownFacts: ["CPU 6 cores / 12 threads."],
      interpretation: [],
      unknown: [],
    },
    analysis: {
      strengths: ["Multi-core tersimpan."],
      considerations: [],
      dataGaps: [],
    },
  });

  const messages = await appendBuildConversationTurn(
    CONVERSATION_ID,
    turn,
    fetchImplementation
  );

  assert.match(calls[0].url, new RegExp(`/build/conversations/${CONVERSATION_ID}/turn$`));
  assert.deepEqual(calls[0].body, {
    question: "Bagaimana karakter build ini?",
    answer: "Karikernya didominasi komponen yang tersedia.",
    evidence: {
      known_facts: ["CPU 6 cores / 12 threads."],
      interpretation: [],
      unknown: [],
    },
    analysis: {
      strengths: ["Multi-core tersimpan."],
      considerations: [],
      data_gaps: [],
    },
  });
  assert.deepEqual(
    messages.map((message) => message.role),
    [BUILD_CHAT_MESSAGE_ROLE.user, BUILD_CHAT_MESSAGE_ROLE.assistant]
  );
  assert.deepEqual(messages[1].evidence.knownFacts, [
    "CPU 6 cores / 12 threads.",
  ]);
});

test("a build turn without a question or an answer is refused", () => {
  for (const [question, result] of [
    ["   ", { answer: "Jawaban." }],
    ["Pertanyaan?", { answer: "   " }],
    ["Pertanyaan?", {}],
  ]) {
    assert.throws(
      () => buildBuildTurnPayload(question, result),
      (error) =>
        error instanceof BuildConversationError &&
        error.kind === CHAT_ERROR_KIND.validation
    );
  }
});

test("a build turn is only saved for a known conversation", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload(), 201),
  ]);

  await assert.rejects(
    () =>
      appendBuildConversationTurn(
        null,
        buildBuildTurnPayload("Pertanyaan?", { answer: "Jawaban." }),
        fetchImplementation
      ),
    (error) => error.kind === CHAT_ERROR_KIND.validation
  );

  assert.equal(calls.length, 0);
});

/* ---------- reset ---------- */

test("a new conversation clears the stored messages", async () => {
  const { calls, fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload()),
  ]);

  const conversation = await resetBuildConversationMessages(
    CONVERSATION_ID,
    fetchImplementation
  );

  assert.match(calls[0].url, new RegExp(`/build/conversations/${CONVERSATION_ID}/reset$`));
  assert.equal(calls[0].method, "POST");
  assert.deepEqual(conversation, {
    id: CONVERSATION_ID,
    cpuHardwareId: CPU_ID,
    gpuHardwareId: GPU_ID,
  });
});

/* ---------- conversation state ---------- */

const idle = (buildToken = BUILD_TOKEN) => createBuildChatState(buildToken);

test("a build chat state carries a conversation identity", () => {
  const state = idle();

  assert.equal(state.conversationId, null);
  assert.equal(getBuildChatConversationId(state), null);
  assert.equal(state.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.idle);
  assert.equal(getBuildChatConversationError(state), null);
  assert.equal(isBuildChatRestoringConversation(state), false);
});

test("loading a stored conversation restores the messages and the id", () => {
  const messages = restoreBuildConversationMessages([...storedTurn(0)]);
  const loading = startBuildChatConversationLoad(idle(), BUILD_TOKEN);

  assert.equal(loading.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.loading);
  assert.equal(isBuildChatRestoringConversation(loading), true);

  const restored = completeBuildChatConversationLoad(
    loading,
    CONVERSATION_ID,
    messages,
    BUILD_TOKEN
  );

  assert.equal(getBuildChatConversationId(restored), CONVERSATION_ID);
  assert.equal(restored.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.ready);
  assert.deepEqual(restored.messages, messages);
  assert.equal(restored.status, CHAT_STATUS.idle);
});

test("a restored conversation keeps the bounded history contract", () => {
  const messages = restoreBuildConversationMessages(
    Array.from({ length: 14 }, (_, index) => storedMessage(index))
  );
  const restored = completeBuildChatConversationLoad(
    idle(),
    CONVERSATION_ID,
    messages,
    BUILD_TOKEN
  );

  assert.equal(restored.messages.length, 14);

  const history = getBuildChatHistory(restored);

  assert.equal(history.length, BUILD_CHAT_HISTORY_MAX_MESSAGES);
  assert.equal(history[0].role, BUILD_CHAT_MESSAGE_ROLE.user);
});

test("an unreadable stored history is never invented into the conversation", () => {
  const loading = startBuildChatConversationLoad(idle(), BUILD_TOKEN);
  const rejected = completeBuildChatConversationLoad(
    loading,
    CONVERSATION_ID,
    null,
    BUILD_TOKEN
  );
  const blankContent = completeBuildChatConversationLoad(
    loading,
    CONVERSATION_ID,
    [{ id: "build-chat-message-1", role: "user", content: "  " }],
    BUILD_TOKEN
  );

  assert.deepEqual(rejected.messages, []);
  assert.equal(getBuildChatConversationId(rejected), null);
  assert.equal(rejected.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.loading);
  assert.deepEqual(blankContent.messages, []);
  assert.equal(getBuildChatConversationId(blankContent), null);
});

test("a failed load is recoverable and reports no history", () => {
  const loading = startBuildChatConversationLoad(idle(), BUILD_TOKEN);
  const failed = failBuildChatConversationLoad(
    loading,
    new Error("The stored conversation could not be read."),
    BUILD_TOKEN
  );

  assert.equal(failed.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.error);
  assert.equal(
    getBuildChatConversationError(failed).kind,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.load
  );
  assert.deepEqual(failed.messages, []);
  assert.equal(getBuildChatConversationId(failed), null);
  assert.equal(failed.status, CHAT_STATUS.idle);
  assert.equal(isBuildChatRestoringConversation(failed), false);
});

test("a stale load is ignored when the build changes while it is in flight", () => {
  const loading = startBuildChatConversationLoad(idle(BUILD_TOKEN), BUILD_TOKEN);
  const afterChange = createBuildChatState(OTHER_BUILD_TOKEN);

  assert.equal(loading.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.loading);
  assert.notEqual(afterChange, loading);

  const staleSuccess = completeBuildChatConversationLoad(
    afterChange,
    CONVERSATION_ID,
    restoreBuildConversationMessages([...storedTurn(0)]),
    BUILD_TOKEN
  );
  const staleFailure = failBuildChatConversationLoad(
    afterChange,
    new Error("stale"),
    BUILD_TOKEN
  );

  assert.equal(staleSuccess, afterChange);
  assert.deepEqual(staleSuccess.messages, []);
  assert.equal(staleFailure, afterChange);
  assert.equal(getBuildChatConversationError(staleFailure), null);
});

test("a save and a reset failure keep the visible transcript", () => {
  const answered = completeBuildChatRequest(
    startBuildChatRequest(idle(), "Bagaimana karakter build ini?", BUILD_TOKEN),
    "Karikernya didominasi komponen yang tersedia.",
    BUILD_TOKEN,
    { knownFacts: ["CPU 6 cores / 12 threads."] },
    { strengths: ["Multi-core tersimpan."] }
  );

  const saveFailed = failBuildChatConversationSave(
    answered,
    new Error("The build turn could not be saved."),
    BUILD_TOKEN
  );
  const resetFailed = failBuildChatConversationReset(
    answered,
    new Error("The new build conversation could not be started."),
    BUILD_TOKEN
  );

  assert.deepEqual(saveFailed.messages, answered.messages);
  assert.equal(
    getBuildChatConversationError(saveFailed).kind,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.save
  );
  assert.equal(
    getBuildChatConversationError(resetFailed).kind,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.reset
  );
  assert.equal(saveFailed.status, CHAT_STATUS.success);
});

test("a saved turn records the conversation id", () => {
  const saved = completeBuildChatConversationSave(idle(), CONVERSATION_ID, BUILD_TOKEN);

  assert.equal(getBuildChatConversationId(saved), CONVERSATION_ID);
  assert.equal(saved.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.ready);
  assert.equal(
    completeBuildChatConversationSave(saved, null, BUILD_TOKEN).conversationId,
    CONVERSATION_ID
  );
});

test("the last exchange can be read back for a save retry", () => {
  const answered = completeBuildChatRequest(
    startBuildChatRequest(idle(), "Bagaimana karakter build ini?", BUILD_TOKEN),
    "Karikernya didominasi komponen yang tersedia.",
    BUILD_TOKEN,
    { knownFacts: ["CPU 6 cores / 12 threads."] },
    { strengths: ["Multi-core tersimpan."] }
  );

  assert.deepEqual(getLastBuildChatTurn(answered), {
    question: "Bagaimana karakter build ini?",
    answer: "Karikernya didominasi komponen yang tersedia.",
    evidence: {
      knownFacts: ["CPU 6 cores / 12 threads."],
      interpretation: [],
      unknown: [],
    },
    analysis: {
      strengths: ["Multi-core tersimpan."],
      considerations: [],
      dataGaps: [],
    },
  });
  assert.equal(getLastBuildChatTurn(idle()), null);
});

/* ---------- app flow ---------- */

const createPersistenceHarness = ({ fetchImplementation, chatResponse }) => {
  const chatGuard = createChatRequestGuard();
  const conversationGuard = createChatRequestGuard();
  const harness = {
    state: createBuildChatState(BUILD_TOKEN),
    token: BUILD_TOKEN,
    conversationId: null,
    restored: null,
    saved: [],
  };

  harness.apply = (nextState) => {
    harness.state = nextState;
    return nextState;
  };

  harness.load = (requestToken = harness.token) => {
    const requestId = conversationGuard.begin();
    harness.apply(startBuildChatConversationLoad(harness.state, requestToken));

    return requestBuildConversation(CPU_ID, GPU_ID, fetchImplementation)
      .then((conversation) =>
        requestBuildConversationMessages(
          conversation.id,
          fetchImplementation
        ).then((messages) => ({ conversation, messages }))
      )
      .then(({ conversation, messages }) => {
        if (!conversationGuard.isCurrent(requestId)) {
          return;
        }
        if (!isSameBuildChatToken(harness.token, requestToken)) {
          return;
        }
        harness.conversationId = conversation.id;
        harness.restored = messages;
        harness.apply(
          completeBuildChatConversationLoad(
            harness.state,
            conversation.id,
            messages,
            requestToken
          )
        );
      })
      .catch((error) => {
        if (!conversationGuard.isCurrent(requestId)) {
          return;
        }
        if (!isSameBuildChatToken(harness.token, requestToken)) {
          return;
        }
        harness.apply(
          failBuildChatConversationLoad(harness.state, error, requestToken)
        );
      });
  };

  harness.ask = (question) => {
    const requestId = chatGuard.begin();
    const requestToken = harness.token;
    const history = buildBuildChatHistory(harness.state.messages);
    const payload = { question, history };

    harness.apply(startBuildChatRequest(harness.state, question, requestToken));

    return requestBuildChatAnswer(payload, chatResponse).then((result) => {
      if (!chatGuard.isCurrent(requestId)) {
        return;
      }
      if (!isSameBuildChatToken(harness.token, requestToken)) {
        return;
      }
      harness.apply(
        completeBuildChatRequest(
          harness.state,
          result.answer,
          requestToken,
          result.evidence,
          result.analysis
        )
      );
      harness.saved.push(payload);
    });
  };

  harness.changeBuild = (nextToken) => {
    chatGuard.invalidate();
    conversationGuard.invalidate();
    harness.token = nextToken;
    harness.conversationId = null;
    harness.restored = null;
    return harness.apply(createBuildChatState(nextToken));
  };

  harness.settle = () => scheduleImmediate();

  return harness;
};

const chatResponseWith = (answer) => async () => ({
  ok: true,
  json: async () => ({
    answer,
    evidence: { known_facts: ["CPU 6 cores / 12 threads."], interpretation: [], unknown: [] },
    analysis: { strengths: [], considerations: [], data_gaps: [] },
  }),
});

test("a reloaded build restores the stored conversation and then extends it", async () => {
  const { fetchImplementation, calls } = createFetchLog([
    (url) =>
      url.endsWith("/messages")
        ? jsonResponse([...storedTurn(0)])
        : jsonResponse(conversationPayload()),
  ]);
  const harness = createPersistenceHarness({
    fetchImplementation,
    chatResponse: chatResponseWith("Karikernya konsisten."),
  });

  await harness.load();
  await harness.settle();

  assert.equal(harness.state.conversationId, CONVERSATION_ID);
  assert.equal(harness.state.messages.length, 2);
  assert.equal(harness.state.messages[0].content, "Pertanyaan 0?");
  assert.equal(harness.state.messages[1].role, BUILD_CHAT_MESSAGE_ROLE.assistant);
  assert.equal(calls.length, 2);

  await harness.ask("Apakah ada data FPS?");
  await harness.settle();

  assert.equal(harness.state.messages.length, 4);
  assert.equal(harness.state.status, CHAT_STATUS.success);
  assert.deepEqual(harness.saved[0].history, [
    { role: BUILD_CHAT_MESSAGE_ROLE.user, content: "Pertanyaan 0?" },
    { role: BUILD_CHAT_MESSAGE_ROLE.assistant, content: "Jawaban 1." },
  ]);
});

test("a build change discards the previous conversation before the load resolves", async () => {
  let releaseMessages = null;
  const gate = new Promise((resolve) => {
    releaseMessages = resolve;
  });
  const { fetchImplementation } = createFetchLog([
    (url) =>
      url.endsWith("/messages")
        ? gate.then(() => jsonResponse([...storedTurn(0)]))
        : jsonResponse(conversationPayload()),
  ]);
  const harness = createPersistenceHarness({
    fetchImplementation,
    chatResponse: chatResponseWith("Karikernya konsisten."),
  });

  const pending = harness.load();
  harness.changeBuild(OTHER_BUILD_TOKEN);
  releaseMessages();
  await pending;
  await harness.settle();

  assert.equal(harness.state.buildToken, OTHER_BUILD_TOKEN);
  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.conversationId, null);
  assert.equal(harness.state.conversation.status, BUILD_CHAT_CONVERSATION_STATUS.idle);
});

test("a failed load is reported and the user can still ask a question", async () => {
  const { fetchImplementation } = createFetchLog([
    jsonResponse(conversationPayload()),
    jsonResponse([], 500),
  ]);
  const harness = createPersistenceHarness({
    fetchImplementation,
    chatResponse: chatResponseWith("Karikernya konsisten."),
  });

  await harness.load();
  await harness.settle();

  const conversationError = getBuildChatConversationError(harness.state);

  assert.equal(
    conversationError.kind,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.load
  );
  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.conversationId, null);

  await harness.ask("Apakah ada data FPS?");
  await harness.settle();

  assert.equal(harness.state.messages.length, 2);
  assert.equal(harness.state.status, CHAT_STATUS.success);
  assert.equal(
    getBuildChatConversationError(harness.state).kind,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.load
  );
});

test("the build token separates two build identities", () => {
  const cpu = { id: CPU_ID, name: "Ryzen 7 7800X3D" };
  const gpu = { id: GPU_ID, name: "GeForce RTX 5070 Ti" };
  const otherGpu = { ...gpu, id: GPU_ID + 1 };
  const context = { useCase: "Gaming", resolution: "1440p" };

  assert.equal(
    getBuildChatToken(getBuildChatSnapshot(cpu, gpu, context)),
    BUILD_TOKEN
  );
  assert.equal(
    getBuildChatToken(getBuildChatSnapshot(cpu, otherGpu, context)),
    OTHER_BUILD_TOKEN
  );
  assert.equal(
    isSameBuildChatToken(
      getBuildChatToken(getBuildChatSnapshot(cpu, gpu, context)),
      getBuildChatToken(getBuildChatSnapshot(cpu, otherGpu, context))
    ),
    false
  );
});
