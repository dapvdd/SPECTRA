import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setImmediate as scheduleImmediate } from "node:timers/promises";

import { apiUrl } from "./api.js";
import { parseMarkdown } from "./markdown.js";
import {
  BUILD_CHAT_ENDPOINT_PATH,
  BUILD_CHAT_MESSAGE_ROLE,
  BUILD_CHAT_SUGGESTED_QUESTIONS,
  BuildChatError,
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  buildChatPayload,
  completeBuildChatRequest,
  createBuildChatState,
  createChatRequestGuard,
  failBuildChatRequest,
  getBuildChatMessages,
  getBuildChatToken,
  getChatLoadingParts,
  hasBuildChatConversation,
  isBuildChatBusy,
  isSameBuildChatToken,
  isValidBuildChatQuestion,
  normalizeBuildChatQuestion,
  requestBuildChatAnswer,
  retryBuildChatRequest,
  startBuildChatRequest,
} from "./buildChat.js";
import {
  addComparisonSelection,
  clearComparisonSelection,
  removeComparisonSelection,
} from "./appState.js";
import {
  completeBuildDetailRequest,
  createBuildConfig,
  createBuildDetailState,
  createBuildUserContext,
  getBuildChatContextSummary,
  getBuildChatSnapshot,
  getBuildSelection,
  setBuildCpu,
  setBuildGpu,
  setBuildResolution,
  setBuildUseCase,
  startBuildDetailRequest,
} from "./buildConfig.js";
import {
  CHAT_STATUS as HARDWARE_CHAT_STATUS,
  buildHardwareChatContext,
  createChatRequestGuard as createHardwareChatGuard,
  createHardwareChatState,
  requestHardwareChatAnswer,
} from "./hardwareChat.js";

const cpuDetail = {
  id: 1,
  name: "Ryzen 7 7800X3D",
  manufacturer: "AMD",
  type: "CPU",
  architecture: "Zen 4",
  release_date: "2023-04-06",
  specifications: {
    cores: 8,
    threads: 16,
    base_clock_ghz: 4.2,
    boost_clock_ghz: 5.0,
    tdp_w: 120,
    socket: "AM5",
    process_node_nm: 5,
  },
};

const gpuDetail = {
  id: 3361,
  name: "GeForce RTX 5070 Ti",
  manufacturer: "NVIDIA",
  type: "GPU",
  architecture: "Blackwell",
  release_date: "2025-02-27",
  specifications: {
    memory_gb: 16,
    memory_type: "GDDR7",
    core_clock_mhz: 2017,
    boost_clock_mhz: 2512,
    vram_bandwidth_gbps: 896,
    tdp_w: 300,
    interface: "PCIe 5.0 x16",
    length_mm: 300,
  },
};

const otherGpuDetail = {
  ...gpuDetail,
  id: 3362,
  name: "GeForce RTX 5080",
};

const userContext = { useCase: "Gaming", resolution: "1440p" };

const cpuBenchmarks = [
  {
    id: 7,
    hardware_id: 1,
    benchmark_name: "Geekbench 7",
    test_type: "single-core",
    score: 2100,
    unit: "points",
    secret_token: "do-not-send",
  },
];

const tokenFor = (cpu = cpuDetail, gpu = gpuDetail, context = userContext) =>
  getBuildChatToken(getBuildChatSnapshot(cpu, gpu, context));

const BUILD_A_TOKEN = "1:3361:gaming:1440p";
const BUILD_B_TOKEN = "1:3362:gaming:1440p";

const idle = (buildToken = BUILD_A_TOKEN) => createBuildChatState(buildToken);

const asking = (question, buildToken = BUILD_A_TOKEN) =>
  startBuildChatRequest(idle(buildToken), question, buildToken);

const answered = (question, answer, buildToken = BUILD_A_TOKEN) =>
  completeBuildChatRequest(asking(question, buildToken), answer, buildToken);

const answering = (fetchImplementation) =>
  requestBuildChatAnswer(
    buildChatPayload(cpuDetail, gpuDetail, userContext, "q", {
      CPU: cpuBenchmarks,
      GPU: [],
    }),
    fetchImplementation
  );

/* ---------- 1. initial idle state ---------- */

test("the conversation starts idle with no messages and no automatic request", () => {
  const state = idle();

  assert.equal(state.buildToken, BUILD_A_TOKEN);
  assert.equal(state.status, CHAT_STATUS.idle);
  assert.deepEqual(state.messages, []);
  assert.equal(state.pendingQuestion, "");
  assert.equal(state.error, null);
  assert.equal(hasBuildChatConversation(state), false);
  assert.equal(isBuildChatBusy(state), false);
  assert.deepEqual(getBuildChatMessages(state), []);
});

test("an omitted build token produces an empty unbound conversation", () => {
  const state = createBuildChatState();

  assert.equal(state.buildToken, "");
  assert.equal(getBuildChatToken(null), "");
  assert.equal(state.status, CHAT_STATUS.idle);
});

/* ---------- 2. suggested questions ---------- */

