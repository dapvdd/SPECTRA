import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setImmediate as scheduleImmediate } from "node:timers/promises";

import {
  BUILD_CHAT_ANALYSIS_LABELS,
  BUILD_CHAT_ANALYSIS_MAX_ITEM_LENGTH,
  BUILD_CHAT_ANALYSIS_MAX_ITEMS,
  BUILD_CHAT_ANALYSIS_SECTION,
  BUILD_CHAT_MESSAGE_ROLE,
  CHAT_STATUS,
  buildChatPayload,
  completeBuildChatRequest,
  createBuildChatState,
  createEmptyBuildChatAnalysis,
  getBuildChatAnalysisSections,
  getBuildChatHistory,
  getBuildChatToken,
  normalizeBuildChatAnalysis,
  requestBuildChatAnswer,
  resetBuildChatConversation,
  startBuildChatRequest,
} from "./buildChat.js";
import { createChatRequestGuard } from "./hardwareChat.js";
import { getBuildChatSnapshot } from "./buildConfig.js";

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

const VALID_ANALYSIS = {
  strengths: ["CPU 8 cores / 16 threads mendukung karakter multi-threaded."],
  considerations: ["Data yang tersedia tidak memuat FPS aktual pada game tertentu."],
  data_gaps: ["Benchmark GPU untuk GPU yang dipilih belum tersedia."],
};

const OK_EVIDENCE = {
  known_facts: ["CPU 8 cores / 16 threads."],
  interpretation: ["Build menggabungkan CPU multi-core dengan GPU diskrit."],
  unknown: ["FPS pada 1440p."],
};

const okBody = (overrides = {}) => ({
  ok: true,
  json: async () => ({
    answer: "Berdasarkan data tersimpan.",
    evidence: OK_EVIDENCE,
    analysis: VALID_ANALYSIS,
    ...overrides,
  }),
});

const answering = (fetchImplementation) =>
  requestBuildChatAnswer(
    buildChatPayload(cpuDetail, gpuDetail, userContext, "q", benchmarks),
    fetchImplementation
  );

const asking = (question, buildToken = BUILD_A_TOKEN) =>
  startBuildChatRequest(createBuildChatState(buildToken), question, buildToken);

const answered = (question, answer, evidence, analysis, buildToken = BUILD_A_TOKEN) =>
  completeBuildChatRequest(
    asking(question, buildToken),
    answer,
    buildToken,
    evidence,
    analysis
  );

/* ---------- normalization ---------- */

test("a valid analysis object is normalized to camelCase keys", () => {
  assert.deepEqual(
    normalizeBuildChatAnalysis({
      strengths: VALID_ANALYSIS.strengths,
      considerations: VALID_ANALYSIS.considerations,
      data_gaps: VALID_ANALYSIS.data_gaps,
    }),
    {
      strengths: VALID_ANALYSIS.strengths,
      considerations: VALID_ANALYSIS.considerations,
      dataGaps: VALID_ANALYSIS.data_gaps,
    }
  );
});

test("each analysis section normalizes independently", () => {
  assert.deepEqual(normalizeBuildChatAnalysis({ strengths: ["kekuatan."] }), {
    strengths: ["kekuatan."],
    considerations: [],
    dataGaps: [],
  });
  assert.deepEqual(
    normalizeBuildChatAnalysis({ considerations: ["pertimbangan."] }),
    {
      strengths: [],
      considerations: ["pertimbangan."],
      dataGaps: [],
    }
  );
  assert.deepEqual(normalizeBuildChatAnalysis({ data_gaps: ["celah data."] }), {
    strengths: [],
    considerations: [],
    dataGaps: ["celah data."],
  });
});

test("an already normalized analysis normalizes to itself", () => {
  const once = normalizeBuildChatAnalysis(VALID_ANALYSIS);

  assert.deepEqual(normalizeBuildChatAnalysis(once), once);
});

