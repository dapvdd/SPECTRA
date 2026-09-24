import { apiUrl } from "./api.js";

export const CHAT_STATUS = {
  idle: "idle",
  loading: "loading",
  success: "success",
  error: "error",
};

export const CHAT_ERROR_KIND = {
  request: "request",
  validation: "validation",
  provider: "provider",
  empty: "empty",
};

const CHAT_ENDPOINT = apiUrl("/hardware/chat");

const BENCHMARK_FIELDS = [
  "id",
  "hardware_id",
  "benchmark_name",
  "test_type",
  "score",
  "unit",
  "source",
  "recorded_at",
];

const getBenchmarkRecords = (benchmarkPayload) => {
  if (Array.isArray(benchmarkPayload)) {
    return benchmarkPayload;
  }

  if (!benchmarkPayload || typeof benchmarkPayload !== "object") {
    return [];
  }

  if (Array.isArray(benchmarkPayload.benchmark_results)) {
    return benchmarkPayload.benchmark_results;
  }

  if (Array.isArray(benchmarkPayload.benchmarks)) {
    return benchmarkPayload.benchmarks;
  }

  if (Array.isArray(benchmarkPayload.results)) {
    return benchmarkPayload.results;
  }

  if (
    benchmarkPayload.performance &&
    Array.isArray(benchmarkPayload.performance.results)
  ) {
    return benchmarkPayload.performance.results;
  }

  return [];
};

const pickFields = (record, fields) => {
  const picked = {};
  for (const field of fields) {
    if (record?.[field] !== undefined) {
      picked[field] = record[field];
    }
  }
  return picked;
};

export const buildHardwareChatContext = (detail, benchmarkPayload) => {
  const source = detail ?? {};

  return {
    id: source.id,
    name: source.name,
    manufacturer: source.manufacturer,
    type: source.type,
    specifications: source.specifications,
    benchmarks: getBenchmarkRecords(benchmarkPayload).map((benchmark) =>
      pickFields(benchmark, BENCHMARK_FIELDS),
    ),
  };
};

export class HardwareChatError extends Error {
  constructor(message, kind, status) {
    super(message);
    this.name = "HardwareChatError";
    this.kind = kind;
    this.status = status;
  }
}

export const getChatErrorKind = (status) => {
  if (status === 422) {
    return CHAT_ERROR_KIND.validation;
  }

  if (status === 502 || status === 503) {
    return CHAT_ERROR_KIND.provider;
  }

  return CHAT_ERROR_KIND.request;
};

export const getChatErrorKindFromError = (error) =>
  error instanceof HardwareChatError
    ? error.kind
    : CHAT_ERROR_KIND.request;

export const requestHardwareChatAnswer = async (
  context,
  question,
  fetchImplementation = fetch
) => {
  const response = await fetchImplementation(CHAT_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ hardware: context, question }),
  });

  if (!response.ok) {
    throw new HardwareChatError(
      `Chat request failed with status ${response.status}`,
      getChatErrorKind(response.status),
      response.status
    );
  }

  const payload = await response.json();

  if (typeof payload?.answer !== "string" || payload.answer.trim() === "") {
    throw new HardwareChatError(
      "The AI chat response did not contain an answer.",
      CHAT_ERROR_KIND.empty
    );
  }

  return payload.answer;
};

export const createHardwareChatState = () => ({
  status: CHAT_STATUS.idle,
  question: "",
  lastQuestion: "",
  answeredQuestion: "",
  answer: "",
  error: null,
});

export const startHardwareChatRequest = (state, question) => ({
  ...state,
  status: CHAT_STATUS.loading,
  question,
  lastQuestion: question,
  error: null,
});

export const completeHardwareChatRequest = (state, answer) => ({
  ...state,
  status: CHAT_STATUS.success,
  question: "",
  answeredQuestion: state.lastQuestion,
  answer,
  error: null,
});

export const failHardwareChatRequest = (state, error) => ({
  ...state,
  status: CHAT_STATUS.error,
  question: "",
  error: {
    kind: getChatErrorKindFromError(error),
    message: error?.message || "The chat request could not be completed.",
  },
});

export const createChatRequestGuard = () => {
  let currentRequestId = 0;

  return {
    begin: () => (currentRequestId += 1),
    isCurrent: (requestId) => requestId === currentRequestId,
    invalidate: () => (currentRequestId += 1),
  };
};