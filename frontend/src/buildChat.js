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
export const BUILD_CHAT_EVIDENCE_MAX_ITEMS = 10;
export const BUILD_CHAT_EVIDENCE_MAX_ITEM_LENGTH = 1000;
export const BUILD_CHAT_ANALYSIS_MAX_ITEMS = 5;
export const BUILD_CHAT_ANALYSIS_MAX_ITEM_LENGTH = 500;

export const BUILD_CHAT_EVIDENCE_SECTION = {
  knownFacts: "known_facts",
  interpretation: "interpretation",
  unknown: "unknown",
};

export const BUILD_CHAT_EVIDENCE_LABELS = {
  knownFacts: "Known facts",
  interpretation: "Interpretation",
  unknown: "Unknown / not provided",
};

export const BUILD_CHAT_ANALYSIS_SECTION = {
  strengths: "strengths",
  considerations: "considerations",
  dataGaps: "data_gaps",
};

export const BUILD_CHAT_ANALYSIS_LABELS = {
  strengths: "Strengths",
  considerations: "Considerations",
  dataGaps: "Data gaps",
};

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

/* ---------- Evidence ---------- */

export const createEmptyBuildChatEvidence = () => ({
  knownFacts: [],
  interpretation: [],
  unknown: [],
});

export const getBuildChatEvidenceSections = (evidence) => {
  const source = evidence ?? createEmptyBuildChatEvidence();

  return [
    {
      key: "knownFacts",
      section: BUILD_CHAT_EVIDENCE_SECTION.knownFacts,
      label: BUILD_CHAT_EVIDENCE_LABELS.knownFacts,
      items: source.knownFacts ?? [],
    },
    {
      key: "interpretation",
      section: BUILD_CHAT_EVIDENCE_SECTION.interpretation,
      label: BUILD_CHAT_EVIDENCE_LABELS.interpretation,
      items: source.interpretation ?? [],
    },
    {
      key: "unknown",
      section: BUILD_CHAT_EVIDENCE_SECTION.unknown,
      label: BUILD_CHAT_EVIDENCE_LABELS.unknown,
      items: source.unknown ?? [],
    },
  ];
};

const EVIDENCE_KEY_MAP = {
  known_facts: "knownFacts",
  knownFacts: "knownFacts",
  interpretation: "interpretation",
  unknown: "unknown",
};

const isEvidenceItem = (item) =>
  typeof item === "string" &&
  item.trim() !== "" &&
  item.length <= BUILD_CHAT_EVIDENCE_MAX_ITEM_LENGTH;

export const normalizeBuildChatEvidence = (evidence) => {
  if (evidence === null || typeof evidence !== "object" || Array.isArray(evidence)) {
    return null;
  }

  const givenKeys = Object.keys(evidence);
  const allowedKeys = Object.keys(EVIDENCE_KEY_MAP);

  if (givenKeys.some((key) => !allowedKeys.includes(key))) {
    return null;
  }

  const normalized = createEmptyBuildChatEvidence();

  for (const key of allowedKeys) {
    const items = evidence[key];

    if (items === undefined) {
      continue;
    }

    if (!Array.isArray(items) || items.length > BUILD_CHAT_EVIDENCE_MAX_ITEMS) {
      return null;
    }

    if (!items.every(isEvidenceItem)) {
      return null;
    }

    normalized[EVIDENCE_KEY_MAP[key]] = items.map((item) => item.trim());
  }

  return normalized;
};

/* ---------- Analysis ---------- */

export const createEmptyBuildChatAnalysis = () => ({
  strengths: [],
  considerations: [],
  dataGaps: [],
});

