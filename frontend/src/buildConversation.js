import { apiUrl } from "./api.js";
import {
  BUILD_CHAT_MESSAGE_ROLE,
  createEmptyBuildChatAnalysis,
  createEmptyBuildChatEvidence,
  normalizeBuildChatAnalysis,
  normalizeBuildChatEvidence,
} from "./buildChat.js";
import {
  CHAT_ERROR_KIND,
  getChatErrorKind,
  getChatErrorKindFromError,
} from "./hardwareChat.js";

export const BUILD_CONVERSATION_ENDPOINT_PATH = "/build/conversations";

const CONVERSATION_ENDPOINT = apiUrl(BUILD_CONVERSATION_ENDPOINT_PATH);

const conversationUrl = (suffix = "") =>
  `${CONVERSATION_ENDPOINT}${suffix}`;

const isUsableId = (value) =>
  typeof value === "number" && Number.isInteger(value) && value > 0;

const isNonEmptyString = (value) =>
  typeof value === "string" && value.trim() !== "";

const isRecord = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

export class BuildConversationError extends Error {
  constructor(message, kind, status) {
    super(message);
    this.name = "BuildConversationError";
    this.kind = kind;
    this.status = status;
  }
}

export const getBuildConversationErrorKindFromError = (error) =>
  error instanceof BuildConversationError
    ? error.kind
    : getChatErrorKindFromError(error);

const readJson = async (response, fallbackMessage) => {
  if (!response?.ok) {
    throw new BuildConversationError(
      `Build conversation request failed with status ${response?.status}`,
      getChatErrorKind(response?.status),
      response?.status
    );
  }

  try {
    return await response.json();
  } catch {
    throw new BuildConversationError(
      fallbackMessage,
      CHAT_ERROR_KIND.empty
    );
  }
};