test("the suggested questions are a fixed deterministic set", () => {
  assert.deepEqual(BUILD_CHAT_SUGGESTED_QUESTIONS, [
    "Bagaimana karakter build ini untuk gaming 1440p?",
    "Apa kelebihan utama CPU dan GPU ini?",
    "Apa yang masih belum bisa disimpulkan dari spesifikasi ini?",
    "Jelaskan build ini berdasarkan data SPECTRA.",
  ]);

  for (const question of BUILD_CHAT_SUGGESTED_QUESTIONS) {
    assert.equal(isValidBuildChatQuestion(question), true);
  }

  assert.deepEqual(BUILD_CHAT_SUGGESTED_QUESTIONS, [
    ...BUILD_CHAT_SUGGESTED_QUESTIONS,
  ]);
  assert.equal(new Set(BUILD_CHAT_SUGGESTED_QUESTIONS).size, 4);
});

/* ---------- 3. custom and suggested question submission ---------- */

test("a custom question produces exactly the API payload for the build", () => {
  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    "Bagaimana karakter build ini?",
    { CPU: cpuBenchmarks, GPU: [] }
  );

  assert.deepEqual(Object.keys(payload).sort(), ["build", "question"]);
  assert.equal(payload.question, "Bagaimana karakter build ini?");
  assert.equal(payload.build.cpu.id, 1);
  assert.equal(payload.build.gpu.id, 3361);
  assert.equal(payload.build.cpu.specifications.cores, 8);
  assert.equal(payload.build.gpu.specifications.memory_gb, 16);
  assert.equal(payload.build.cpu.benchmarks.length, 1);
  assert.equal(payload.build.gpu.benchmarks.length, 0);
  assert.deepEqual(payload.build.context, {
    use_case: "gaming",
    resolution: "1440p",
  });
});

test("a suggested question is submitted exactly like a custom question", () => {
  for (const question of BUILD_CHAT_SUGGESTED_QUESTIONS) {
    const payload = buildChatPayload(
      cpuDetail,
      gpuDetail,
      userContext,
      question,
      { CPU: cpuBenchmarks, GPU: [] }
    );

    assert.equal(payload.question, question);

    const state = answered(
      question,
      "Berdasarkan spesifikasi yang tersimpan.",
      BUILD_A_TOKEN
    );

    assert.equal(state.status, CHAT_STATUS.success);
    assert.equal(state.messages.length, 2);
    assert.equal(state.messages[0].content, question);
  }
});

test("a long custom question is preserved verbatim in the conversation", () => {
  const longQuestion = `Specs ${"detail ".repeat(200).trim()}?`;

  assert.equal(longQuestion.length > 1000, true);
  assert.equal(isValidBuildChatQuestion(longQuestion), true);

  const state = answered(longQuestion, "Jawaban.", BUILD_A_TOKEN);

  assert.equal(state.messages[0].content, longQuestion);
  assert.equal(state.messages[0].content.length, longQuestion.length);
});

/* ---------- 4. 5. 6. empty and whitespace questions ---------- */

test("empty and whitespace-only questions are rejected before any request", () => {
  for (const question of [
    "",
    "   ",
    "\n\t ",
    null,
    undefined,
    42,
    {},
    "x".repeat(2001),
  ]) {
    assert.equal(isValidBuildChatQuestion(question), false);
    assert.throws(
      () => buildChatPayload(cpuDetail, gpuDetail, userContext, question),
      /build chat question/
    );

    const before = idle();
    assert.equal(
      startBuildChatRequest(before, question),
      before,
      "an invalid question must not change state"
    );
    assert.equal(before.status, CHAT_STATUS.idle);
  }

  assert.equal(normalizeBuildChatQuestion("  spaced  "), "spaced");
  assert.equal(isValidBuildChatQuestion("x".repeat(2000)), true);
});

/* ---------- 7. loading state ---------- */

test("starting a request enters loading, keeps messages, and blocks duplicates", () => {
  const withHistory = answered("Pertanyaan pertama.", "Jawaban pertama.");
  const loading = startBuildChatRequest(
    withHistory,
    "Kalau untuk productivity?",
    BUILD_A_TOKEN
  );

  assert.equal(loading.status, CHAT_STATUS.loading);
  assert.equal(loading.pendingQuestion, "Kalau untuk productivity?");
  assert.equal(loading.error, null);
  assert.equal(isBuildChatBusy(loading), true);
  assert.equal(loading.messages.length, 2);
  assert.equal(loading.messages[0].content, "Pertanyaan pertama.");
  assert.equal(
    startBuildChatRequest(loading, "duplikat").status,
    CHAT_STATUS.loading
  );
  assert.equal(retryBuildChatRequest(loading), loading);
});

test("the loading label and the pending question are never the same text", () => {
  const label = "Asking SPECTRA about this build...";

  assert.deepEqual(
    getChatLoadingParts(label, "Kalau untuk productivity?"),
    { label, detail: "Kalau untuk productivity?" }
  );
  assert.equal(
    getChatLoadingParts(label, label).detail,
    "",
    "a question equal to the label must not be rendered twice"
  );
  assert.deepEqual(getChatLoadingParts("Asking SPECTRA..."), {
    label: "Asking SPECTRA...",
    detail: "",
  });
  assert.deepEqual(getChatLoadingParts(label, "   "), { label, detail: "" });
  assert.deepEqual(getChatLoadingParts(label, null), { label, detail: "" });
  assert.equal(
    getChatLoadingParts(label, " 无关  ").detail,
    "无关"
  );
});