export const getBuildChatAnalysisSections = (analysis) => {
  const source = analysis ?? createEmptyBuildChatAnalysis();

  return [
    {
      key: "strengths",
      section: BUILD_CHAT_ANALYSIS_SECTION.strengths,
      label: BUILD_CHAT_ANALYSIS_LABELS.strengths,
      items: source.strengths ?? [],
    },
    {
      key: "considerations",
      section: BUILD_CHAT_ANALYSIS_SECTION.considerations,
      label: BUILD_CHAT_ANALYSIS_LABELS.considerations,
      items: source.considerations ?? [],
    },
    {
      key: "dataGaps",
      section: BUILD_CHAT_ANALYSIS_SECTION.dataGaps,
      label: BUILD_CHAT_ANALYSIS_LABELS.dataGaps,
      items: source.dataGaps ?? [],
    },
  ];
};

const ANALYSIS_KEY_MAP = {
  strengths: "strengths",
  considerations: "considerations",
  data_gaps: "dataGaps",
  dataGaps: "dataGaps",
};

const isAnalysisItem = (item) =>
  typeof item === "string" &&
  item.trim() !== "" &&
  item.length <= BUILD_CHAT_ANALYSIS_MAX_ITEM_LENGTH;

export const normalizeBuildChatAnalysis = (analysis) => {
  if (analysis === null || typeof analysis !== "object" || Array.isArray(analysis)) {
    return null;
  }

  const givenKeys = Object.keys(analysis);
  const allowedKeys = Object.keys(ANALYSIS_KEY_MAP);

  if (givenKeys.some((key) => !allowedKeys.includes(key))) {
    return null;
  }

  const normalized = createEmptyBuildChatAnalysis();

  for (const key of allowedKeys) {
    const items = analysis[key];

    if (items === undefined) {
      continue;
    }

    if (!Array.isArray(items) || items.length > BUILD_CHAT_ANALYSIS_MAX_ITEMS) {
      return null;
    }

    if (!items.every(isAnalysisItem)) {
      return null;
    }

    normalized[ANALYSIS_KEY_MAP[key]] = items.map((item) => item.trim());
  }

  return normalized;
};

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

  const evidence = normalizeBuildChatEvidence(responsePayload.evidence);

  if (evidence === null) {
    throw new BuildChatError(
      "The build chat response did not contain valid evidence.",
      CHAT_ERROR_KIND.provider
    );
  }

  return {
    answer: responsePayload.answer,
    evidence,
    analysis:
      normalizeBuildChatAnalysis(responsePayload.analysis) ??
      createEmptyBuildChatAnalysis(),
  };
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

export const BUILD_CHAT_CONVERSATION_STATUS = {
  idle: "idle",
  loading: "loading",
  ready: "ready",
  error: "error",
};

export const BUILD_CHAT_CONVERSATION_ERROR_KIND = {
  load: "load",
  save: "save",
  reset: "reset",
};

export const createBuildChatConversationState = () => ({
  status: BUILD_CHAT_CONVERSATION_STATUS.idle,
  error: null,
});

export const createBuildChatState = (buildToken = "") => ({
  buildToken,
  conversationId: null,
  conversation: createBuildChatConversationState(),
  status: CHAT_STATUS.idle,
  messages: [],
  pendingQuestion: "",
  error: null,
});

export const getBuildChatMessages = (state) => state.messages;

export const hasBuildChatConversation = (state) => state.messages.length > 0;

export const getBuildChatConversationId = (state) => state.conversationId ?? null;

export const isBuildChatRestoringConversation = (state) =>
  state?.conversation?.status === BUILD_CHAT_CONVERSATION_STATUS.loading;

export const getBuildChatConversationError = (state) =>
  state?.conversation?.error ?? null;

export const resetBuildChatConversation = (state) =>
  createBuildChatState(state?.buildToken ?? "");

export const isBuildChatBusy = (state) =>
  state.status === CHAT_STATUS.loading;

const isUsableConversationId = (value) =>
  typeof value === "number" && Number.isInteger(value) && value > 0;

const isRestorableMessageList = (messages) =>
  Array.isArray(messages) &&
  messages.every(
    (message) =>
      message !== null &&
      typeof message === "object" &&
      (message.role === BUILD_CHAT_MESSAGE_ROLE.user ||
        message.role === BUILD_CHAT_MESSAGE_ROLE.assistant) &&
      typeof message.content === "string" &&
      message.content.trim() !== ""
  );

