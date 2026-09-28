import { apiUrl } from "./api.js";
import {
  BUILD_CHAT_ENDPOINT_PATH,
  BUILD_CHAT_INTEGRATION_STATUS,
  buildBuildChatContext,
  toBuildUserContext,
} from "./buildConfig.js";
import {
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  createChatRequestGuard,
  getChatErrorKind,
  getChatErrorKindFromError,
  getChatLoadingParts,
} from "./hardwareChat.js";

export {
  BUILD_CHAT_ENDPOINT_PATH,
  BUILD_CHAT_INTEGRATION_STATUS,
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  getChatLoadingParts,
};

export const BUILD_CHAT_QUESTION_MAX_LENGTH = 2000;
export const BUILD_CHAT_HISTORY_MAX_MESSAGES = 10;
export const BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH = 4000;

const CHAT_ENDPOINT = apiUrl(BUILD_CHAT_ENDPOINT_PATH);

export const BUILD_CHAT_MESSAGE_ROLE = {
  user: "user",
  assistant: "assistant",
};

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

const truncateHistoryContent = (content) =>
  content.length > BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH
    ? content.slice(0, BUILD_CHAT_HISTORY_MAX_MESSAGE_LENGTH)
    : content;

const expectedHistoryRole = (index) =>
  index % 2 === 0
    ? BUILD_CHAT_MESSAGE_ROLE.user
    : BUILD_CHAT_MESSAGE_ROLE.assistant;

const isStrictlyAlternating = (messages) =>
  messages.every(
    (message, index) =>
      message !== null &&
      typeof message === "object" &&
      message.role === expectedHistoryRole(index)
  );

/* ---------- Bounded conversation history ---------- */

export const buildBuildChatHistory = (messages) => {
  if (!Array.isArray(messages) || !isStrictlyAlternating(messages)) {
    return [];
  }

  const window = messages.slice(-BUILD_CHAT_HISTORY_MAX_MESSAGES);

  if (window[0]?.role !== BUILD_CHAT_MESSAGE_ROLE.user) {
    window.shift();
  }

  const history = [];
  for (const message of window) {
    const content =
      typeof message?.content === "string" ? message.content.trim() : "";

    if (!content) {
      return [];
    }

    history.push({
      role: message.role,
      content: truncateHistoryContent(content),
    });
  }

  return history;
};

export const getBuildChatHistory = (state) =>
  buildBuildChatHistory(state?.messages);

export const buildChatPayload = (
  cpuDetail,
  gpuDetail,
  userContext,
  question,
  benchmarksBySlot = {},
  messages = []
) => {
  const normalizedQuestion = normalizeBuildChatQuestion(question);

  if (!isValidBuildChatQuestion(normalizedQuestion)) {
    throw new Error(
      `A build chat question must be between 1 and ${BUILD_CHAT_QUESTION_MAX_LENGTH} characters.`
    );
  }

  const history = buildBuildChatHistory(messages);
  const payload = {
    build: buildBuildChatContext(
      cpuDetail,
      gpuDetail,
      userContext,
      benchmarksBySlot
    ),
  };

  if (history.length > 0) {
    payload.messages = history;
  }

  payload.question = normalizedQuestion;

  return payload;
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

/* ---------- Build identity ---------- */

export const getBuildChatToken = (snapshot) => {
  if (!snapshot) {
    return "";
  }

  const { use_case: useCase, resolution } = toBuildUserContext({
    useCase: snapshot.useCase,
    resolution: snapshot.resolution,
  });

  return [
    snapshot.cpuId ?? "none",
    snapshot.gpuId ?? "none",
    useCase,
    resolution,
  ].join(":");
};

export const isSameBuildChatToken = (token, other) => token === other;

/* ---------- Conversation state ---------- */

export const createBuildChatState = (buildToken = "") => ({
  buildToken,
  status: CHAT_STATUS.idle,
  messages: [],
  pendingQuestion: "",
  error: null,
});

export const getBuildChatMessages = (state) => state.messages;

export const hasBuildChatConversation = (state) => state.messages.length > 0;

export const resetBuildChatConversation = (state) =>
  createBuildChatState(state?.buildToken ?? "");

export const isBuildChatBusy = (state) =>
  state.status === CHAT_STATUS.loading;

const createMessage = (role, content, index) => ({
  id: `build-chat-message-${index}`,
  role,
  content,
});

const isResponseForThisConversation = (state, token) =>
  token === undefined || token === state.buildToken;

const canStartRequest = (state) =>
  state.status !== CHAT_STATUS.loading &&
  isValidBuildChatQuestion(state.pendingQuestion);

export const startBuildChatRequest = (state, question, buildToken) => {
  if (!isValidBuildChatQuestion(question)) {
    return state;
  }

  return {
    ...state,
    buildToken: buildToken ?? state.buildToken,
    status: CHAT_STATUS.loading,
    pendingQuestion: normalizeBuildChatQuestion(question),
    error: null,
  };
};

export const retryBuildChatRequest = (state) => {
  if (!canStartRequest(state)) {
    return state;
  }

  return {
    ...state,
    status: CHAT_STATUS.loading,
    error: null,
  };
};

export const completeBuildChatRequest = (state, answer, token) => {
  if (!isResponseForThisConversation(state, token)) {
    return state;
  }

  if (!isValidBuildChatQuestion(state.pendingQuestion)) {
    return state;
  }

  const nextIndex = state.messages.length;

  return {
    ...state,
    status: CHAT_STATUS.success,
    messages: [
      ...state.messages,
      createMessage(
        BUILD_CHAT_MESSAGE_ROLE.user,
        state.pendingQuestion,
        nextIndex
      ),
      createMessage(BUILD_CHAT_MESSAGE_ROLE.assistant, answer, nextIndex + 1),
    ],
    pendingQuestion: "",
    error: null,
  };
};

export const failBuildChatRequest = (state, error, token) => {
  if (!isResponseForThisConversation(state, token)) {
    return state;
  }

  return {
    ...state,
    status: CHAT_STATUS.error,
    error: {
      kind: getBuildChatErrorKindFromError(error),
      message: error?.message || "The build chat request could not be completed.",
    },
  };
};

export { createChatRequestGuard };
