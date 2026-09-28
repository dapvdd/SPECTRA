import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setImmediate as scheduleImmediate } from "node:timers/promises";

import {
  BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH,
  BUILD_CHAT_HISTORY_MAX_MESSAGES,
  BUILD_CHAT_MESSAGE_ROLE,
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  buildBuildChatHistory,
  buildChatPayload,
  completeBuildChatRequest,
  createBuildChatState,
  createChatRequestGuard,
  failBuildChatRequest,
  getBuildChatHistory,
  getBuildChatToken,
  isBuildChatBusy,
  isSameBuildChatToken,
  requestBuildChatAnswer,
  resetBuildChatConversation,
  retryBuildChatRequest,
  startBuildChatRequest,
} from "./buildChat.js";
import {
  createBuildConfig,
  createBuildUserContext,
  getBuildChatSnapshot,
  getBuildSelection,
  setBuildCpu,
  setBuildGpu,
  setBuildResolution,
  setBuildUseCase,
} from "./buildConfig.js";
import {
  CHAT_STATUS as HARDWARE_CHAT_STATUS,
  createHardwareChatState,
} from "./hardwareChat.js";
import {
  addComparisonSelection,
  clearComparisonSelection,
} from "./appState.js";
import { parseMarkdown } from "./markdown.js";

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

const otherGpuDetail = { ...gpuDetail, id: 3362, name: "GeForce RTX 5080" };

const userContext = { useCase: "Gaming", resolution: "1440p" };

const cpuBenchmarks = [
  {
    id: 7,
    hardware_id: 1,
    benchmark_name: "Geekbench 7",
    test_type: "single-core",
    score: 2100,
    unit: "points",
  },
];

const benchmarks = { CPU: cpuBenchmarks, GPU: [] };

const tokenFor = (cpu = cpuDetail, gpu = gpuDetail, context = userContext) =>
  getBuildChatToken(getBuildChatSnapshot(cpu, gpu, context));

const BUILD_A_TOKEN = "1:3361:gaming:1440p";
const BUILD_B_TOKEN = "1:3362:gaming:1440p";

const idle = (buildToken = BUILD_A_TOKEN) => createBuildChatState(buildToken);

const asking = (question, buildToken = BUILD_A_TOKEN) =>
  startBuildChatRequest(idle(buildToken), question, buildToken);

const withTurns = (turns, buildToken = BUILD_A_TOKEN) => {
  let state = idle(buildToken);
  for (let index = 0; index < turns; index += 1) {
    state = completeBuildChatRequest(
      startBuildChatRequest(state, `Pertanyaan ${index}?`, buildToken),
      `Jawaban ${index}.`,
      buildToken
    );
  }
  return state;
};