/* ---------- 8. 9. success and ordering ---------- */

test("a successful response appends the user message then the answer", () => {
  const state = answered("Jelaskan build ini.", "## Jawaban\n\n**Fakta**.");

  assert.equal(state.status, CHAT_STATUS.success);
  assert.equal(state.pendingQuestion, "");
  assert.equal(state.error, null);
  assert.deepEqual(
    state.messages.map((message) => message.role),
    [BUILD_CHAT_MESSAGE_ROLE.user, BUILD_CHAT_MESSAGE_ROLE.assistant]
  );
  assert.deepEqual(
    state.messages.map((message) => message.id),
    ["build-chat-message-0", "build-chat-message-1"]
  );
  assert.equal(state.messages[0].content, "Jelaskan build ini.");
  assert.equal(state.messages[1].content, "## Jawaban\n\n**Fakta**.");
  assert.equal(hasBuildChatConversation(state), true);
});

/* ---------- 10. follow-up ---------- */

test("a follow-up question appends a second turn in order", () => {
  let state = answered(
    "Bagaimana karakter build ini untuk gaming 1440p?",
    "Konteks gaming 1440p perlu data FPS yang tidak tersedia."
  );
  state = startBuildChatRequest(
    state,
    "Kalau untuk productivity?",
    BUILD_A_TOKEN
  );

  assert.equal(state.messages.length, 2);
  assert.equal(state.status, CHAT_STATUS.loading);

  state = completeBuildChatRequest(
    state,
    "Untuk produktivitas, data yang tersedia adalah spesifikasi.",
    BUILD_A_TOKEN
  );

  assert.equal(state.status, CHAT_STATUS.success);
  assert.equal(state.messages.length, 4);
  assert.deepEqual(
    state.messages.map((message) => message.role),
    [
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
    ]
  );
  assert.deepEqual(
    state.messages.map((message) => message.content),
    [
      "Bagaimana karakter build ini untuk gaming 1440p?",
      "Konteks gaming 1440p perlu data FPS yang tidak tersedia.",
      "Kalau untuk productivity?",
      "Untuk produktivitas, data yang tersedia adalah spesifikasi.",
    ]
  );
  assert.deepEqual(
    state.messages.map((message) => message.id),
    [
      "build-chat-message-0",
      "build-chat-message-1",
      "build-chat-message-2",
      "build-chat-message-3",
    ]
  );
});

test("a completed response without a pending question is not appended", () => {
  const idleState = idle();

  assert.equal(
    completeBuildChatRequest(idleState, "Jawaban tanpa pertanyaan.", BUILD_A_TOKEN),
    idleState
  );
  assert.equal(idleState.messages.length, 0);
});

/* ---------- 11. failed first request ---------- */

test("a failed first request leaves the conversation empty and retryable", () => {
  const state = failBuildChatRequest(
    asking("Apa yang diketahui?", BUILD_A_TOKEN),
    new BuildChatError("provider down", CHAT_ERROR_KIND.provider, 503),
    BUILD_A_TOKEN
  );

  assert.equal(state.status, CHAT_STATUS.error);
  assert.deepEqual(state.messages, []);
  assert.equal(state.pendingQuestion, "Apa yang diketahui?");
  assert.equal(state.error.kind, CHAT_ERROR_KIND.provider);
  assert.equal(state.error.message, "provider down");
  assert.equal(isBuildChatBusy(state), false);
});

/* ---------- 12. failed follow-up preserves prior messages ---------- */

test("a failed follow-up preserves every previous successful message", () => {
  let state = answered("Pertanyaan pertama.", "Jawaban pertama.");
  state = startBuildChatRequest(state, "Pertanyaan kedua.", BUILD_A_TOKEN);
  state = failBuildChatRequest(
    state,
    new BuildChatError("provider down", CHAT_ERROR_KIND.provider, 503),
    BUILD_A_TOKEN
  );

  assert.equal(state.status, CHAT_STATUS.error);
  assert.equal(state.messages.length, 2);
  assert.equal(state.messages[0].content, "Pertanyaan pertama.");
  assert.equal(state.messages[1].content, "Jawaban pertama.");
  assert.equal(state.pendingQuestion, "Pertanyaan kedua.");
  assert.equal(state.error.kind, CHAT_ERROR_KIND.provider);
});

/* ---------- 13. 21. retry ---------- */

test("retry re-asks the same question for the current build", () => {
  const failed = failBuildChatRequest(
    asking("Apa yang diketahui?", BUILD_A_TOKEN),
    new BuildChatError("provider down", CHAT_ERROR_KIND.provider, 503),
    BUILD_A_TOKEN
  );

  const retried = retryBuildChatRequest(failed);

  assert.equal(retried.status, CHAT_STATUS.loading);
  assert.equal(retried.pendingQuestion, "Apa yang diketahui?");
  assert.equal(retried.error, null);
  assert.equal(retried.buildToken, BUILD_A_TOKEN);

  const succeeded = completeBuildChatRequest(
    retried,
    "Hanya spesifikasi yang tersimpan.",
    BUILD_A_TOKEN
  );

  assert.equal(succeeded.status, CHAT_STATUS.success);
  assert.equal(succeeded.messages.length, 2);
  assert.equal(succeeded.messages[0].content, "Apa yang diketahui?");
});

