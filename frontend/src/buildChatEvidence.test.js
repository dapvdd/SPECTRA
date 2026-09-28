import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setImmediate as scheduleImmediate } from "node:timers/promises";

import {
  BUILD_CHAT_EVIDENCE_MAX_ITEM_LENGTH,
  BUILD_CHAT_EVIDENCE_MAX_ITEMS,
  BUILD_CHAT_EVIDENCE_LABELS,
  BUILD_CHAT_EVIDENCE_SECTION,
  BUILD_CHAT_MESSAGE_ROLE,
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  BuildChatError,
  buildChatPayload,
  completeBuildChatRequest,
  createBuildChatState,
  createChatRequestGuard,
  createEmptyBuildChatEvidence,
  failBuildChatRequest,
  getBuildChatHistory,
  getBuildChatEvidenceSections,
  getBuildChatToken,
  isBuildChatBusy,
  isSameBuildChatToken,
  normalizeBuildChatEvidence,
  requestBuildChatAnswer,
  resetBuildChatConversation,
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
  requestHardwareChatAnswer,
  buildHardwareChatContext,
} from "./hardwareChat.js";
import { addComparisonSelection } from "./appState.js";
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

const okBody = (answer, evidence) => ({
  ok: true,
  json: async () => ({ answer, evidence }),
});

const structuredAnswer = (
  answer = "Berdasarkan data tersimpan.",
  evidence = {
    known_facts: ["CPU 8 cores / 16 threads.", "GPU 16 GB VRAM GDDR7."],
    interpretation: ["Build menggabungkan CPU multi-core dengan GPU diskrit."],
    unknown: ["FPS pada 1440p.", "kebutuhan PSU.", "suhu sistem."],
  }
) => okBody(answer, evidence);

const answering = (fetchImplementation) =>
  requestBuildChatAnswer(
    buildChatPayload(cpuDetail, gpuDetail, userContext, "q", benchmarks),
    fetchImplementation
  );

const asking = (question, buildToken = BUILD_A_TOKEN) =>
  startBuildChatRequest(createBuildChatState(buildToken), question, buildToken);

const answered = (question, answer, evidence, buildToken = BUILD_A_TOKEN) =>
  completeBuildChatRequest(
    asking(question, buildToken),
    answer,
    buildToken,
    evidence
  );

/* ---------- structured assistant message ---------- */

test("an assistant message keeps the free-form answer and the evidence object", () => {
  const state = answered(
    "Apa yang diketahui?",
    "Ringkasan berbasis data.",
    {
      known_facts: ["CPU 8 cores / 16 threads."],
      interpretation: [],
      unknown: ["FPS."],
    }
  );

  const assistant = state.messages[1];

  assert.equal(assistant.role, BUILD_CHAT_MESSAGE_ROLE.assistant);
  assert.equal(assistant.content, "Ringkasan berbasis data.");
  assert.deepEqual(assistant.evidence, {
    knownFacts: ["CPU 8 cores / 16 threads."],
    interpretation: [],
    unknown: ["FPS."],
  });
});

test("a user message never carries evidence", () => {
  const state = answered("Apa yang diketahui?", "Jawaban.", {
    known_facts: ["fakta."],
    interpretation: [],
    unknown: [],
  });

  const user = state.messages[0];

  assert.equal(user.role, BUILD_CHAT_MESSAGE_ROLE.user);
  assert.deepEqual(Object.keys(user).sort(), ["content", "id", "role"]);
});

test("missing evidence on a completed message defaults to empty sections", () => {
  const state = answered("q", "Jawaban.");

  assert.deepEqual(state.messages[1].evidence, {
    knownFacts: [],
    interpretation: [],
    unknown: [],
  });
});

test("the evidence payload is normalized to camelCase keys from snake_case", () => {
  const result = normalizeBuildChatEvidence({
    known_facts: ["a"],
    interpretation: ["b"],
    unknown: [],
  });

  assert.deepEqual(result, {
    knownFacts: ["a"],
    interpretation: ["b"],
    unknown: [],
  });
});