const createConversationHarness = ({
  fetchImplementation,
  cpu = cpuDetail,
  gpu = gpuDetail,
  context = userContext,
}) => {
  const guard = createChatRequestGuard();
  const harness = {
    cpu,
    gpu,
    context,
    token: tokenFor(cpu, gpu, context),
    state: createBuildChatState(tokenFor(cpu, gpu, context)),
    requests: [],
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
      payload = buildChatPayload(
        harness.cpu,
        harness.gpu,
        harness.context,
        question,
        benchmarks,
        harness.state.messages
      );
    } catch (error) {
      return harness.apply(
        failBuildChatRequest(harness.state, error, harness.state.buildToken)
      );
    }

    harness.requests.push(payload);
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

  harness.retry = () => harness.ask(harness.state.pendingQuestion);

  harness.reset = () => {
    guard.invalidate();
    return harness.apply(resetBuildChatConversation(harness.state));
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

const alwaysAnswer = (answer = "Jawaban.") => async () => ({
  ok: true,
  json: async () => ({ answer }),
});

/* ---------- history bounds ---------- */

test("the history bounds match the accepted backend contract", () => {
  assert.equal(BUILD_CHAT_HISTORY_MAX_MESSAGES, 10);
  assert.equal(BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH, 4000);
});

test("a conversation history is built from role and content only", () => {
  const state = withTurns(1);

  assert.deepEqual(getBuildChatHistory(state), [
    { role: BUILD_CHAT_MESSAGE_ROLE.user, content: "Pertanyaan 0?" },
    { role: BUILD_CHAT_MESSAGE_ROLE.assistant, content: "Jawaban 0." },
  ]);
});

test("an empty conversation produces no history", () => {
  assert.deepEqual(buildBuildChatHistory([]), []);
  assert.deepEqual(buildBuildChatHistory(undefined), []);
  assert.deepEqual(buildBuildChatHistory(null), []);
  assert.deepEqual(buildBuildChatHistory("not a list"), []);
  assert.deepEqual(getBuildChatHistory(idle()), []);
  assert.deepEqual(getBuildChatHistory(undefined), []);
});

test("history is bounded to the ten newest messages", () => {
  const state = withTurns(20);
  const history = getBuildChatHistory(state);

  assert.equal(state.messages.length, 40);
  assert.equal(history.length, BUILD_CHAT_HISTORY_MAX_MESSAGES);
  assert.equal(history[0].role, BUILD_CHAT_MESSAGE_ROLE.user);
  assert.equal(
    history.at(-1).content,
    state.messages.at(-1).content,
    "the newest turn must survive the bound"
  );
});

test("history is bounded to ten messages in the request payload", () => {
  const state = withTurns(12);

  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    "Pertanyaan berikutnya?",
    benchmarks,
    state.messages
  );

  assert.equal(payload.messages.length, BUILD_CHAT_HISTORY_MAX_MESSAGES);
  assert.equal(payload.question, "Pertanyaan berikutnya?");
});

test("history message content is bounded to four thousand characters", () => {
  const longAnswer = "y".repeat(BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH + 500);
  const state = completeBuildChatRequest(
    startBuildChatRequest(idle(), "q", BUILD_A_TOKEN),
    longAnswer,
    BUILD_A_TOKEN
  );

  const history = getBuildChatHistory(state);

  assert.equal(history[1].content.length, BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH);
});

test("structurally invalid history is dropped rather than sent", () => {
  const alternating = [
    { role: BUILD_CHAT_MESSAGE_ROLE.user, content: "q" },
    { role: BUILD_CHAT_MESSAGE_ROLE.assistant, content: "a" },
  ];

  assert.deepEqual(buildBuildChatHistory([alternating[1]]), []);
  assert.deepEqual(
    buildBuildChatHistory([
      alternating[0],
      { role: BUILD_CHAT_MESSAGE_ROLE.user, content: "q2" },
    ]),
    []
  );
  assert.deepEqual(buildBuildChatHistory([{ role: "system", content: "x" }]), []);
  assert.deepEqual(
    buildBuildChatHistory([{ role: BUILD_CHAT_MESSAGE_ROLE.user, content: "  " }]),
    []
  );
  assert.deepEqual(buildBuildChatHistory([null, alternating[0]]), []);
});

/* ---------- payload separation ---------- */

test("a first turn sends no history key at all", () => {
  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    "Bagaimana karakter build ini?",
    benchmarks,
    []
  );

  assert.deepEqual(Object.keys(payload).sort(), ["build", "question"]);
});

test("a follow-up payload carries history, build context, and question separately", () => {
  const state = withTurns(1);

  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    "Kalau untuk productivity?",
    benchmarks,
    state.messages
  );

  assert.deepEqual(Object.keys(payload).sort(), ["build", "messages", "question"]);
  assert.equal(payload.question, "Kalau untuk productivity?");
  assert.equal(payload.messages.length, 2);
  assert.equal(payload.build.cpu.id, 1);
  assert.equal(payload.build.gpu.id, 3361);
  assert.equal(payload.build.messages, undefined);
  assert.equal(payload.build.question, undefined);
  assert.deepEqual(payload.build.context, { use_case: "gaming", resolution: "1440p" });
});

test("history messages carry only role and content", () => {
  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    "q",
    benchmarks,
    withTurns(1).messages
  );

  for (const message of payload.messages) {
    assert.deepEqual(Object.keys(message).sort(), ["content", "role"]);
  }
});

/* ---------- no duplicated current question ---------- */

test("the current question is never duplicated into the history", () => {
  const question = "Bagaimana karakter build ini?";
  const state = withTurns(2);
  const loading = startBuildChatRequest(state, question, BUILD_A_TOKEN);

  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    question,
    benchmarks,
    loading.messages
  );

  assert.equal(
    payload.messages.filter((message) => message.content === question).length,
    0
  );
  assert.equal(payload.messages.length, 4);
  assert.equal(payload.question, question);
});