test("analysis items are trimmed and empty analysis normalizes to empty sections", () => {
  assert.deepEqual(normalizeBuildChatAnalysis({ strengths: ["  kekuatan.  "] }), {
    strengths: ["kekuatan."],
    considerations: [],
    dataGaps: [],
  });
  assert.deepEqual(normalizeBuildChatAnalysis({}), createEmptyBuildChatAnalysis());
  assert.deepEqual(
    createEmptyBuildChatAnalysis(),
    { strengths: [], considerations: [], dataGaps: [] }
  );
});

test("malformed analysis is rejected instead of partially trusted", () => {
  for (const value of [
    null,
    undefined,
    "analysis",
    42,
    ["strengths"],
    { strengths: "bukan array" },
    { strengths: [42] },
    { strengths: [{ value: "object" }] },
    { strengths: ["   "] },
    { strengths: [null] },
    { score: 90 },
    { strengths: [], recommendation: [] },
  ]) {
    assert.equal(
      normalizeBuildChatAnalysis(value),
      null,
      `expected malformed analysis to be rejected: ${JSON.stringify(value)}`
    );
  }
});

test("analysis item limits are enforced on both count and length", () => {
  assert.deepEqual(
    normalizeBuildChatAnalysis({
      strengths: Array.from(
        { length: BUILD_CHAT_ANALYSIS_MAX_ITEMS },
        (_, index) => `item ${index}`
      ),
    }).strengths.length,
    BUILD_CHAT_ANALYSIS_MAX_ITEMS
  );
  assert.equal(
    normalizeBuildChatAnalysis({
      considerations: Array.from(
        { length: BUILD_CHAT_ANALYSIS_MAX_ITEMS + 1 },
        (_, index) => `item ${index}`
      ),
    }),
    null
  );
  assert.equal(
    normalizeBuildChatAnalysis({
      data_gaps: ["x".repeat(BUILD_CHAT_ANALYSIS_MAX_ITEM_LENGTH)],
    }).dataGaps.length,
    1
  );
  assert.equal(
    normalizeBuildChatAnalysis({
      data_gaps: ["x".repeat(BUILD_CHAT_ANALYSIS_MAX_ITEM_LENGTH + 1)],
    }),
    null
  );
});

/* ---------- response handling ---------- */

test("the client returns the normalized analysis next to the answer and evidence", async () => {
  const result = await answering(async () => okBody());

  assert.equal(result.answer, "Berdasarkan data tersimpan.");
  assert.deepEqual(result.analysis, {
    strengths: VALID_ANALYSIS.strengths,
    considerations: VALID_ANALYSIS.considerations,
    dataGaps: VALID_ANALYSIS.data_gaps,
  });
});

test("a malformed analysis never crashes the client and never invents content", async () => {
  const result = await answering(async () =>
    okBody({ analysis: { strengths: ["  ", 42] } })
  );

  assert.deepEqual(result.analysis, createEmptyBuildChatAnalysis());
  assert.equal(result.answer, "Berdasarkan data tersimpan.");
  assert.deepEqual(result.evidence, {
    knownFacts: OK_EVIDENCE.known_facts,
    interpretation: OK_EVIDENCE.interpretation,
    unknown: OK_EVIDENCE.unknown,
  });
});

test("a missing analysis degrades to empty sections instead of failing the answer", async () => {
  const result = await answering(async () => ({
    ok: true,
    json: async () => ({ answer: "Jawaban.", evidence: OK_EVIDENCE }),
  }));

  assert.deepEqual(result.analysis, createEmptyBuildChatAnalysis());
});

