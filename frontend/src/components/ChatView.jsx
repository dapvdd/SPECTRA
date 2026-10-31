import { useState } from "react";
import { MarkdownContent } from "./Markdown.jsx";
import { CHAT_ERROR_KIND, CHAT_STATUS } from "../hardwareChat.js";
import { getChatLoadingParts } from "../buildChat.js";

const CHAT_SUGGESTED_PROMPTS = [
  "Kuat buat GTA V?",
  "Cocok buat Figma?",
  "Buat coding project gede?",
  "Cocok buat Android Studio?",
];

const CHAT_ERROR_COPY = {
  [CHAT_ERROR_KIND.validation]:
    "The question could not be sent. Reword it and try again.",
  [CHAT_ERROR_KIND.provider]:
    "SPECTRA's AI provider could not answer right now.",
  [CHAT_ERROR_KIND.empty]:
    "SPECTRA returned an empty answer. Try again.",
  [CHAT_ERROR_KIND.request]:
    "The request could not be completed. Check the connection and try again.",
};

function HardwareChatTranscript({ chatState }) {
  if (!chatState.answeredQuestion) {
    return null;
  }

  return (
    <div className="hardware-chat-qna">
      <div className="hardware-chat-question">
        <span>You</span>
        <strong>{chatState.answeredQuestion}</strong>
      </div>
      <div className="hardware-chat-answer">
        <span className="hardware-chat-answer-label">SPECTRA</span>
        <MarkdownContent markdown={chatState.answer} />
      </div>
    </div>
  );
}

function AiChatSection({
  id,
  eyebrow = "ASK SPECTRA",
  title,
  intro,
  introId,
  loadingMessage,
  composerLabel,
  composerPlaceholder,
  submitLabel,
  prompts,
  promptsLabel = "Suggested questions",
  transcript,
  loadingDetail = "",
  promptsSecondary = false,
  onRetry,
  chatState,
  onAsk,
}) {
  const [draft, setDraft] = useState("");
  const loading = chatState.status === CHAT_STATUS.loading;
  const loadingParts = getChatLoadingParts(loadingMessage, loadingDetail);
  const resolvedIntroId = introId || `${id}-intro`;

  const submit = (question) => {
    const trimmed = (question ?? draft).trim();
    if (!trimmed || loading) {
      return;
    }

    setDraft("");
    onAsk(trimmed);
  };

  return (
    <section className="hardware-chat" aria-busy={loading} aria-labelledby={id}>
      <div className="hardware-chat-header">
        <div>
          <p className="detail-section-label">{eyebrow}</p>
          <h3 id={id}>{title}</h3>
        </div>
        <span className="hardware-chat-mark" aria-hidden="true">AI</span>
      </div>

      <p className="hardware-chat-intro" id={resolvedIntroId}>
        {intro}
      </p>

      {transcript}

      {loading && (
        <div className="hardware-chat-message" role="status">
          <span className="state-spinner" aria-hidden="true" />
          <span>
            {chatState.answeredQuestion
              ? "Asking a follow-up..."
              : loadingParts.label}
            {loadingParts.detail && <strong>{loadingParts.detail}</strong>}
          </span>
        </div>
      )}

      {chatState.status === CHAT_STATUS.error && (
        <div className="hardware-chat-error" role="alert">
          <strong>Could not get an answer.</strong>
          <span>
            {CHAT_ERROR_COPY[chatState.error?.kind] ??
              CHAT_ERROR_COPY[CHAT_ERROR_KIND.request]}
          </span>
          <button
            type="button"
            className="hardware-chat-retry"
            disabled={loading}
            onClick={() => {
              if (onRetry) {
                onRetry();
                return;
              }

              submit(chatState.lastQuestion);
            }}
          >
            Retry
          </button>
        </div>
      )}

      <div
        className={
          promptsSecondary
            ? "hardware-chat-prompts hardware-chat-prompts-secondary"
            : "hardware-chat-prompts"
        }
        aria-label={promptsLabel}
        role="group"
      >
        {prompts.map((prompt) => (
          <button
            type="button"
            className="hardware-chat-prompt"
            key={prompt}
            disabled={loading}
            onClick={() => submit(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>

      <form
        className="hardware-chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="sr-only" htmlFor={`${id}-composer`}>
          {composerLabel}
        </label>

        <input
          id={`${id}-composer`}
          type="text"
          aria-describedby={resolvedIntroId}
          autoComplete="off"
          enterKeyHint="send"
          placeholder={composerPlaceholder}
          value={draft}
          disabled={loading}
          onChange={(event) => setDraft(event.target.value)}
        />

        <button type="submit" disabled={loading}>
          {loading ? "Asking…" : submitLabel}
        </button>
      </form>
    </section>
  );
}

function HardwareChatSection({ chatState, onAsk }) {
  return (
    <AiChatSection
      id="hardware-chat-title"
      title="Ask your hardware anything"
      intro="Ask a natural-language question about this CPU. SPECTRA answers from verified specifications and benchmark data only."
      loadingMessage="Asking SPECTRA..."
      composerLabel="Ask about this CPU"
      composerPlaceholder="Ask about this CPU..."
      submitLabel="Ask"
      prompts={CHAT_SUGGESTED_PROMPTS}
      promptsLabel="Suggested questions for this CPU"
      transcript={<HardwareChatTranscript chatState={chatState} />}
      chatState={chatState}
      onAsk={onAsk}
    />
  );
}

export { AiChatSection, HardwareChatSection };