test("a successful turn records the question once in the conversation", async () => {
  const harness = createConversationHarness({ fetchImplementation: alwaysAnswer() });

  harness.ask("Pertanyaan pertama?");
  await harness.settle();
  harness.ask("Pertanyaan kedua?");
  await harness.settle();

  assert.equal(harness.state.messages.length, 4);
  assert.deepEqual(
    harness.state.messages.map((message) => message.content),
    ["Pertanyaan pertama?", "Jawaban.", "Pertanyaan kedua?", "Jawaban."]
  );

  const [, second] = harness.requests;

  assert.equal(
    second.messages.filter(
      (message) => message.content === "Pertanyaan kedua?"
    ).length,
    0,
    "the current question must not be copied into its own history"
  );
  assert.equal(
    second.messages.filter(
      (message) => message.content === "Pertanyaan pertama?"
    ).length,
    1
  );
});

/* ---------- reset ---------- */

test("a new conversation returns the same build to an idle state", () => {
  const loading = startBuildChatRequest(
    withTurns(2),
    "Pertanyaan gagal?",
    BUILD_A_TOKEN
  );
  const errored = failBuildChatRequest(
    loading,
    new Error("provider failed"),
    BUILD_A_TOKEN
  );

  const reset = resetBuildChatConversation(errored);

  assert.equal(reset.buildToken, BUILD_A_TOKEN);
  assert.equal(reset.status, CHAT_STATUS.idle);
  assert.deepEqual(reset.messages, []);
  assert.equal(reset.pendingQuestion, "");
  assert.equal(reset.error, null);
  assert.equal(isBuildChatBusy(reset), false);
});

test("a new conversation resets an unanswered loading state", () => {
  const reset = resetBuildChatConversation(asking("Belum terjawab?", BUILD_A_TOKEN));

  assert.equal(reset.status, CHAT_STATUS.idle);
  assert.equal(reset.pendingQuestion, "");
  assert.equal(reset.error, null);
});

test("a reset conversation never changes the selected build", () => {
  let config = createBuildConfig();
  config = setBuildCpu(config, { id: cpuDetail.id, name: cpuDetail.name, type: "CPU" });
  config = setBuildGpu(config, { id: gpuDetail.id, name: gpuDetail.name, type: "GPU" });
  const context = setBuildResolution(setBuildUseCase(createBuildUserContext(), "Gaming"), "1440p");

  const before = JSON.stringify({ config, context });
  const token = tokenFor(cpuDetail, gpuDetail, context);

  resetBuildChatConversation(withTurns(3, token));

  assert.equal(JSON.stringify({ config, context }), before);
  assert.equal(getBuildSelection(config, "CPU").id, cpuDetail.id);
  assert.equal(getBuildSelection(config, "GPU").id, gpuDetail.id);
  assert.equal(tokenFor(cpuDetail, gpuDetail, context), token);
});

test("a reset conversation leaves comparison and hardware chat state alone", () => {
  let compareList = addComparisonSelection([], { id: 5, type: "CPU" });
  const before = JSON.stringify(compareList);
  const hardwareChat = createHardwareChatState();

  resetBuildChatConversation(withTurns(2));

  assert.equal(JSON.stringify(compareList), before);
  assert.equal(hardwareChat.status, HARDWARE_CHAT_STATUS.idle);
  compareList = clearComparisonSelection(compareList, 5);
  assert.equal(compareList.length, 0);
});

test("a new conversation action discards an in-flight answer", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createConversationHarness({
    fetchImplementation: async () => {
      await pending;
      return { ok: true, json: async () => ({ answer: "Jawaban basi." }) };
    },
  });

  harness.ask("Bagaimana karakter build ini?");
  assert.equal(harness.state.status, CHAT_STATUS.loading);

  harness.reset();
  release();
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.equal(harness.state.messages.length, 0);
  assert.equal(harness.state.error, null);
  assert.equal(harness.state.buildToken, BUILD_A_TOKEN);
});

/* ---------- retry ---------- */

test("a failed question is retried once without duplicating the user message", async () => {
  const responses = [
    { ok: false, status: 503, json: async () => ({}) },
    { ok: true, json: async () => ({ answer: "Jawaban setelah retry." }) },
  ];
  let call = 0;
  const harness = createConversationHarness({
    fetchImplementation: async () => responses[call++],
  });

  harness.ask("Apakah data ini cukup?");
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.error);
  assert.equal(harness.state.error.kind, CHAT_ERROR_KIND.provider);
  assert.equal(harness.state.messages.length, 0);
  assert.equal(harness.state.pendingQuestion, "Apakah data ini cukup?");

  harness.retry();
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.success);
  assert.equal(harness.state.messages.length, 2);
  assert.equal(harness.state.messages[0].content, "Apakah data ini cukup?");
  assert.equal(harness.state.messages[1].content, "Jawaban setelah retry.");
  assert.equal(harness.state.pendingQuestion, "");
  assert.equal(call, 2);
});