test("empty evidence sections are normalized and never null", () => {
  assert.deepEqual(normalizeBuildChatEvidence({}), {
    knownFacts: [],
    interpretation: [],
    unknown: [],
  });
  assert.deepEqual(createEmptyBuildChatEvidence(), {
    knownFacts: [],
    interpretation: [],
    unknown: [],
  });
});

/* ---------- malformed evidence / API responses ---------- */

test("evidence with extra keys is rejected as a malformed response", async () => {
  await assert.rejects(
    answering(async () =>
      okBody("ok", {
        known_facts: [],
        interpretation: [],
        unknown: [],
        recommendation: [],
      })
    ),
    (error) =>
      error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.provider
  );
});

test("evidence with nested objects is rejected as a malformed response", async () => {
  await assert.rejects(
    answering(async () =>
      okBody("ok", {
        known_facts: [{ value: "obj" }],
        interpretation: [],
        unknown: [],
      })
    ),
    (error) =>
      error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.provider
  );
});

test("evidence with non-array sections is rejected as a malformed response", async () => {
  await assert.rejects(
    answering(async () =>
      okBody("ok", { known_facts: "bukan array", interpretation: [], unknown: [] })
    ),
    (error) =>
      error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.provider
  );
});

test("evidence with more than ten items per section is rejected", async () => {
  await assert.rejects(
    answering(async () =>
      okBody("ok", {
        known_facts: Array.from(
          { length: BUILD_CHAT_EVIDENCE_MAX_ITEMS + 1 },
          (_, index) => `item ${index}`
        ),
        interpretation: [],
        unknown: [],
      })
    ),
    (error) =>
      error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.provider
  );
});

test("evidence with items longer than the character bound is rejected", async () => {
  await assert.rejects(
    answering(async () =>
      okBody("ok", {
        known_facts: [],
        interpretation: ["x".repeat(BUILD_CHAT_EVIDENCE_MAX_ITEM_LENGTH + 1)],
        unknown: [],
      })
    ),
    (error) =>
      error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.provider
  );
});

test("evidence declarations enforce the exact limits", () => {
  assert.equal(BUILD_CHAT_EVIDENCE_MAX_ITEMS, 10);
  assert.equal(BUILD_CHAT_EVIDENCE_MAX_ITEM_LENGTH, 1000);
});

test("evidence items exactly at the bounds are accepted", async () => {
  const outcome = await answering(async () =>
    okBody("ok", {
      known_facts: Array.from(
        { length: BUILD_CHAT_EVIDENCE_MAX_ITEMS },
        (_, index) => `item ${index}`
      ),
      interpretation: ["x".repeat(BUILD_CHAT_EVIDENCE_MAX_ITEM_LENGTH)],
      unknown: [],
    })
  );

  assert.equal(outcome.answer, "ok");
  assert.equal(outcome.evidence.knownFacts.length, BUILD_CHAT_EVIDENCE_MAX_ITEMS);
});

test("a blank answer is rejected with the empty kind even with valid evidence", async () => {
  await assert.rejects(
    answering(async () =>
      okBody("   ", {
        known_facts: [],
        interpretation: [],
        unknown: [],
      })
    ),
    (error) =>
      error instanceof BuildChatError && error.kind === CHAT_ERROR_KIND.empty
  );
});

test("an API failure still maps to its original error taxonomy", async () => {
  for (const [status, kind] of [
    [422, CHAT_ERROR_KIND.validation],
    [502, CHAT_ERROR_KIND.provider],
    [503, CHAT_ERROR_KIND.provider],
    [500, CHAT_ERROR_KIND.request],
  ]) {
    await assert.rejects(
      answering(async () => ({ ok: false, status, json: async () => ({}) })),
      (error) => error instanceof BuildChatError && error.kind === kind
    );
  }
});