test("retry is a no-op without a pending question or while already loading", () => {
  const idleState = idle();

  assert.equal(retryBuildChatRequest(idleState), idleState);

  const loading = asking("q", BUILD_A_TOKEN);
  assert.equal(retryBuildChatRequest(loading), loading);

  const failed = failBuildChatRequest(
    asking("q2", BUILD_A_TOKEN),
    new BuildChatError("x", CHAT_ERROR_KIND.request),
    BUILD_A_TOKEN
  );

  assert.equal(retryBuildChatRequest(failed).status, CHAT_STATUS.loading);
});

test("retry against a changed build has nothing to re-ask", () => {
  const reset = idle(BUILD_B_TOKEN);

  assert.equal(reset.pendingQuestion, "");
  assert.equal(retryBuildChatRequest(reset), reset);
  assert.equal(reset.messages.length, 0);
});

/* ---------- 14-17. context change resets ---------- */

test("a CPU change resets the conversation to the new build identity", () => {
  const withHistory = answered("Pertanyaan lama.", "Jawaban lama.");
  const cpuChanged = idle("9:3361:gaming:1440p");

  assert.equal(cpuChanged.messages.length, 0);
  assert.equal(cpuChanged.status, CHAT_STATUS.idle);
  assert.equal(cpuChanged.error, null);
  assert.equal(cpuChanged.pendingQuestion, "");
  assert.equal(cpuChanged.buildToken, "9:3361:gaming:1440p");
  assert.notEqual(withHistory.buildToken, cpuChanged.buildToken);
});

test("a GPU change resets the conversation to the new build identity", () => {
  const gpuChanged = idle(BUILD_B_TOKEN);

  assert.equal(gpuChanged.messages.length, 0);
  assert.equal(gpuChanged.buildToken, BUILD_B_TOKEN);
  assert.equal(isSameBuildChatToken(BUILD_B_TOKEN, BUILD_A_TOKEN), false);
});

test("a use case change resets the conversation to the new build identity", () => {
  const useCaseChanged = idle("1:3361:productivity:1440p");

  assert.equal(useCaseChanged.messages.length, 0);
  assert.equal(useCaseChanged.status, CHAT_STATUS.idle);
  assert.equal(useCaseChanged.buildToken, "1:3361:productivity:1440p");
});

test("a resolution change resets the conversation to the new build identity", () => {
  const resolutionChanged = idle("1:3361:gaming:1080p");

  assert.equal(resolutionChanged.messages.length, 0);
  assert.equal(resolutionChanged.status, CHAT_STATUS.idle);
  assert.equal(resolutionChanged.buildToken, "1:3361:gaming:1080p");
});

/* ---------- 18-20. 17. stale responses ---------- */

test("a stale success is ignored when the GPU changes before the response", async () => {
  const guard = createChatRequestGuard();
  const requestId = guard.begin();
  const requestToken = tokenFor(cpuDetail, gpuDetail, userContext);

  assert.equal(requestToken, BUILD_A_TOKEN);

  let state = startBuildChatRequest(
    createBuildChatState(BUILD_A_TOKEN),
    "Bagaimana karakter build ini?",
    requestToken
  );

  // The user changes the GPU while the request is in flight.
  guard.invalidate();
  let currentToken = tokenFor(cpuDetail, otherGpuDetail, userContext);
  assert.equal(currentToken, BUILD_B_TOKEN);
  state = createBuildChatState(currentToken);

  // The old response arrives.
  if (guard.isCurrent(requestId)) {
    state = completeBuildChatRequest(state, "Jawaban untuk build lama.", requestToken);
  }
  assert.equal(isSameBuildChatToken(currentToken, requestToken), false);

  assert.equal(state.messages.length, 0);
  assert.equal(state.status, CHAT_STATUS.idle);
  assert.equal(state.error, null);
  assert.equal(state.buildToken, BUILD_B_TOKEN);
});

test("a stale failure is ignored when the GPU changes before the response", () => {
  const guard = createChatRequestGuard();
  const requestId = guard.begin();
  const requestToken = tokenFor(cpuDetail, gpuDetail, userContext);

  guard.invalidate();
  let state = createBuildChatState(BUILD_B_TOKEN);

  if (guard.isCurrent(requestId)) {
    state = failBuildChatRequest(
      state,
      new BuildChatError("stale", CHAT_ERROR_KIND.provider, 503),
      requestToken
    );
  }

  assert.equal(state.status, CHAT_STATUS.idle);
  assert.equal(state.error, null);
  assert.equal(state.messages.length, 0);
  assert.equal(state.buildToken, BUILD_B_TOKEN);
});

test("a stale loading completion is ignored when the CPU changes", () => {
  const requestToken = tokenFor(cpuDetail, gpuDetail, userContext);
  const loading = startBuildChatRequest(
    createBuildChatState(requestToken),
    "Pertanyaan berjalan",
    requestToken
  );

  assert.equal(loading.status, CHAT_STATUS.loading);

  const currentToken = tokenFor(
    { ...cpuDetail, id: 42 },
    gpuDetail,
    userContext
  );
  assert.equal(currentToken, "42:3361:gaming:1440p");

  const afterChange = createBuildChatState(currentToken);
  const applied = completeBuildChatRequest(
    afterChange,
    "Jawaban untuk CPU lama.",
    requestToken
  );

  assert.equal(applied.messages.length, 0);
  assert.equal(applied.status, CHAT_STATUS.idle);
  assert.equal(applied.buildToken, currentToken);
});

