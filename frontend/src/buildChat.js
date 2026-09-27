import { apiUrl } from "./api.js";
import {
  BUILD_CHAT_ENDPOINT_PATH,
  BUILD_CHAT_INTEGRATION_STATUS,
  buildBuildChatContext,
} from "./buildConfig.js";
import {
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  createChatRequestGuard,
  getChatErrorKind,
  getChatErrorKindFromError,
} from "./hardwareChat.js";

export {
  BUILD_CHAT_ENDPOINT_PATH,
  BUILD_CHAT_INTEGRATION_STATUS,
  CHAT_ERROR_KIND,
  CHAT_STATUS,
};

export const BUILD_CHAT_QUESTION_MAX_LENGTH = 2000;

const CHAT_ENDPOINT = apiUrl(BUILD_CHAT_ENDPOINT_PATH);

export const BUILD_CHAT_SUGGESTED_QUESTIONS = [
  "Bagaimana karakter build ini untuk gaming 1440p?",
  "Apa kelebihan utama CPU dan GPU ini?",
  "Apa yang masih belum bisa disimpulkan dari spesifikasi ini?",
  "Jelaskan build ini berdasarkan data SPECTRA.",
];

export const normalizeBuildChatQuestion = (question) =>
  typeof question === "string" ? question.trim() : "";

export const isValidBuildChatQuestion = (question) => {
  const normalized = normalizeBuildChatQuestion(question);

  return normalized.length > 0 && normalized.length <= BUILD_CHAT_QUESTION_MAX_LENGTH;
};

export const buildChatPayload = (
  cpuDetail,
  gpuDetail,
  userContext,
  question,
  benchmarksBySlot = {}
) => {
  const normalizedQuestion = normalizeBuildChatQuestion(question);

  if (!isValidBuildChatQuestion(normalizedQuestion)) {
    throw new Error(
      `A build chat question must be between 1 and ${BUILD_CHAT_QUESTION_MAX_LENGTH} characters.`
    );
  }

  return {
    build: buildBuildChatContext(
      cpuDetail,
      gpuDetail,
      userContext,
      benchmarksBySlot
    ),
    question: normalizedQuestion,
  };
};

export class BuildChatError extends Error {
  constructor(message, kind, status) {
    super(message);
    this.name = "BuildChatError";
    this.kind = kind;
    this.status = status;
  }
}

export const getBuildChatErrorKind = getChatErrorKind;

export const getBuildChatErrorKindFromError = (error) =>
  error instanceof BuildChatError
    ? error.kind
    : getChatErrorKindFromError(error);

export const requestBuildChatAnswer = async (
  payload,
  fetchImplementation = fetch
) => {
  let response;

  try {
    response = await fetchImplementation(CHAT_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (networkError) {
    throw new BuildChatError(
      networkError?.message || "The build chat request could not be sent.",
      CHAT_ERROR_KIND.request
    );
  }

  if (!response.ok) {
    throw new BuildChatError(
      `Build chat request failed with status ${response.status}`,
      getBuildChatErrorKind(response.status),
      response.status
    );
  }

  const responsePayload = await response.json();

  if (
    typeof responsePayload?.answer !== "string" ||
    responsePayload.answer.trim() === ""
  ) {
    throw new BuildChatError(
      "The build chat response did not contain an answer.",
      CHAT_ERROR_KIND.empty
    );
  }

  return responsePayload.answer;
};

export const createBuildChatState = () => ({
  status: CHAT_STATUS.idle,
  question: "",
  lastQuestion: "",
  answeredQuestion: "",
  answer: "",
  error: null,
  buildSnapshot: null,
});

export const startBuildChatRequest = (state, question, buildSnapshot = null) => ({
  ...state,
  status: CHAT_STATUS.loading,
  question,
  lastQuestion: question,
  answeredQuestion: "",
  answer: "",
  error: null,
  buildSnapshot,
});

export const completeBuildChatRequest = (state, answer) => ({
  ...state,
  status: CHAT_STATUS.success,
  question: "",
  answeredQuestion: state.lastQuestion,
  answer,
  error: null,
});

export const failBuildChatRequest = (state, error) => ({
  ...state,
  status: CHAT_STATUS.error,
  question: state.lastQuestion,
  error: {
    kind: getBuildChatErrorKindFromError(error),
    message: error?.message || "The build chat request could not be completed.",
  },
});

export { createChatRequestGuard };