/* ---------- rendering sections ---------- */

test("evidence sections render in stable order with labels", () => {
  const sections = getBuildChatEvidenceSections({
    knownFacts: ["fakta."],
    interpretation: ["interpretasi."],
    unknown: ["tidak diketahui."],
  });

  assert.deepEqual(
    sections.map((section) => section.label),
    [
      BUILD_CHAT_EVIDENCE_LABELS.knownFacts,
      BUILD_CHAT_EVIDENCE_LABELS.interpretation,
      BUILD_CHAT_EVIDENCE_LABELS.unknown,
    ]
  );
  assert.equal(sections[0].key, "knownFacts");
  assert.equal(sections[1].key, "interpretation");
  assert.equal(sections[2].key, "unknown");
  assert.equal(sections[0].items[0], "fakta.");
});

test("missing or empty evidence yields no sections to render", () => {
  assert.deepEqual(getBuildChatEvidenceSections(undefined).map((s) => s.items), [
    [],
    [],
    [],
  ]);
  assert.deepEqual(getBuildChatEvidenceSections(null).map((s) => s.items), [
    [],
    [],
    [],
  ]);
  assert.deepEqual(
    getBuildChatEvidenceSections(createEmptyBuildChatEvidence())
      .map((s) => s.items)
      .flat(),
    []
  );
});

test("section keys map to the backend snake_case vocabulary", () => {
  assert.equal(BUILD_CHAT_EVIDENCE_SECTION.knownFacts, "known_facts");
  assert.equal(BUILD_CHAT_EVIDENCE_SECTION.interpretation, "interpretation");
  assert.equal(BUILD_CHAT_EVIDENCE_SECTION.unknown, "unknown");
});

test("the evidence items are never parsed as markdown by the renderer", () => {
  const sections = getBuildChatEvidenceSections({
    knownFacts: ["**bukan heading** dan <b>bukan HTML</b>"],
    interpretation: [],
    unknown: [],
  });

  assert.equal(sections[0].items[0], "**bukan heading** dan <b>bukan HTML</b>");
  assert.equal(
    parseMarkdown(sections[0].items[0])[0].type,
    "paragraph",
    "evidence items remain plain data strings"
  );
});

test("the transcript never uses dangerouslySetInnerHTML and renders evidence", () => {
  const source = readFileSync(new URL("./App.jsx", import.meta.url), "utf8");

  assert.equal(source.includes("dangerouslySetInnerHTML"), false);
  assert.equal(source.includes("<BuildChatEvidence evidence={message.evidence} />"), true);
  assert.equal(source.includes("build-chat-evidence-section"), true);
  assert.equal(source.includes("MarkdownContent markdown={message.content}"), true);
});