test("an assistant message keeps the analysis as response metadata", () => {
  const state = answered(
    "Apa yang diketahui?",
    "Jawaban.",
    OK_EVIDENCE,
    VALID_ANALYSIS
  );

  const [, assistant] = state.messages;

  assert.equal(assistant.role, BUILD_CHAT_MESSAGE_ROLE.assistant);
  assert.deepEqual(assistant.analysis, {
    strengths: VALID_ANALYSIS.strengths,
    considerations: VALID_ANALYSIS.considerations,
    dataGaps: VALID_ANALYSIS.data_gaps,
  });
  assert.deepEqual(assistant.evidence, {
    knownFacts: OK_EVIDENCE.known_facts,
    interpretation: OK_EVIDENCE.interpretation,
    unknown: OK_EVIDENCE.unknown,
  });
});

test("a user message never carries an analysis", () => {
  const state = answered("q", "a", OK_EVIDENCE, VALID_ANALYSIS);

  const [user] = state.messages;

  assert.equal("analysis" in user, false);
  assert.equal("evidence" in user, false);
});

test("a completed message without analysis falls back to empty sections", () => {
  const state = answered("q", "a", OK_EVIDENCE);

  assert.deepEqual(state.messages[1].analysis, createEmptyBuildChatAnalysis());
});

/* ---------- rendering sections ---------- */

test("analysis sections render in stable order with labels", () => {
  const sections = getBuildChatAnalysisSections({
    strengths: ["kekuatan."],
    considerations: ["pertimbangan."],
    dataGaps: ["celah data."],
  });

  assert.deepEqual(
    sections.map((section) => section.label),
    [
      BUILD_CHAT_ANALYSIS_LABELS.strengths,
      BUILD_CHAT_ANALYSIS_LABELS.considerations,
      BUILD_CHAT_ANALYSIS_LABELS.dataGaps,
    ]
  );
  assert.deepEqual(
    sections.map((section) => section.key),
    ["strengths", "considerations", "dataGaps"]
  );
  assert.equal(sections[2].items[0], "celah data.");
});

test("section keys map to the backend snake_case vocabulary", () => {
  assert.equal(BUILD_CHAT_ANALYSIS_SECTION.strengths, "strengths");
  assert.equal(BUILD_CHAT_ANALYSIS_SECTION.considerations, "considerations");
  assert.equal(BUILD_CHAT_ANALYSIS_SECTION.dataGaps, "data_gaps");
});

test("missing or empty analysis yields no sections to render", () => {
  for (const value of [undefined, null, createEmptyBuildChatAnalysis()]) {
    assert.deepEqual(
      getBuildChatAnalysisSections(value).map((section) => section.items),
      [[], [], []]
    );
  }
});