test("a response without a token still applies to its own conversation", () => {
  const state = completeBuildChatRequest(
    asking("q", BUILD_A_TOKEN),
    "Jawaban."
  );

  assert.equal(state.messages.length, 2);
});

/* ---------- 22. build identity ---------- */

test("the build identity token is deterministic for the current build", () => {
  assert.equal(
    getBuildChatToken(
      getBuildChatSnapshot(cpuDetail, gpuDetail, {
        useCase: "Gaming",
        resolution: "1440p",
      })
    ),
    "1:3361:gaming:1440p"
  );
  assert.equal(
    getBuildChatToken(
      getBuildChatSnapshot(cpuDetail, gpuDetail, {
        useCase: "Gaming",
        resolution: "1440p",
      })
    ),
    getBuildChatToken(
      getBuildChatSnapshot(cpuDetail, gpuDetail, {
        useCase: "Gaming",
        resolution: "1440p",
      })
    )
  );
});

test("the build identity token changes for each build dimension", () => {
  const base = tokenFor();

  assert.notEqual(tokenFor({ ...cpuDetail, id: 42 }, gpuDetail), base);
  assert.notEqual(tokenFor(cpuDetail, otherGpuDetail), base);
  assert.notEqual(
    tokenFor(cpuDetail, gpuDetail, { ...userContext, useCase: "Productivity" }),
    base
  );
  assert.notEqual(
    tokenFor(cpuDetail, gpuDetail, { ...userContext, resolution: "1080p" }),
    base
  );
  assert.equal(
    tokenFor(cpuDetail, gpuDetail, { ...userContext, useCase: "Not specified" }),
    "1:3361:unspecified:1440p"
  );
  assert.equal(tokenFor(null, null, null), "none:none:unspecified:unspecified");
  assert.equal(isSameBuildChatToken(base, tokenFor()), true);
  assert.equal(isSameBuildChatToken(base, "1:3361:gaming:unspecified"), false);
});

/* ---------- 23-25. isolation ---------- */

test("a conversation never changes the build configuration state", () => {
  let build = setBuildCpu(createBuildConfig(), {
    id: 1,
    name: cpuDetail.name,
    type: "CPU",
  });
  build = setBuildGpu(build, {
    id: 3361,
    name: gpuDetail.name,
    type: "GPU",
  });
  const before = JSON.stringify(build);

  const state = answered(
    "Bagaimana karakter build ini?",
    "Jawaban.",
    getBuildChatToken(getBuildChatSnapshot(cpuDetail, gpuDetail, userContext))
  );

  assert.equal(state.status, CHAT_STATUS.success);
  assert.equal(JSON.stringify(build), before);
  assert.equal(getBuildSelection(build, "CPU").id, 1);
  assert.equal(getBuildSelection(build, "GPU").id, 3361);
});

test("a conversation never changes comparison selection or detail requests", () => {
  const compareList = addComparisonSelection(
    addComparisonSelection([], { id: 11, name: "Ryzen 9 9950X", type: "CPU" }),
    { id: 12, name: "Ryzen 7 7800X3D", type: "CPU" }
  );
  const before = JSON.stringify(compareList);

  answered("q", "a", BUILD_A_TOKEN);
  failBuildChatRequest(
    asking("q2", BUILD_A_TOKEN),
    new BuildChatError("x", CHAT_ERROR_KIND.request),
    BUILD_A_TOKEN
  );
  startBuildChatRequest(idle(BUILD_B_TOKEN), "q3", BUILD_B_TOKEN);

  assert.equal(JSON.stringify(compareList), before);
  assert.equal(compareList.length, 2);
  assert.equal(compareList.some((item) => item.id === 1), false);
  assert.equal(compareList.some((item) => item.id === 3361), false);
  assert.equal(removeComparisonSelection(compareList, 11).length, 1);
  assert.deepEqual(clearComparisonSelection(), []);
  assert.equal(compareList.length, 2);
});

test("build chat detail state is not mutated by conversation activity", () => {
  let state = startBuildDetailRequest(createBuildDetailState(), "CPU", 1);
  state = completeBuildDetailRequest(state, "CPU", 1, cpuDetail);
  state = startBuildDetailRequest(state, "GPU", 1);
  state = completeBuildDetailRequest(state, "GPU", 1, gpuDetail);
  const before = JSON.stringify(state);

  buildChatPayload(
    state.detailsBySlot.CPU,
    state.detailsBySlot.GPU,
    createBuildUserContext(),
    "q",
    { CPU: cpuBenchmarks, GPU: [] }
  );
  answered("q", "a", BUILD_A_TOKEN);

  assert.equal(JSON.stringify(state), before);
  assert.equal(state.detailsBySlot.CPU.id, 1);
  assert.equal(state.detailsBySlot.GPU.id, 3361);
});