test("the evidence stylesheet keeps sections usable and wrap-safe", () => {
  const css = readFileSync(new URL("./App.css", import.meta.url), "utf8");

  assert.match(css, /\.build-chat-evidence\s*\{/);
  assert.match(css, /\.build-chat-evidence-item\s*\{[^}]*overflow-wrap:\s*anywhere/);
  for (const selector of [
    ".build-chat-evidence-section",
    ".build-chat-evidence-list",
    ".build-chat-evidence-label",
  ]) {
    assert.match(css, new RegExp(selector.replace(/\./g, "\\.") + "\\s*\\{"));
  }
});

/* ---------- conversation compatibility ---------- */

const createEvidenceHarness = ({ fetchImplementation, fetchFor = undefined }) => {
  const guard = createChatRequestGuard();
  const harness = {
    cpu: cpuDetail,
    gpu: gpuDetail,
    context: userContext,
    token: BUILD_A_TOKEN,
    state: createBuildChatState(BUILD_A_TOKEN),
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

    const payload = buildChatPayload(
      harness.cpu,
      harness.gpu,
      harness.context,
      question,
      benchmarks,
      harness.state.messages
    );
    harness.requests.push(payload);

    const requestId = guard.begin();
    const requestToken = harness.token;
    harness.apply(startBuildChatRequest(harness.state, payload.question, requestToken));

    const fetchImplementationToUse =
      typeof fetchFor === "function" ? fetchFor(payload) : fetchImplementation;

    requestBuildChatAnswer(payload, fetchImplementationToUse).then(
      (result) => {
        if (!guard.isCurrent(requestId)) {
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
            result.evidence
          )
        );
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

test("a follow-up conversation keeps evidence sections on every assistant message", async () => {
  const harness = createEvidenceHarness({
    fetchImplementation: async () => structuredAnswer(),
  });

  harness.ask("Apa yang diketahui?");
  await harness.settle();
  harness.ask("Kalau untuk productivity?");
  await harness.settle();

  assert.equal(harness.state.messages.length, 4);
  for (const message of harness.state.messages) {
    assert.equal(message.role === BUILD_CHAT_MESSAGE_ROLE.assistant
      ? message.evidence.knownFacts.length >= 0
      : true, true);
  }
  assert.deepEqual(
    harness.state.messages.filter((m) => m.role === BUILD_CHAT_MESSAGE_ROLE.assistant)
      .map((m) => m.evidence.unknown.length),
    [3, 3]
  );
});

test("history serialization stays strict and drops evidence from assistant turns", () => {
  let state = answered(
    "Apa yang diketahui?",
    "Jawaban.",
    { known_facts: ["fakta hanya untuk tampilan."], interpretation: [], unknown: [] }
  );
  state = completeBuildChatRequest(
    startBuildChatRequest(state, "Kalau untuk productivity?", BUILD_A_TOKEN),
    "Lanjutan.",
    BUILD_A_TOKEN,
    { known_facts: [], interpretation: ["interpretasi."], unknown: ["FPS."] }
  );

  const history = getBuildChatHistory(state);

  assert.deepEqual(history, [
    { role: "user", content: "Apa yang diketahui?" },
    { role: "assistant", content: "Jawaban." },
    { role: "user", content: "Kalau untuk productivity?" },
    { role: "assistant", content: "Lanjutan." },
  ]);
  for (const message of history) {
    assert.equal(
      "evidence" in message,
      false,
      "evidence never becomes part of the conversation history payload"
    );
  }
});

test("a reset conversation drops evidence and returns to idle", () => {
  const state = answered(
    "Apa yang diketahui?",
    "Jawaban.",
    { known_facts: ["fakta."], interpretation: [], unknown: [] }
  );

  const reset = resetBuildChatConversation(state);

  assert.equal(reset.status, CHAT_STATUS.idle);
  assert.deepEqual(reset.messages, []);
  assert.equal(reset.buildToken, BUILD_A_TOKEN);
});

test("a reset preserves the selected build configuration", () => {
  let config = createBuildConfig();
  config = setBuildCpu(config, { id: 1, name: cpuDetail.name, type: "CPU" });
  config = setBuildGpu(config, { id: 3361, name: gpuDetail.name, type: "GPU" });
  const context = setBuildResolution(
    setBuildUseCase(createBuildUserContext(), "Gaming"),
    "1440p"
  );
  const before = JSON.stringify({ config, context });

  resetBuildChatConversation(
    answered(
      "q",
      "Jawaban.",
      { known_facts: ["fakta."], interpretation: [], unknown: [] }
    )
  );

  assert.equal(JSON.stringify({ config, context }), before);
  assert.equal(getBuildSelection(config, "CPU").id, 1);
  assert.equal(getBuildSelection(config, "GPU").id, 3361);
});

test("a stale success with evidence is ignored after a build change", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createEvidenceHarness({
    fetchFor: async () => {
      await pending;
      return structuredAnswer("Jawaban untuk build lama.");
    },
  });

  harness.ask("Bagaimana karakter build ini?");
  harness.changeBuild({ gpu: otherGpuDetail });
  release();
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.deepEqual(harness.state.messages, []);
  assert.equal(harness.state.buildToken, BUILD_B_TOKEN);
});

test("a stale failure is ignored after a build change", async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });

  const harness = createEvidenceHarness({
    fetchFor: async () => {
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
});

test("a failed follow-up keeps prior evidence and retries without duplication", async () => {
  const responses = [
    structuredAnswer("Jawaban pertama."),
    { ok: false, status: 503, json: async () => ({}) },
    structuredAnswer("Jawaban setelah retry."),
  ];
  let call = 0;
  const harness = createEvidenceHarness({
    fetchImplementation: async () => responses[call++],
  });

  harness.ask("Pertanyaan pertama?");
  await harness.settle();

  const firstAssistant = harness.state.messages[1];

  harness.ask("Pertanyaan kedua?");
  await harness.settle();
  assert.equal(harness.state.status, CHAT_STATUS.error);
  assert.equal(harness.state.messages.length, 2);

  harness.ask(harness.state.pendingQuestion);
  await harness.settle();

  assert.equal(harness.state.status, CHAT_STATUS.success);
  assert.equal(harness.state.messages.length, 4);
  assert.equal(
    harness.state.messages.filter((m) => m.content === "Pertanyaan kedua?").length,
    1
  );
  assert.deepEqual(firstAssistant.evidence.knownFacts, [
    "CPU 8 cores / 16 threads.",
    "GPU 16 GB VRAM GDDR7.",
  ]);
});

test("comparison selection stays isolated from evidence messages", () => {
  let compareList = addComparisonSelection([], { id: 9, type: "GPU" });
  const before = JSON.stringify(compareList);

  answered("q", "Jawaban.", {
    known_facts: ["fakta."],
    interpretation: [],
    unknown: [],
  });

  assert.equal(JSON.stringify(compareList), before);
});

test("hardware chat stays on its own single-answer contract", async () => {
  const hardwareState = createHardwareChatState();
  assert.equal(hardwareState.status, HARDWARE_CHAT_STATUS.idle);
  assert.equal(hardwareState.answer, "");

  const answer = await requestHardwareChatAnswer(
    buildHardwareChatContext(cpuDetail, cpuBenchmarks),
    "q",
    async () => ({
      ok: true,
      json: async () => ({ answer: "Hanya teks." }),
    })
  );

  assert.equal(answer, "Hanya teks.");
});

test("no fabricated GPU benchmark is introduced by the build payload", () => {
  const payload = buildChatPayload(
    cpuDetail,
    gpuDetail,
    userContext,
    "Apa yang diketahui?",
    benchmarks
  );

  assert.deepEqual(payload.build.gpu.benchmarks, []);
  assert.equal(JSON.stringify(payload).toLowerCase().includes("\"fps\""), false);
});

test("null specifications stay N/A and are never inflated by evidence", () => {
  const payload = buildChatPayload(
    {
      ...cpuDetail,
      specifications: {
        cores: 8,
        threads: 16,
        base_clock_ghz: null,
        boost_clock_ghz: null,
        tdp_w: null,
      },
    },
    {
      ...gpuDetail,
      specifications: {
        memory_gb: 16,
        memory_type: null,
        tdp_w: null,
      },
    },
    userContext,
    "Apa yang diketahui?",
    benchmarks
  );

  assert.equal(payload.build.cpu.specifications.boost_clock_ghz, null);
  assert.equal(payload.build.gpu.specifications.tdp_w, null);
});

test("evidence items remain bounded inside a completed message", () => {
  const longItem = "y".repeat(BUILD_CHAT_EVIDENCE_MAX_ITEM_LENGTH + 500);

  assert.equal(
    normalizeBuildChatEvidence({
      known_facts: [longItem],
      interpretation: [],
      unknown: [],
    }),
    null
  );
});