test("a failed follow-up retry keeps the earlier turns and adds one turn", async () => {
  const responses = [
    { ok: true, json: async () => ({ answer: "Jawaban pertama." }) },
    { ok: false, status: 502, json: async () => ({}) },
    { ok: true, json: async () => ({ answer: "Jawaban ketiga." }) },
  ];
  let call = 0;
  const harness = createConversationHarness({
    fetchImplementation: async () => responses[call++],
  });

  harness.ask("Pertanyaan pertama?");
  await harness.settle();
  harness.ask("Pertanyaan kedua?");
  await harness.settle();

  assert.equal(harness.state.messages.length, 2);

  harness.retry();
  await harness.settle();

  assert.equal(harness.state.messages.length, 4);
  assert.equal(
    harness.state.messages.filter(
      (message) => message.content === "Pertanyaan kedua?"
    ).length,
    1,
    "the retried question must not be recorded twice"
  );
  assert.deepEqual(
    harness.state.messages.map((message) => message.role),
    [
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
    ]
  );
});

test("a retry is a no-op without a pending question or while loading", () => {
  const noPending = idle();

  assert.equal(retryBuildChatRequest(noPending), noPending);

  const loading = asking("Sudah dikirim?", BUILD_A_TOKEN);

  assert.equal(retryBuildChatRequest(loading), loading);
  assert.equal(isBuildChatBusy(loading), true);
});

/* ---------- build identity invalidation ---------- */

test("a CPU change clears the conversation and returns it to idle", async () => {
  const harness = createConversationHarness({ fetchImplementation: alwaysAnswer() });

  harness.ask("Bagaimana karakter build ini?");
  await harness.settle();
  assert.equal(harness.state.messages.length, 2);

  harness.changeBuild({ cpu: { ...cpuDetail, id: 42 } });

  assert.equal(harness.token, "42:3361:gaming:1440p");
  assert.equal(harness.state.buildToken, "42:3361:gaming:1440p");
  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.equal(harness.state.pendingQuestion, "");
  assert.equal(harness.state.error, null);
  assert.deepEqual(getBuildChatHistory(harness.state), []);
});

test("a GPU change clears the conversation and returns it to idle", async () => {
  const harness = createConversationHarness({ fetchImplementation: alwaysAnswer() });

  harness.ask("Bagaimana karakter build ini?");
  await harness.settle();
  harness.changeBuild({ gpu: otherGpuDetail });

  assert.equal(harness.state.buildToken, BUILD_B_TOKEN);
  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
});

test("a use case change clears the conversation and returns it to idle", async () => {
  const harness = createConversationHarness({ fetchImplementation: alwaysAnswer() });

  harness.ask("Bagaimana karakter build ini?");
  await harness.settle();
  harness.changeBuild({ context: { useCase: "Productivity", resolution: "1440p" } });

  assert.equal(harness.state.buildToken, "1:3361:productivity:1440p");
  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
});

test("a resolution change clears the conversation and returns it to idle", async () => {
  const harness = createConversationHarness({ fetchImplementation: alwaysAnswer() });

  harness.ask("Bagaimana karakter build ini?");
  await harness.settle();
  harness.changeBuild({ context: { useCase: "Gaming", resolution: "4K" } });

  assert.equal(harness.state.buildToken, "1:3361:gaming:4k");
  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
});

test("a stale success is ignored and never becomes history", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createConversationHarness({
    fetchImplementation: async () => {
      await pending;
      return { ok: true, json: async () => ({ answer: "Jawaban build lama." }) };
    },
  });

  harness.ask("Bagaimana karakter build ini?");
  harness.changeBuild({ gpu: otherGpuDetail });
  release();
  await harness.settle();

  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.deepEqual(getBuildChatHistory(harness.state), []);
});