test("hardware chat stays on its own endpoint and state shape", async () => {
  const buildRequests = [];
  const hardwareRequests = [];

  await answering(async (url, options) => {
    buildRequests.push({ url, options });
    return { ok: true, json: async () => ({ answer: "Build answer." }) };
  });

  const hardwareChatState = createHardwareChatState();
  assert.equal(hardwareChatState.status, HARDWARE_CHAT_STATUS.idle);
  assert.equal(hardwareChatState.messages, undefined);
  assert.equal(hardwareChatState.answeredQuestion, "");

  await requestHardwareChatAnswer(
    buildHardwareChatContext(cpuDetail, cpuBenchmarks),
    "q",
    async (url, options) => {
      hardwareRequests.push({ url, options });
      return { ok: true, json: async () => ({ answer: "Hardware answer." }) };
    }
  );

  assert.equal(buildRequests.length, 1);
  assert.equal(buildRequests[0].url, apiUrl("/build/chat"));
  assert.equal(hardwareRequests.length, 1);
  assert.equal(hardwareRequests[0].url, apiUrl("/hardware/chat"));
  assert.notEqual(buildRequests[0].url, hardwareRequests[0].url);

  assert.deepEqual(Object.keys(JSON.parse(buildRequests[0].options.body)).sort(), [
    "build",
    "question",
  ]);
  assert.deepEqual(
    Object.keys(JSON.parse(hardwareRequests[0].options.body)).sort(),
    ["hardware", "question"]
  );

  const buildGuard = createChatRequestGuard();
  const hardwareGuard = createHardwareChatGuard();
  assert.equal(buildGuard.begin(), 1);
  assert.equal(hardwareGuard.begin(), 1);
});

/* ---------- 26-28. rendering ---------- */

test("assistant markdown uses the existing renderer and stays plain data", () => {
  const markdown = "## Ringkasan\n\n**Fakta** tersimpan.\n\n- cores: 8\n- threads: 16";
  const state = answered("q", markdown);
  const assistant = state.messages[1];

  assert.equal(assistant.role, BUILD_CHAT_MESSAGE_ROLE.assistant);
  assert.equal(assistant.content, markdown);

  const blocks = parseMarkdown(assistant.content);

  assert.deepEqual(blocks[0], {
    type: "heading",
    level: 2,
    children: [{ type: "text", value: "Ringkasan" }],
  });
  assert.equal(blocks[1].type, "paragraph");
  assert.deepEqual(blocks[1].children, [
    { type: "bold", value: "Fakta" },
    { type: "text", value: " tersimpan." },
  ]);
  assert.equal(blocks[2].type, "list");
  assert.equal(blocks[2].items.length, 2);

  const rendered = JSON.stringify(blocks);
  assert.equal(rendered.includes("<script"), false);
  assert.equal(rendered.includes("dangerouslySetInnerHTML"), false);
});

test("a user message stays plain text and is never markdown-parsed", () => {
  const raw = "## Bukan heading\n**Bukan bold** <b>html</b>";
  const state = answered(raw, "Jawaban.");
  const user = state.messages[0];

  assert.equal(user.role, BUILD_CHAT_MESSAGE_ROLE.user);
  assert.equal(user.content, raw);
  assert.equal(typeof user.content, "string");
  assert.deepEqual(
    state.messages.map((message) => typeof message.content),
    ["string", "string"]
  );
});

test("every conversation message carries only id, role, and content", () => {
  const state = answered("q", "a");

  for (const message of state.messages) {
    assert.deepEqual(Object.keys(message).sort(), ["content", "id", "role"]);
    assert.equal(typeof message.id, "string");
    assert.equal(
      BUILD_CHAT_MESSAGE_ROLE.user === message.role ||
        BUILD_CHAT_MESSAGE_ROLE.assistant === message.role,
      true
    );
  }
});

/* ---------- client and error taxonomy (Sprint 11 coverage) ---------- */

test("the build chat client posts the payload to /build/chat", async () => {
  assert.equal(BUILD_CHAT_ENDPOINT_PATH, "/build/chat");

  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    "Apa yang diketahui dari build ini?",
    { CPU: cpuBenchmarks, GPU: [] }
  );
  const answer = await requestBuildChatAnswer(
    payload,
    async () => ({
      ok: true,
      json: async () => ({ answer: "Hanya data yang tersimpan." }),
    })
  );

  assert.equal(answer, "Hanya data yang tersimpan.");
});

test("422, 502, 503, and network failures keep their classifications", async () => {
  for (const [status, kind] of [
    [422, CHAT_ERROR_KIND.validation],
    [502, CHAT_ERROR_KIND.provider],
    [503, CHAT_ERROR_KIND.provider],
    [500, CHAT_ERROR_KIND.request],
  ]) {
    await assert.rejects(
      answering(async () => ({ ok: false, status, json: async () => ({}) })),
      (error) =>
        error instanceof BuildChatError &&
        error.kind === kind &&
        error.status === status
    );
  }

  await assert.rejects(
    answering(async () => {
      throw new TypeError("Failed to fetch");
    }),
    (error) =>
      error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.request
  );
});

test("malformed and empty answers are rejected", async () => {
  for (const answer of [undefined, null, "", "   ", 42, ["a"], { text: "hi" }]) {
    await assert.rejects(
      answering(async () => ({ ok: true, json: async () => ({ answer }) })),
      (error) =>
        error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.empty
    );
  }
});