test("the transcript renders the analysis after the evidence without raw HTML", () => {
  const source = readFileSync(new URL("./App.jsx", import.meta.url), "utf8");

  assert.equal(source.includes("dangerouslySetInnerHTML"), false);
  assert.equal(
    source.includes("<BuildChatEvidence evidence={message.evidence} />"),
    true
  );
  assert.equal(
    source.includes("<BuildChatAnalysis analysis={message.analysis} />"),
    true
  );
  assert.equal(
    source.indexOf("<BuildChatEvidence evidence={message.evidence} />") <
      source.indexOf("<BuildChatAnalysis analysis={message.analysis} />"),
    true,
    "the analysis renders after the evidence"
  );
  assert.equal(source.includes("build-chat-analysis-section"), true);
  assert.equal(source.includes("Build analysis"), true);
  assert.match(
    source,
    /getBuildChatAnalysisSections\(analysis\)\.filter\([\s\S]*?section\.items\.length > 0/
  );
});

test("the analysis stylesheet keeps sections usable and wrap-safe", () => {
  const css = readFileSync(new URL("./App.css", import.meta.url), "utf8");

  for (const selector of [
    ".build-chat-analysis",
    ".build-chat-analysis-title",
    ".build-chat-analysis-section",
    ".build-chat-analysis-label",
    ".build-chat-analysis-list",
    ".build-chat-analysis-item",
  ]) {
    assert.match(css, new RegExp(selector.replace(/\./g, "\\.") + "\\s*\\{"));
  }
  assert.match(
    css,
    /\.build-chat-analysis-item\s*\{[^}]*overflow-wrap:\s*anywhere/
  );
});

/* ---------- conversation and stale-response compatibility ---------- */

const createHarness = ({ fetchImplementation }) => {
  const guard = createChatRequestGuard();
  const harness = {
    cpu: cpuDetail,
    gpu: gpuDetail,
    context: userContext,
    token: BUILD_A_TOKEN,
    state: createBuildChatState(BUILD_A_TOKEN),
    apply(nextState) {
      harness.state = nextState;
      return nextState;
    },
  };

  harness.ask = (question) => {
    if (harness.state.status === CHAT_STATUS.loading) {
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

    const requestId = guard.begin();
    const requestToken = harness.token;
    harness.apply(startBuildChatRequest(harness.state, payload.question, requestToken));

    requestBuildChatAnswer(payload, fetchImplementation).then(
      (result) => {
        if (!guard.isCurrent(requestId)) {
          return;
        }
        if (!isSameBuildToken(harness.token, requestToken)) {
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
      },
      (error) => {
        if (!guard.isCurrent(requestId)) {
          return;
        }
        harness.apply({
          ...harness.state,
          status: CHAT_STATUS.error,
          error: { kind: "request", message: error?.message ?? "" },
        });
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

const isSameBuildToken = (token, other) => token === other;

test("a follow-up conversation keeps the analysis on every assistant message", async () => {
  const harness = createHarness({ fetchImplementation: async () => okBody() });

  harness.ask("Apa yang diketahui?");
  await harness.settle();
  harness.ask("Kalau untuk productivity?");
  await harness.settle();

  assert.equal(harness.state.messages.length, 4);
  assert.deepEqual(
    harness.state.messages
      .filter((message) => message.role === BUILD_CHAT_MESSAGE_ROLE.assistant)
      .map((message) => message.analysis.dataGaps.length),
    [1, 1]
  );
});

test("history serialization keeps only role and content, never the analysis", () => {
  const state = answered(
    "Apa yang diketahui?",
    "Jawaban.",
    OK_EVIDENCE,
    VALID_ANALYSIS
  );
  const next = completeBuildChatRequest(
    startBuildChatRequest(state, "Kalau untuk productivity?", BUILD_A_TOKEN),
    "Lanjutan.",
    BUILD_A_TOKEN,
    OK_EVIDENCE,
    VALID_ANALYSIS
  );

  const history = getBuildChatHistory(next);

  assert.deepEqual(history, [
    { role: "user", content: "Apa yang diketahui?" },
    { role: "assistant", content: "Jawaban." },
    { role: "user", content: "Kalau untuk productivity?" },
    { role: "assistant", content: "Lanjutan." },
  ]);
  for (const message of history) {
    assert.equal(
      "analysis" in message,
      false,
      "AI analysis never becomes authoritative build context"
    );
    assert.equal("evidence" in message, false);
  }
});

test("a stale response for a previous build is discarded with its analysis", async () => {
  const harness = createHarness({ fetchImplementation: async () => okBody() });

  harness.ask("Apa yang diketahui?");
  harness.changeBuild({ gpu: otherGpuDetail });
  await harness.settle();

  assert.equal(harness.state.messages.length, 0);
  assert.equal(harness.state.status, CHAT_STATUS.idle);
  assert.notEqual(harness.token, BUILD_A_TOKEN);
  assert.equal(tokenFor(cpuDetail, otherGpuDetail), BUILD_B_TOKEN);
});

test("a reset conversation drops the analysis and returns to idle", () => {
  const state = answered("q", "a", OK_EVIDENCE, VALID_ANALYSIS);

  const reset = resetBuildChatConversation(state);

  assert.equal(reset.status, CHAT_STATUS.idle);
  assert.deepEqual(reset.messages, []);
  assert.equal(reset.buildToken, BUILD_A_TOKEN);
});