const isBuildResponseForThisConversation = (state, token) =>
  token === undefined || token === state.buildToken;

const withConversationError = (state, kind, fallbackMessage, error) => ({
  ...state,
  conversation: {
    status: BUILD_CHAT_CONVERSATION_STATUS.error,
    error: {
      kind,
      message: error?.message || fallbackMessage,
    },
  },
});

export const startBuildChatConversationLoad = (state, buildToken) => ({
  ...state,
  buildToken: buildToken ?? state.buildToken,
  conversationId: null,
  conversation: {
    status: BUILD_CHAT_CONVERSATION_STATUS.loading,
    error: null,
  },
});

export const completeBuildChatConversationLoad = (
  state,
  conversationId,
  messages,
  buildToken
) => {
  if (!isBuildResponseForThisConversation(state, buildToken)) {
    return state;
  }

  if (!isUsableConversationId(conversationId) || !isRestorableMessageList(messages)) {
    return state;
  }

  return {
    ...state,
    conversationId,
    conversation: {
      status: BUILD_CHAT_CONVERSATION_STATUS.ready,
      error: null,
    },
    messages,
  };
};

export const failBuildChatConversationLoad = (state, error, buildToken) => {
  if (!isBuildResponseForThisConversation(state, buildToken)) {
    return state;
  }

  return withConversationError(
    state,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.load,
    "The saved conversation could not be loaded.",
    error
  );
};

export const completeBuildChatConversationSave = (
  state,
  conversationId,
  buildToken
) => {
  if (!isBuildResponseForThisConversation(state, buildToken)) {
    return state;
  }

  if (!isUsableConversationId(conversationId)) {
    return state;
  }

  return {
    ...state,
    conversationId,
    conversation: {
      status: BUILD_CHAT_CONVERSATION_STATUS.ready,
      error: null,
    },
  };
};

export const failBuildChatConversationSave = (state, error, buildToken) => {
  if (!isBuildResponseForThisConversation(state, buildToken)) {
    return state;
  }

  return withConversationError(
    state,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.save,
    "This exchange could not be saved.",
    error
  );
};

export const failBuildChatConversationReset = (state, error, buildToken) => {
  if (!isBuildResponseForThisConversation(state, buildToken)) {
    return state;
  }

  return withConversationError(
    state,
    BUILD_CHAT_CONVERSATION_ERROR_KIND.reset,
    "A new conversation could not be started.",
    error
  );
};

export const getLastBuildChatTurn = (state) => {
  const messages = state?.messages ?? [];

  if (messages.length < 2) {
    return null;
  }

  const answer = messages[messages.length - 1];
  const question = messages[messages.length - 2];

  if (
    question?.role !== BUILD_CHAT_MESSAGE_ROLE.user ||
    answer?.role !== BUILD_CHAT_MESSAGE_ROLE.assistant
  ) {
    return null;
  }

  return {
    question: question.content,
    answer: answer.content,
    evidence: answer.evidence ?? createEmptyBuildChatEvidence(),
    analysis: answer.analysis ?? createEmptyBuildChatAnalysis(),
  };
};

const createUserMessage = (content, index) => ({
  id: `build-chat-message-${index}`,
  role: BUILD_CHAT_MESSAGE_ROLE.user,
  content,
});

const createAssistantMessage = (content, evidence, analysis, index) => ({
  id: `build-chat-message-${index}`,
  role: BUILD_CHAT_MESSAGE_ROLE.assistant,
  content,
  evidence: normalizeBuildChatEvidence(evidence) ?? createEmptyBuildChatEvidence(),
  analysis: normalizeBuildChatAnalysis(analysis) ?? createEmptyBuildChatAnalysis(),
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

export const completeBuildChatRequest = (state, answer, token, evidence, analysis) => {
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
      createUserMessage(state.pendingQuestion, nextIndex),
      createAssistantMessage(answer, evidence, analysis, nextIndex + 1),
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