test("unknown chat failures are reported as request errors", () => {
  const state = failBuildChatRequest(
    asking("q", BUILD_A_TOKEN),
    new Error("boom"),
    BUILD_A_TOKEN
  );

  assert.equal(state.error.kind, CHAT_ERROR_KIND.request);
  assert.equal(state.error.message, "boom");
});

/* ---------- 30. responsive surface ---------- */

test("the build chat surface exposes compact, wrap-safe presentation data", () => {
  const summary = getBuildChatContextSummary(cpuDetail, gpuDetail, userContext);

  assert.equal(summary.contextLabel, "Gaming · 1440p");
  assert.equal(
    BUILD_CHAT_SUGGESTED_QUESTIONS.every(
      (question) => question.length <= 80 && !question.includes("\n")
    ),
    true
  );

  const longAnswer = `${"x".repeat(5000)}`;
  const state = answered("q", longAnswer);

  assert.equal(state.messages[1].content.length, 5000);
  assert.equal(
    state.messages.every((message) => !String(message.content).includes("\t")),
    true
  );
});

/* ---------- responsive presentation contract ---------- */

test("the chat stylesheet keeps long content wrapped and composer inputs bounded", () => {
  const css = readFileSync(new URL("./App.css", import.meta.url), "utf8");

  assert.match(css, /\.build-chat-message-text\s*\{[^}]*overflow-wrap:\s*anywhere/);
  assert.match(css, /\.build-chat-message-text\s*\{[^}]*word-break:\s*break-word/);
  assert.match(
    css,
    /\.hardware-chat-composer input\s*\{[^}]*min-width:\s*0/
  );
  assert.match(
    css,
    /\.hardware-chat-composer input\s*\{[^}]*width:\s*100%/
  );
  assert.match(
    css,
    /@media \(max-width: 700px\)[\s\S]*\.hardware-chat-prompts\s*\{[^}]*flex-direction:\s*column/
  );
  assert.match(
    css,
    /@media \(max-width: 700px\)[\s\S]*\.hardware-chat-prompt\s*\{[^}]*overflow-wrap:\s*anywhere/
  );
  assert.match(
    css,
    /@media \(max-width: 700px\)[\s\S]*\.hardware-chat-composer\s*\{[^}]*flex-direction:\s*column/
  );
});

test("the build chat section never renders raw HTML", () => {
  const source = readFileSync(new URL("./App.jsx", import.meta.url), "utf8");

  assert.equal(source.includes("dangerouslySetInnerHTML"), false);
  assert.equal(source.includes("build-chat-message-user"), true);
  assert.equal(source.includes("MarkdownContent markdown={message.content}"), true);
});

/* ---------- composed ask flow (App wiring contract) ---------- */

const createAskHarness = ({ fetchImplementation, cpu = cpuDetail, gpu = gpuDetail, context = userContext }) => {
  const guard = createChatRequestGuard();
  const harness = {
    cpu,
    gpu,
    context,
    token: tokenFor(cpu, gpu, context),
    state: createBuildChatState(tokenFor(cpu, gpu, context)),
    apply(nextState) {
      harness.state = nextState;
      return nextState;
    },
  };

  harness.ask = (question) => {
    if (isBuildChatBusy(harness.state)) {
      return null;
    }

    let payload;

    try {
      payload = buildChatPayload(harness.cpu, harness.gpu, harness.context, question, {
        CPU: cpuBenchmarks,
        GPU: [],
      });
    } catch (error) {
      return harness.apply(failBuildChatRequest(harness.state, error, harness.state.buildToken));
    }

    const requestId = guard.begin();
    const requestToken = harness.token;
    harness.apply(startBuildChatRequest(harness.state, payload.question, requestToken));

    requestBuildChatAnswer(payload, fetchImplementation).then(
      (answer) => {
        if (!guard.isCurrent(requestId)) {
          return;
        }
        if (!isSameBuildChatToken(harness.token, requestToken)) {
          return;
        }
        harness.apply(completeBuildChatRequest(harness.state, answer, requestToken));
      },
      (error) => {
        if (!guard.isCurrent(requestId)) {
          return;
        }
        if (!isSameBuildChatToken(harness.token, requestToken)) {
          return;
        }
        harness.apply(failBuildChatRequest(harness.state, error, requestToken));
      }
    );

    return payload;
  };

  harness.changeBuild = (changes = {}) => {
    harness.cpu = changes.cpu ?? harness.cpu;
    harness.gpu = changes.gpu ?? harness.gpu;
    harness.context = changes.context ?? harness.context;
    harness.token = tokenFor(harness.cpu, harness.gpu, harness.context);
    guard.invalidate();
    return harness.apply(createBuildChatState(harness.token));
  };

  harness.settle = () => scheduleImmediate();

  return harness;
};

test("composed flow records a full turn and a follow-up for one build", async () => {
  const harness = createAskHarness({
    fetchImplementation: async (url, options) => {
      const question = JSON.parse(options.body).question;

      return {
        ok: true,
        json: async () => ({
          answer: `Jawaban untuk: ${question}`,
        }),
      };
    },
  });

  harness.ask("Bagaimana karakter build ini untuk gaming 1440p?");
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.success);
  assert.equal(harness.state.messages.length, 2);

  harness.ask("Kalau untuk productivity?");
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.success);
  assert.equal(harness.state.messages.length, 4);
  assert.deepEqual(
    harness.state.messages.map((message) => message.role),
    [
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
    ]
  );
  assert.equal(
    harness.state.messages[3].content,
    "Jawaban untuk: Kalau untuk productivity?"
  );
  assert.equal(harness.state.buildToken, BUILD_A_TOKEN);
});