test("a stale failure is ignored and leaves no error on the new build", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createConversationHarness({
    fetchImplementation: async () => {
      await pending;
      return { ok: false, status: 503, json: async () => ({}) };
    },
  });

  harness.ask("Bagaimana karakter build ini?");
  harness.changeBuild({ gpu: otherGpuDetail });
  release();
  await harness.settle();

  assert.equal(harness.state.error, null);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.equal(harness.state.pendingQuestion, "");
});

/* ---------- composed conversation flow ---------- */

test("a composed conversation sends the previous turns with every follow-up", async () => {
  const harness = createConversationHarness({
    fetchImplementation: async () => ({
      ok: true,
      json: async () => ({ answer: "Jawaban." }),
    }),
  });

  harness.ask("Bagaimana karakter build ini untuk gaming 1440p?");
  await harness.settle();
  harness.ask("Kalau untuk productivity?");
  await harness.settle();
  harness.ask("Apa yang tidak bisa disimpulkan?");
  await harness.settle();

  assert.equal(harness.requests.length, 3);
  assert.equal(harness.requests[0].messages, undefined);
  assert.deepEqual(harness.requests[1].messages, [
    { role: BUILD_CHAT_MESSAGE_ROLE.user, content: "Bagaimana karakter build ini untuk gaming 1440p?" },
    { role: BUILD_CHAT_MESSAGE_ROLE.assistant, content: "Jawaban." },
  ]);
  assert.deepEqual(
    harness.requests[2].messages.map((message) => message.role),
    [
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
      BUILD_CHAT_MESSAGE_ROLE.user,
      BUILD_CHAT_MESSAGE_ROLE.assistant,
    ]
  );
  assert.equal(harness.requests[2].messages.length, 4);
  assert.equal(harness.state.messages.length, 6);
});

test("a composed conversation keeps the request bounded across many turns", async () => {
  const harness = createConversationHarness({ fetchImplementation: alwaysAnswer() });

  for (let index = 0; index < 9; index += 1) {
    harness.ask(`Pertanyaan ${index}?`);
    await harness.settle();
  }

  assert.equal(harness.state.messages.length, 18);
  assert.equal(harness.requests.length, 9);

  for (const payload of harness.requests) {
    if (payload.messages) {
      assert.equal(payload.messages.length <= BUILD_CHAT_HISTORY_MAX_MESSAGES, true);
      for (const message of payload.messages) {
        assert.equal(
          message.content.length <= BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH,
          true
        );
      }
    }
  }

  assert.equal(
    harness.requests.at(-1).messages.length,
    BUILD_CHAT_HISTORY_MAX_MESSAGES
  );
});

test("a composed conversation keeps user text plain and assistant text markdown", async () => {
  const harness = createConversationHarness({
    fetchImplementation: alwaysAnswer("## Ringkasan\n\n**Fakta** tersimpan."),
  });

  harness.ask("Jelaskan **build** ini.");
  await harness.settle();

  const [user, assistant] = harness.state.messages;

  assert.equal(user.content, "Jelaskan **build** ini.");
  assert.equal(user.role, BUILD_CHAT_MESSAGE_ROLE.user);
  assert.equal(assistant.role, BUILD_CHAT_MESSAGE_ROLE.assistant);
  assert.equal(parseMarkdown(user.content).length, 1);
  assert.equal(parseMarkdown(user.content)[0].type, "paragraph");
  assert.equal(parseMarkdown(assistant.content)[0].type, "heading");
});

test("a composed conversation leaves the build and comparison state unchanged", async () => {
  const compareList = addComparisonSelection([], { id: 9, type: "GPU" });
  const before = JSON.stringify(compareList);

  const harness = createConversationHarness({ fetchImplementation: alwaysAnswer() });

  harness.ask("q");
  await harness.settle();
  harness.reset();
  harness.ask("q2");
  await harness.settle();

  assert.equal(JSON.stringify(compareList), before);
  assert.equal(harness.state.buildToken, BUILD_A_TOKEN);
});

/* ---------- rendering contract ---------- */

test("the build chat UI exposes a new conversation control", () => {
  const source = readFileSync(new URL("./App.jsx", import.meta.url), "utf8");

  assert.equal(source.includes("dangerouslySetInnerHTML"), false);
  assert.equal(source.includes("New conversation"), true);
  assert.equal(source.includes("onReset={onNewBuildChat}"), true);
  assert.equal(source.includes("buildChatState.messages,"), true);
  assert.equal(source.includes("MarkdownContent markdown={message.content}"), true);
});