const postJson = async (url, body, fallbackMessage, fetchImplementation) => {
  let response;

  try {
    response = await fetchImplementation(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch (networkError) {
    throw new BuildConversationError(
      networkError?.message || "The build conversation request could not be sent.",
      CHAT_ERROR_KIND.request
    );
  }

  return readJson(response, fallbackMessage);
};

const getJson = async (url, fallbackMessage, fetchImplementation) => {
  let response;

  try {
    response = await fetchImplementation(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
  } catch (networkError) {
    throw new BuildConversationError(
      networkError?.message || "The build conversation request could not be sent.",
      CHAT_ERROR_KIND.request
    );
  }

  return readJson(response, fallbackMessage);
};

const toEvidencePayload = (evidence) => ({
  known_facts: evidence?.knownFacts ?? [],
  interpretation: evidence?.interpretation ?? [],
  unknown: evidence?.unknown ?? [],
});

const toAnalysisPayload = (analysis) => ({
  strengths: analysis?.strengths ?? [],
  considerations: analysis?.considerations ?? [],
  data_gaps: analysis?.dataGaps ?? [],
});

export const buildBuildTurnPayload = (question, result) => {
  if (!isNonEmptyString(question) || !isNonEmptyString(result?.answer)) {
    throw new BuildConversationError(
      "A build turn needs both the question and the answer.",
      CHAT_ERROR_KIND.validation
    );
  }

  return {
    question: question.trim(),
    answer: result.answer.trim(),
    evidence: toEvidencePayload(
      normalizeBuildChatEvidence(result.evidence) ?? createEmptyBuildChatEvidence()
    ),
    analysis: toAnalysisPayload(
      normalizeBuildChatAnalysis(result.analysis) ?? createEmptyBuildChatAnalysis()
    ),
  };
};

export const normalizeBuildConversation = (payload) => {
  if (
    !isRecord(payload) ||
    !isUsableId(payload.id) ||
    !isUsableId(payload.cpu_hardware_id) ||
    !isUsableId(payload.gpu_hardware_id)
  ) {
    throw new BuildConversationError(
      "The build conversation response is not usable.",
      CHAT_ERROR_KIND.provider
    );
  }

  return {
    id: payload.id,
    cpuHardwareId: payload.cpu_hardware_id,
    gpuHardwareId: payload.gpu_hardware_id,
  };
};

const restoreAssistantMetadata = (payload, field, normalize, createEmpty) => {
  if (payload[field] === null || payload[field] === undefined) {
    return createEmpty();
  }

  const normalized = normalize(payload[field]);

  if (normalized === null) {
    throw new BuildConversationError(
      `A stored build message has unreadable ${field}.`,
      CHAT_ERROR_KIND.provider
    );
  }

  return normalized;
};

const restoreMessage = (payload) => {
  if (
    !isRecord(payload) ||
    !isUsableId(payload.id) ||
    !isUsableId(payload.conversation_id) ||
    !isNonEmptyString(payload.content) ||
    (payload.role !== BUILD_CHAT_MESSAGE_ROLE.user &&
      payload.role !== BUILD_CHAT_MESSAGE_ROLE.assistant)
  ) {
    throw new BuildConversationError(
      "The stored build conversation contains an unreadable message.",
      CHAT_ERROR_KIND.provider
    );
  }

  const message = {
    id: `build-chat-message-${payload.id}`,
    role: payload.role,
    content: payload.content,
  };

  if (payload.role !== BUILD_CHAT_MESSAGE_ROLE.assistant) {
    return message;
  }

  return {
    ...message,
    evidence: restoreAssistantMetadata(
      payload,
      "evidence",
      normalizeBuildChatEvidence,
      createEmptyBuildChatEvidence
    ),
    analysis: restoreAssistantMetadata(
      payload,
      "analysis",
      normalizeBuildChatAnalysis,
      createEmptyBuildChatAnalysis
    ),
  };
};

export const restoreBuildConversationMessages = (payload) => {
  if (!Array.isArray(payload)) {
    throw new BuildConversationError(
      "The stored build conversation is not a message list.",
      CHAT_ERROR_KIND.provider
    );
  }

  return payload.map(restoreMessage);
};

export const requestBuildConversation = async (
  cpuHardwareId,
  gpuHardwareId,
  fetchImplementation = fetch
) => {
  if (!isUsableId(cpuHardwareId) || !isUsableId(gpuHardwareId)) {
    throw new BuildConversationError(
      "A build conversation needs a CPU and a GPU id.",
      CHAT_ERROR_KIND.validation
    );
  }

  const payload = await postJson(
    conversationUrl(),
    { cpu_hardware_id: cpuHardwareId, gpu_hardware_id: gpuHardwareId },
    "The build conversation response could not be read.",
    fetchImplementation
  );

  const conversation = normalizeBuildConversation(payload);

  if (conversation.cpuHardwareId !== cpuHardwareId) {
    throw new BuildConversationError(
      "The build conversation does not match the requested CPU.",
      CHAT_ERROR_KIND.provider
    );
  }

  if (conversation.gpuHardwareId !== gpuHardwareId) {
    throw new BuildConversationError(
      "The build conversation does not match the requested GPU.",
      CHAT_ERROR_KIND.provider
    );
  }

  return conversation;
};

export const requestBuildConversationMessages = async (
  conversationId,
  fetchImplementation = fetch
) => {
  if (!isUsableId(conversationId)) {
    throw new BuildConversationError(
      "A stored build conversation needs a valid conversation id.",
      CHAT_ERROR_KIND.validation
    );
  }

  const payload = await getJson(
    conversationUrl(`/${conversationId}/messages`),
    "The stored build conversation could not be read.",
    fetchImplementation
  );

  return restoreBuildConversationMessages(payload);
};

export const ensureBuildConversation = async (
  conversationId,
  cpuHardwareId,
  gpuHardwareId,
  fetchImplementation = fetch
) => {
  if (isUsableId(conversationId)) {
    return conversationId;
  }

  const conversation = await requestBuildConversation(
    cpuHardwareId,
    gpuHardwareId,
    fetchImplementation
  );

  return conversation.id;
};

export const appendBuildConversationTurn = async (
  conversationId,
  turn,
  fetchImplementation = fetch
) => {
  if (!isUsableId(conversationId)) {
    throw new BuildConversationError(
      "A saved build turn needs a valid conversation id.",
      CHAT_ERROR_KIND.validation
    );
  }

  const payload = await postJson(
    conversationUrl(`/${conversationId}/turn`),
    turn,
    "The build turn could not be saved.",
    fetchImplementation
  );

  return restoreBuildConversationMessages([
    payload?.user_message,
    payload?.assistant_message,
  ]);
};

export const resetBuildConversationMessages = async (
  conversationId,
  fetchImplementation = fetch
) => {
  if (!isUsableId(conversationId)) {
    throw new BuildConversationError(
      "A new build conversation needs a valid conversation id.",
      CHAT_ERROR_KIND.validation
    );
  }

  const payload = await postJson(
    conversationUrl(`/${conversationId}/reset`),
    {},
    "The new build conversation could not be started.",
    fetchImplementation
  );

  return normalizeBuildConversation(payload);
};