test("composed flow ignores a stale success when the GPU changes mid-flight", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createAskHarness({
    fetchImplementation: async () => {
      await pending;

      return {
        ok: true,
        json: async () => ({ answer: "Jawaban untuk build lama." }),
      };
    },
  });

  harness.ask("Bagaimana karakter build ini?");

  assert.equal(harness.state.status, CHAT_STATUS.loading);
  assert.equal(harness.state.buildToken, BUILD_A_TOKEN);

  harness.changeBuild({ gpu: otherGpuDetail });

  assert.equal(harness.token, BUILD_B_TOKEN);
  assert.equal(harness.state.buildToken, BUILD_B_TOKEN);

  release();
  await harness.settle();

  assert.equal(harness.state.messages.length, 0);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.equal(harness.state.error, null);
  assert.equal(harness.state.buildToken, BUILD_B_TOKEN);
});

test("composed flow ignores a stale failure when the CPU changes mid-flight", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createAskHarness({
    fetchImplementation: async () => {
      await pending;

      return { ok: false, status: 503, json: async () => ({}) };
    },
  });

  harness.ask("Apa yang diketahui dari build ini?");
  harness.changeBuild({ cpu: { ...cpuDetail, id: 42 } });

  assert.equal(harness.token, "42:3361:gaming:1440p");

  release();
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.equal(harness.state.error, null);
  assert.equal(harness.state.messages.length, 0);
  assert.equal(harness.state.buildToken, "42:3361:gaming:1440p");
});

test("composed flow ignores a stale failure when the use case changes mid-flight", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createAskHarness({
    fetchImplementation: async () => {
      await pending;

      return { ok: false, status: 502, json: async () => ({}) };
    },
  });

  harness.ask("Bagaimana karakter build ini?");
  harness.changeBuild({ context: { useCase: "Productivity", resolution: "1440p" } });

  assert.equal(harness.token, "1:3361:productivity:1440p");

  release();
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.equal(harness.state.error, null);
  assert.equal(harness.state.messages.length, 0);
});

test("composed flow keeps a failed answer on the current build and retries it", async () => {
  const responses = [
    { ok: false, status: 503, json: async () => ({}) },
    { ok: true, json: async () => ({ answer: "Jawaban setelah retry." }) },
  ];
  let call = 0;

  const harness = createAskHarness({
    fetchImplementation: async () => responses[call++],
  });

  harness.ask("Apa yang diketahui dari build ini?");
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.error);
  assert.equal(harness.state.error.kind, CHAT_ERROR_KIND.provider);
  assert.equal(harness.state.messages.length, 0);
  assert.equal(harness.state.pendingQuestion, "Apa yang diketahui dari build ini?");

  harness.ask(harness.state.pendingQuestion);
  assert.equal(harness.state.status, CHAT_STATUS.loading);
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.success);
  assert.equal(harness.state.messages.length, 2);
  assert.equal(harness.state.messages[1].content, "Jawaban setelah retry.");
  assert.equal(call, 2);
});

test("composed flow blocks a duplicate submission while loading", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createAskHarness({
    fetchImplementation: async () => {
      await pending;

      return { ok: true, json: async () => ({ answer: "Jawaban." }) };
    },
  });

  harness.ask("Pertama");
  assert.equal(harness.ask("Duplikat"), null);
  assert.equal(harness.state.pendingQuestion, "Pertama");

  release();
  await harness.settle();

  assert.equal(harness.state.messages.length, 2);
  assert.equal(harness.state.messages[0].content, "Pertama");
});

test("composed flow does not touch catalog or comparison state", async () => {
  const compareList = [{ id: 11, type: "CPU" }];
  const catalogFilter = { type: "All", manufacturer: "All" };
  const before = JSON.stringify({ compareList, catalogFilter });

  const harness = createAskHarness({
    fetchImplementation: async () => ({
      ok: true,
      json: async () => ({ answer: "Jawaban." }),
    }),
  });

  harness.ask("q");
  await harness.settle();
  harness.changeBuild({ gpu: otherGpuDetail });
  harness.ask("q2");
  await harness.settle();

  assert.equal(JSON.stringify({ compareList, catalogFilter }), before);
  assert.equal(compareList.length, 1);
  assert.equal(compareList[0].id, 11);
});

test("composed flow keeps user context setters mapped to the build identity", () => {
  const context = createBuildUserContext();
  const gaming = setBuildUseCase(context, "Gaming");
  const at1440p = setBuildResolution(gaming, "1440p");

  assert.equal(tokenFor(cpuDetail, gpuDetail, at1440p), BUILD_A_TOKEN);
  assert.equal(
    tokenFor(cpuDetail, gpuDetail, setBuildUseCase(context, "Productivity")),
    "1:3361:productivity:unspecified"
  );
  assert.equal(tokenFor(cpuDetail, gpuDetail, context), "1:3361:unspecified:unspecified");
});
