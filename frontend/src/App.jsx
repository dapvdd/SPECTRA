import { useEffect, useRef, useState } from "react";
import "./App.css";
import {
  getBenchmarkComparisonData,
  getPerformanceState,
  PERFORMANCE_METRICS,
} from "./performance.js";
import {
  calculateComparisonInsights,
  buildComparisonFacts,
} from "./comparison.js";
import {
  DECISION_STATUS,
  buildComparisonDecisionSummary,
  buildComparisonSpecRows,
} from "./comparisonDecision.js";
import {
  BUILD_INTELLIGENCE_STATUS,
  BUILD_LIST_SECTIONS,
  BUILD_SIGNAL_CATEGORY_LABELS,
  BUILD_SIGNAL_CATEGORY_ORDER,
  buildBuildIntelligence,
} from "./buildIntelligence.js";
import {
  AI_ANALYSIS_STATUS,
  requestComparisonExplanation,
} from "./comparisonExplanation.js";
import {
  getCpuDetailViewModel,
  getDetailBackLabel,
  getDetailComparisonAction,
} from "./detail.js";
import { parseMarkdown } from "./markdown.js";
import {
  THEME_PREFERENCES,
  applyThemeToDocument,
  createThemePreferenceState,
  getPrefersColorSchemeDark,
  normalizeThemePreference,
  readStoredThemePreference,
  selectThemePreference,
  writeStoredThemePreference,
} from "./theme.js";
import {
  buildSignalProfile,
  formatSignalCount,
  getSignalPrimaryLabel,
  getSignalStatusLabel,
} from "./signalProfile.js";
import {
  BUILD_CHAT_CONVERSATION_ERROR_KIND,
  BUILD_CHAT_CONVERSATION_STATUS,
  BUILD_CHAT_MESSAGE_ROLE,
  BUILD_CHAT_SUGGESTED_QUESTIONS,
  buildChatPayload,
  completeBuildChatConversationLoad,
  completeBuildChatConversationSave,
  completeBuildChatRequest,
  createBuildChatState,
  failBuildChatConversationLoad,
  failBuildChatConversationReset,
  failBuildChatConversationSave,
  failBuildChatRequest,
  getBuildChatToken,
  getBuildChatAnalysisSections,
  getBuildChatConversationError,
  getBuildChatEvidenceSections,
  getChatLoadingParts,
  getLastBuildChatTurn,
  isBuildChatBusy,
  isBuildChatRestoringConversation,
  isSameBuildChatToken,
  requestBuildChatAnswer,
  resetBuildChatConversation,
  startBuildChatConversationLoad,
  startBuildChatRequest,
} from "./buildChat.js";
import {
  appendBuildConversationTurn,
  buildBuildTurnPayload,
  ensureBuildConversation,
  requestBuildConversation,
  requestBuildConversationMessages,
  resetBuildConversationMessages,
} from "./buildConversation.js";
import {
  HARDWARE_TYPES,
  MANUFACTURER_FILTERS,
  createCatalogLoadGuard,
  getCatalogFilterState,
  getCatalogResultSummary,
  requestHardwareCatalog,
} from "./catalog.js";
import {
  getGpuDetailViewModel,
  getHardwareCardPrimarySpecs,
} from "./hardwareCard.js";
import {
  createDetailRequestGuard,
  requestHardwareDetail,
} from "./detailRequest.js";
import {
  completeComparisonDetailRequest,
  createComparisonDetailState,
  failComparisonDetailRequest,
  getComparisonDetailsInSelectionOrder,
  removeComparisonDetail,
  startComparisonDetailRequest,
} from "./comparisonDetails.js";
import {
  assertSuccessfulResponse,
  validateBenchmarkPayload,
  validateComparisonDetailPayload,
  validateHardwareDetailPayload,
} from "./apiValidation.js";
import { apiUrl } from "./api.js";
import {
  CHAT_ERROR_KIND,
  CHAT_STATUS,
  buildHardwareChatContext,
  completeHardwareChatRequest,
  createChatRequestGuard,
  createHardwareChatState,
  failHardwareChatRequest,
  requestHardwareChatAnswer,
  startHardwareChatRequest,
} from "./hardwareChat.js";
import {
  BUILD_DETAIL_STATUS,
  BUILD_RESOLUTIONS,
  BUILD_USE_CASES,
  calculateListedTdpSum,
  clearBuildCpu,
  clearBuildGpu,
  clearBuildSlotDetail,
  completeBuildDetailRequest,
  createBuildConfig,
  createBuildDetailState,
  createBuildUserContext,
  failBuildDetailRequest,
  getBuildChatSnapshot,
  getBuildChatContextSummary,
  getBuildComponentAction,
  getBuildComponentSpecs,
  getBuildComponentSummary,
  getBuildFacts,
  getBuildSelection,
  getBuildSlotDetail,
  getBuildSlotChecklistItem,
  getBuildSlotRequestState,
  getBuildSummary,
  isBuildChatContextReady,
  setBuildCpu,
  setBuildGpu,
  setBuildResolution,
  setBuildUseCase,
  startBuildDetailRequest,
} from "./buildConfig.js";
import {
  addComparisonSelection,
  clearComparisonSelection,
  completeDetailNavigation,
  createDetailNavigationState,
  failDetailNavigation,
  getComparisonSelectionSummary,
  getComparisonTypeConflict,
  removeBenchmarkState,
  removeComparisonSelection,
  returnToCatalogState,
  setBenchmarkError,
  setBenchmarkLoading,
  setBenchmarkSuccess,
  startDetailNavigation,
} from "./appState.js";

const formatBenchmarkScore = (score) =>
  Number.isInteger(score) ? score.toLocaleString() : score.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const getScrollBehavior = () => (prefersReducedMotion() ? "auto" : "smooth");

const scrollToSection = (id, block = "start") => {
  window.setTimeout(() => {
    document.getElementById(id)?.scrollIntoView({
      behavior: getScrollBehavior(),
      block,
    });
  }, 0);
};

const prefersColorSchemeDark = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-color-scheme: dark)").matches;

const THEME_OPTION_COPY = {
  system: { glyph: "◐", label: "System" },
  dark: { glyph: "◑", label: "Dark" },
  light: { glyph: "○", label: "Light" },
};

/* Theme is a tri-state preference, so the control is a segmented group of
   toggle buttons rather than a single switch. `aria-pressed` carries state
   and the visible glyph carries it independently of colour. */
function ThemeControl({ preference, onSelect }) {
  return (
    <div
      className="theme-switch"
      role="group"
      aria-label="Colour theme"
    >
      {THEME_PREFERENCES.map((option) => {
        const copy = THEME_OPTION_COPY[option];
        const isActive = preference === option;

        return (
          <button
            type="button"
            className="theme-switch-option"
            key={option}
            aria-pressed={isActive}
            aria-label={`${copy.label} theme`}
            title={`${copy.label} theme`}
            onClick={() => onSelect(option)}
          >
            <span className="theme-switch-glyph" aria-hidden="true">
              {copy.glyph}
            </span>
            <span className="theme-switch-label">{copy.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/* SPECTRA SIGNAL
   The hero's right half. Reads real composition out of the catalog payload the
   app has already loaded - nothing is estimated, and no benchmark figure is
   involved. The trace beneath it is decorative identity, which is why it is
   aria-hidden and never described as a measurement. */
function SignalReadout({ profile, loading, error }) {
  const status = getSignalStatusLabel(profile, { loading, error });
  const isLoaded = !profile.isEmpty && !loading && !error;

  return (
    <aside
      className="signal"
      aria-labelledby="signal-title"
      data-loaded={isLoaded ? "true" : "false"}
    >
      <div className="signal-head">
        <p className="spectra-label">{getSignalPrimaryLabel(profile)}</p>
        <p className="section-head-status" role="status">
          {status}
        </p>
      </div>

      <h2 id="signal-title" className="sr-only">
        Catalog composition
      </h2>

      <p className="signal-total">
        <span className="signal-value">
          {formatSignalCount(profile.total)}
        </span>
        <span className="signal-total-label">
          records
          <br />
          indexed
        </span>
      </p>

      <dl className="signal-channels">
        {profile.channels.map((channel) => (
          <div className="signal-channel" key={channel.label}>
            <dt>{channel.label}</dt>
            <dd>
              {formatSignalCount(channel.value)}
              <span className="signal-channel-share">
                {` ${Math.round(channel.share)}%`}
              </span>
            </dd>
            <div className="signal-channel-meter">
              <div
                className="meter"
                role="presentation"
              >
                <span
                  className="meter-fill"
                  style={{ width: `${channel.share}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </dl>

      {profile.manufacturers.length > 0 && (
        <ul className="signal-manufacturers">
          {profile.manufacturers.map((manufacturer) => (
            <li key={manufacturer.label}>
              {manufacturer.label}
              <strong>{formatSignalCount(manufacturer.value)}</strong>
            </li>
          ))}
        </ul>
      )}

      <div className="signal-foot">
        <p className="spectra-label">Share of catalog</p>
        <span className="spectra-ref">S-00</span>
      </div>

      <span
        className="spectra-spectrum spectra-spectrum-tall"
        aria-hidden="true"
      />
    </aside>
  );
}

/* Slot letters for the A vs B pair in comparison. Two slots is a product
   constraint, not a coincidence, so the letters are fixed rather than derived. */
const COMPARISON_SLOT_LETTERS = ["A", "B"];
const PERFORMANCE_STATUS_LABELS = {
  available: "DATA AVAILABLE",
  partial: "PARTIAL DATA",
  unavailable: "NOT AVAILABLE",
  loading: "LOADING",
  error: "UNAVAILABLE",
};

function PerformanceSection({
  benchmarkState,
  hardwareType = "CPU",
  titleId,
}) {
  const performanceState = getPerformanceState(benchmarkState);
  const isLoading = performanceState.status === "loading";

  return (
    <section
      className="performance-section"
      aria-busy={isLoading}
      aria-labelledby={titleId}
    >
      <p className="detail-section-label">PERFORMANCE</p>

      <div className="performance-intro">
        <div>
          <h3 id={titleId}>Performance signals, when verified</h3>

          <p>
            Benchmark scores are shown only when returned by a verified data
            source. No score is estimated or substituted here.
          </p>
        </div>

        <span
          className={`performance-status performance-status-${performanceState.status}`}
        >
          {PERFORMANCE_STATUS_LABELS[performanceState.status]}
        </span>
      </div>

      {performanceState.status === "unavailable" && (
        <div className="performance-notice">
          <strong>Benchmark data is not available yet.</strong>
          <span>
            {hardwareType === "GPU"
              ? "No verified GPU benchmark result has been returned for this GPU."
              : "No supported Geekbench 7 result has been returned for this CPU."}
          </span>
        </div>
      )}

      {performanceState.status === "partial" && (
        <div className="performance-notice">
          <strong>Some benchmark data is unavailable.</strong>
          <span>
            Available results are shown below; missing metrics remain clearly
            marked until verified data is returned.
          </span>
        </div>
      )}

      {performanceState.status === "loading" && (
        <div className="performance-notice performance-notice-loading">
          <strong>Loading performance data</strong>
          <span>Waiting for the benchmark data source to respond.</span>
        </div>
      )}

      {performanceState.status === "error" && (
        <div className="performance-notice performance-notice-error">
          <strong>Performance data could not be loaded.</strong>
          <span>{performanceState.message}</span>
        </div>
      )}

      <div className="performance-grid">
        {PERFORMANCE_METRICS.map((metric, index) => {
          const result = performanceState.results[metric.key];
          const sourceName = result?.source?.name || result?.source_name;

          return (
            <article
              className={`performance-card ${
                result ? "performance-card-available" : ""
              }`}
              key={metric.key}
            >
              <div className="performance-card-header">
                <div>
                  <span className="performance-card-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3>{metric.title}</h3>
                </div>

                <span
                  className={`performance-badge ${
                    result ? "performance-badge-available" : ""
                  }`}
                >
                  {result ? "AVAILABLE" : "NO DATA"}
                </span>
              </div>

              {result ? (
                <div className="performance-result">
                  <div className="performance-value">
                    <strong>{formatBenchmarkScore(result.score)}</strong>
                    <span>{result.unit}</span>
                  </div>

                  <p>{metric.description}</p>

                  {(result.benchmark_name || sourceName || result.recorded_at) && (
                    <small>
                      <span>{result.benchmark_name || "Benchmark result"}</span>
                      {sourceName && <span>Source: {sourceName}</span>}
                    </small>
                  )}
                </div>
              ) : (
                <div className="performance-result performance-result-unavailable">
                  <div className="performance-value">
                    <strong>--</strong>
                    <span>score</span>
                  </div>

                  <p>{metric.description}</p>

                  <small>
                    No verified result has been returned for this metric.
                  </small>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}


const DECISION_COMPLETENESS_CLASS = {
  complete: "performance-status-available",
  partial: "performance-status-partial",
  unavailable: "performance-status-error",
  loading: "performance-status-loading",
};

function ComparisonDecisionSupport({ summary }) {
  if (summary.status === DECISION_STATUS.empty) {
    return null;
  }

  const { availability, benchmarkSupport, lead, overview } = summary;
  const isLoading = summary.status === DECISION_STATUS.loading;

  return (
    <section
      className="comparison-decision"
      aria-labelledby="decision-support-title"
      aria-busy={isLoading}
    >
      <div className="comparison-decision-header">
        <div>
          <p className="detail-section-label">DECISION SUPPORT</p>
          <h3 id="decision-support-title">What this comparison covers</h3>
          <p className="comparison-decision-subhead">{overview.headline}</p>
        </div>

        <span
          className={`performance-status ${
            DECISION_COMPLETENESS_CLASS[availability.completeness]
          }`}
        >
          {availability.statusLabel}
        </span>
      </div>

      <div className="comparison-overview">
        {overview.participants.map((participant, index) => (
          <div className="comparison-overview-side" key={participant.side}>
            <span className="comparison-overview-slot">
              {overview.noun} {String(index + 1).padStart(2, "0")}
            </span>
            <strong>{participant.name}</strong>
            <span className="comparison-overview-meta">
              {participant.manufacturer} · {participant.type}
            </span>
          </div>
        ))}
      </div>

      <dl className="decision-facts">
        <div className="decision-fact">
          <dt>Measurable metrics</dt>
          <dd>
            {summary.measurableCount} of {availability.totalCount}
          </dd>
        </div>

        <div className="decision-fact">
          <dt>Tied metrics</dt>
          <dd>{summary.tieCount}</dd>
        </div>

        <div className="decision-fact">
          <dt>Unavailable metrics</dt>
          <dd>{summary.unavailableCount}</dd>
        </div>

        <div className="decision-fact">
          <dt>Benchmark support</dt>
          <dd>{benchmarkSupport.label}</dd>
        </div>
      </dl>

      <div className="comparison-decision-block">
        <h4>Where each side leads</h4>

        {isLoading ? (
          <p className="comparison-decision-note" role="status">
            <span className="state-spinner" aria-hidden="true" />
            Waiting for verified benchmark data before any lead is reported.
          </p>
        ) : summary.canCompare ? (
          <>
            {summary.leadLines.map((line, index) => (
              <p className="comparison-decision-note" key={`${index}-${line}`}>
                {line}
              </p>
            ))}

            <ul className="decision-lead-list">
              {lead.groups.map((group) => (
                <li className="decision-lead-group" key={group.winner}>
                  <div className="decision-lead-heading">
                    <strong>{group.winnerName}</strong>
                    <span>
                      leads {group.count} of {summary.measurableCount} measurable
                      metrics
                    </span>
                  </div>

                  <ul className="decision-lead-metrics">
                    {group.metrics.map((metric) => (
                      <li key={metric.key}>
                        <span>{metric.label}</span>
                        <span>{metric.differenceLabel}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="comparison-decision-note">
            No verified value is available on both sides yet, so no lead can be
            reported for this comparison.
          </p>
        )}
      </div>

      {lead.tieCount > 0 && (
        <div className="comparison-decision-block">
          <h4>Tied metrics</h4>

          <ul className="decision-tie-list">
            {lead.ties.map((tie) => (
              <li key={tie.key}>
                <span>{tie.label}</span>
                <span>tie at {tie.valueLabel}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="comparison-decision-block">
        <h4>Data availability</h4>

        <ul className="decision-limitation-list">
          {summary.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function BenchmarkComparison({ comparisonData, compareDetails }) {
  if (comparisonData.status === "loading") {
    return (
      <section className="benchmark-comparison" aria-labelledby="benchmark-comparison-title">
        <div className="benchmark-comparison-header">
          <div>
            <p className="detail-section-label">BENCHMARK COMPARISON</p>
            <h3 id="benchmark-comparison-title">Geekbench 7 scores</h3>
          </div>
          <span className="performance-status performance-status-loading">LOADING</span>
        </div>
        <div className="benchmark-comparison-notice" role="status">
          <span className="state-spinner" aria-hidden="true" />
          Waiting for verified benchmark data.
        </div>
      </section>
    );
  }

  const hasAvailableScore = comparisonData.metrics.some((metric) =>
    metric.rows.some((row) => row.value != null)
  );

  return (
    <section className="benchmark-comparison" aria-labelledby="benchmark-comparison-title">
      <div className="benchmark-comparison-header">
        <div>
          <p className="detail-section-label">BENCHMARK COMPARISON</p>
          <h3 id="benchmark-comparison-title">Geekbench 7 scores</h3>
        </div>
        <span className="performance-status">
          {hasAvailableScore ? "VERIFIED DATA" : "NO DATA"}
        </span>
      </div>

      {!hasAvailableScore ? (
        <p className="benchmark-comparison-notice">
          Benchmark data unavailable.
        </p>
      ) : (
        <div className="benchmark-comparison-grid">
          {comparisonData.metrics.map((metric) => (
            <article className="benchmark-comparison-card" key={metric.key}>
              <div className="benchmark-comparison-card-heading">
                <h4>{metric.title}</h4>
                {metric.winner === "tie" && (
                  <span className="benchmark-comparison-result">TIE</span>
                )}
                {metric.winner && metric.winner !== "tie" && (
                  <span className="benchmark-comparison-result">
                    {metric.winner === "cpuA" ? compareDetails[0].name : compareDetails[1].name} leads
                  </span>
                )}
              </div>

              <div className="benchmark-bars">
                {metric.rows.map((row, index) => {
                  const cpu = compareDetails[index];
                  const isWinner = metric.winner === row.cpu;

                  return (
                    <div className="benchmark-bar-row" key={row.cpu}>
                      <div className="benchmark-bar-label">
                        <span title={cpu.name}>{cpu.name}</span>
                        {row.value != null ? (
                          <strong>{formatBenchmarkScore(row.value)} points</strong>
                        ) : (
                          <strong className="benchmark-bar-unavailable">No data</strong>
                        )}
                      </div>
                      <div className="benchmark-bar-track" aria-hidden="true">
                        {row.width != null && (
                          <span
                            className={`benchmark-bar-fill ${isWinner ? "benchmark-bar-fill-winner" : ""}`}
                            style={{ width: `${row.width}%` }}
                          />
                        )}
                      </div>
                      {isWinner && <span className="sr-only">Higher score</span>}
                    </div>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function DetailSpecGrid({ items }) {
  return (
    <div className="spec-grid">
      {items.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

function CpuDetailView({
  hardware,
  benchmarkState,
  compareList,
  buildAction,
  onBack,
  onCompare,
  onAddToBuild,
  detailError,
  chatState,
  onAskQuestion,
}) {
  const viewModel = getCpuDetailViewModel(hardware);
  const comparisonAction = getDetailComparisonAction(compareList, hardware.id);
  const backLabel = getDetailBackLabel("CPU");

  return (
    <section className="hardware-detail" aria-labelledby="cpu-detail-title">
      <button
        type="button"
        className="back-button"
        onClick={onBack}
        aria-label={`${backLabel} and close this detail view`}
      >
        <span aria-hidden="true">←</span> {backLabel}
      </button>

      {detailError && (
        <div className="detail-state detail-state-error" role="alert">
          <strong>CPU details unavailable</strong>
          <span>{detailError}</span>
        </div>
      )}

      <div className="hardware-detail-header">
        <div>
          <p className="eyebrow detail-type">CPU DETAIL</p>
          <h2 id="cpu-detail-title" tabIndex={-1}>
            {viewModel.name}
          </h2>
          <p className="hardware-meta">
            <span className="manufacturer-mark" aria-hidden="true">
              {viewModel.manufacturer.slice(0, 1)}
            </span>
            {viewModel.manufacturer} · {viewModel.type}
          </p>
        </div>

        <div className="detail-header-actions">
          <button
            type="button"
            className={`detail-compare-button ${
              comparisonAction.alreadySelected ? "added" : ""
            }`}
            onClick={onCompare}
            disabled={comparisonAction.comparisonFull}
            aria-pressed={comparisonAction.alreadySelected}
          >
            {comparisonAction.alreadySelected
              ? `✓ CPU ${comparisonAction.comparisonSlot} selected`
              : comparisonAction.comparisonFull
                ? "Comparison Full"
                : "Compare CPU"}
          </button>

          <button
            type="button"
            className={`detail-build-button ${
              buildAction.alreadySelected ? "added" : ""
            }`}
            onClick={onAddToBuild}
            aria-pressed={buildAction.alreadySelected}
          >
            {buildAction.actionLabel}
          </button>
        </div>
      </div>

      <div className="detail-specifications">
        <p className="detail-section-label">OVERVIEW</p>
        <DetailSpecGrid items={viewModel.overview} />

        <p className="detail-section-label technical-label">
          KEY SPECIFICATIONS
        </p>
        <DetailSpecGrid items={viewModel.keySpecifications} />

        <p className="detail-section-label technical-label">
          TECHNICAL SPECIFICATIONS
        </p>
        <DetailSpecGrid items={viewModel.technicalSpecifications} />
      </div>

      <PerformanceSection
        benchmarkState={benchmarkState}
        titleId="cpu-performance-title"
      />

      <HardwareChatSection chatState={chatState} onAsk={onAskQuestion} />
    </section>
  );
}

function GpuDetailSection({ label, items }) {
  return (
    <section className="gpu-detail-section">
      <p className="detail-section-label">{label}</p>
      <DetailSpecGrid items={items} />
    </section>
  );
}

function GpuHardwareDetail({ hardware, buildAction, onBack, onAddToBuild }) {
  const viewModel = getGpuDetailViewModel(hardware);
  const backLabel = getDetailBackLabel("GPU");

  return (
    <section className="hardware-detail gpu-detail" aria-labelledby="gpu-detail-title">
      <button
        type="button"
        className="back-button"
        onClick={onBack}
        aria-label={`${backLabel} and close this detail view`}
      >
        <span aria-hidden="true">←</span> {backLabel}
      </button>

      <div className="hardware-detail-header">
        <div>
          <p className="eyebrow detail-type">GPU DETAIL</p>
          <h2 id="gpu-detail-title" tabIndex={-1}>
            {viewModel.name}
          </h2>
          <p className="hardware-meta">
            <span className="manufacturer-mark" aria-hidden="true">
              {viewModel.manufacturer.slice(0, 1)}
            </span>
            {viewModel.manufacturer} · {viewModel.type}
          </p>
        </div>

        <div className="detail-header-actions">
          <button
            type="button"
            className={`detail-build-button ${
              buildAction.alreadySelected ? "added" : ""
            }`}
            onClick={onAddToBuild}
            aria-pressed={buildAction.alreadySelected}
          >
            {buildAction.actionLabel}
          </button>
        </div>
      </div>

      <div className="gpu-detail-sections">
        <GpuDetailSection label="OVERVIEW" items={viewModel.overview} />
        <GpuDetailSection label="MEMORY" items={viewModel.memory} />
        <GpuDetailSection label="CLOCK SPEEDS" items={viewModel.clocks} />
        <GpuDetailSection
          label="POWER & PHYSICAL"
          items={viewModel.powerPhysical}
        />
        <GpuDetailSection label="INTERFACE" items={viewModel.interface} />
      </div>
    </section>
  );
}

const formatInsightValue = (value, format, unit) => {
  const formattedValue =
    format === "integer"
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

  return unit ? `${formattedValue} ${unit}` : formattedValue;
};

function ComparisonInsights({ insights, compareDetails }) {
  if (insights.pendingMetrics.length > 0) {
    return (
      <section className="comparison-insights" aria-labelledby="insights-title">
        <div className="comparison-insights-header">
          <div>
            <p className="detail-section-label">COMPARISON INSIGHTS</p>
            <h3 id="insights-title">Waiting for comparable data</h3>
          </div>
          <span className="comparison-insights-mark" aria-hidden="true">?</span>
        </div>
        <p className="comparison-insights-message">
          Verified benchmark data is still loading. Insights will appear when
          both CPUs have finished loading their supported metrics.
        </p>
      </section>
    );
  }

  if (insights.measurableCount === 0) {
    return (
      <section className="comparison-insights" aria-labelledby="insights-title">
        <div className="comparison-insights-header">
          <div>
            <p className="detail-section-label">COMPARISON INSIGHTS</p>
            <h3 id="insights-title">No measurable lead yet</h3>
          </div>
          <span className="comparison-insights-mark" aria-hidden="true">—</span>
        </div>
        <p className="comparison-insights-message">
          Not enough comparable data to generate insights.
        </p>
      </section>
    );
  }

  const [cpuA, cpuB] = compareDetails;
  const unavailableLabel =
    insights.unavailableMetrics.length === 1
      ? "1 metric could not be compared because data is unavailable."
      : `${insights.unavailableMetrics.length} metrics could not be compared because data is unavailable.`;

  return (
    <section className="comparison-insights" aria-labelledby="insights-title">
      <div className="comparison-insights-header">
        <div>
          <p className="detail-section-label">COMPARISON INSIGHTS</p>
          <h3 id="insights-title">Why the numbers differ</h3>
        </div>
        <span className="comparison-insights-mark" aria-hidden="true">+</span>
      </div>

      <div className="comparison-insights-summary">
        {insights.wins.cpuA > 0 && (
          <p>
            <strong>{cpuA.name}</strong> leads in {insights.wins.cpuA} of{" "}
            {insights.measurableCount} measurable metrics.
          </p>
        )}
        {insights.wins.cpuB > 0 && (
          <p>
            <strong>{cpuB.name}</strong> leads in {insights.wins.cpuB} of{" "}
            {insights.measurableCount} measurable metrics.
          </p>
        )}
        {insights.wins.cpuA === 0 && insights.wins.cpuB === 0 && (
          <p>All {insights.measurableCount} measurable metrics are tied.</p>
        )}
      </div>

      {insights.insights.length > 0 && (
        <ul className="comparison-insight-list">
          {insights.insights.map((insight) => (
            <li className="comparison-insight-item" key={insight.metricKey}>
              <span className="comparison-insight-icon" aria-hidden="true">+</span>
              <div>
                <strong>{insight.metric}</strong>
                <span>{insight.winnerName}</span>
              </div>
              <span className="comparison-insight-difference">
                {insight.direction === "lower" ? "" : "+"}
                {insight.differencePercent.toFixed(1)}%{" "}
                {insight.direction === "lower" ? "lower" : "higher"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {insights.tieDetails.length > 0 && (
        <div className="comparison-insight-ties">
          <strong>Ties</strong>
          {insights.tieDetails.map((tie) => (
            <span key={tie.metricKey}>
              {tie.metric} — Tie at {formatInsightValue(tie.value, tie.format, tie.unit)}
            </span>
          ))}
        </div>
      )}

      {insights.unavailableMetrics.length > 0 && (
        <p className="comparison-insights-unavailable">{unavailableLabel}</p>
      )}
    </section>
  );
}

function AiAnalysis({ analysis, onGenerate }) {
  const isLoading = analysis.status === AI_ANALYSIS_STATUS.loading;

  return (
    <section className="ai-analysis" aria-labelledby="ai-analysis-title">
      <div className="ai-analysis-header">
        <div>
          <p className="detail-section-label">AI ANALYSIS</p>
          <h3 id="ai-analysis-title">A concise explanation of the comparison</h3>
        </div>
        <span className="ai-analysis-mark" aria-hidden="true">AI</span>
      </div>

      {analysis.status === AI_ANALYSIS_STATUS.idle && (
        <div className="ai-analysis-empty">
          <p>
            SPECTRA can summarise this comparison in plain language, using only
            the verified values shown above.
          </p>
          <button type="button" className="ai-analysis-button" onClick={onGenerate}>
            Generate Analysis
          </button>
        </div>
      )}

      {isLoading && (
        <div className="ai-analysis-message" role="status">
          <span className="state-spinner" aria-hidden="true" />
          <span>Analyzing comparison...</span>
        </div>
      )}

      {analysis.status === AI_ANALYSIS_STATUS.success && (
        <div className="ai-analysis-result">
          <MarkdownContent markdown={analysis.explanation} headingOffset={2} />
          <button
            type="button"
            className="ai-analysis-button"
            onClick={onGenerate}
          >
            Regenerate Analysis
          </button>
        </div>
      )}

      {analysis.status === AI_ANALYSIS_STATUS.error && (
        <div className="ai-analysis-error" role="alert">
          <p>Unable to generate analysis.</p>
          <p className="ai-analysis-error-hint">
            The comparison itself is unaffected. Try again in a moment.
          </p>
          <button type="button" className="ai-analysis-button" onClick={onGenerate}>
            Try Again
          </button>
        </div>
      )}
    </section>
  );
}

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

function MarkdownContent({ markdown, headingOffset = 0, className = "" }) {
  const blockClassName = className
    ? `markdown-content ${className}`
    : "markdown-content";

  return (
    <div className={blockClassName}>
      {parseMarkdown(markdown).map((block, blockIndex) => {
        const renderInline = (parts) =>
          parts.map((part, partIndex) =>
            part.type === "bold" ? (
              <strong key={`${blockIndex}-${partIndex}`}>{part.value}</strong>
            ) : (
              <span key={`${blockIndex}-${partIndex}`}>{part.value}</span>
            ),
          );

        if (block.type === "heading") {
          const Heading = `h${Math.min(6, Math.max(1, block.level + headingOffset))}`;
          return (
            <Heading key={blockIndex}>
              {renderInline(block.children)}
            </Heading>
          );
        }

        if (block.type === "list") {
          return (
            <ul key={blockIndex}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }

        return <p key={blockIndex}>{renderInline(block.children)}</p>;
      })}
    </div>
  );
}

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

function BuildChatEvidence({ evidence }) {
  const sections = getBuildChatEvidenceSections(evidence).filter(
    (section) => section.items.length > 0
  );

  if (sections.length === 0) {
    return null;
  }

  return (
    <div className="build-chat-evidence">
      {sections.map((section) => (
        <section className="build-chat-evidence-section" key={section.key}>
          <h4 className="build-chat-evidence-label">{section.label}</h4>
          <ul className="build-chat-evidence-list">
            {section.items.map((item, index) => (
              <li
                className="build-chat-evidence-item"
                key={`${section.key}-${index}`}
              >
                {item}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function BuildChatAnalysis({ analysis }) {
  const sections = getBuildChatAnalysisSections(analysis).filter(
    (section) => section.items.length > 0
  );

  if (sections.length === 0) {
    return null;
  }

  return (
    <div className="build-chat-analysis">
      <h4 className="build-chat-analysis-title">Build analysis</h4>
      {sections.map((section) => (
        <section className="build-chat-analysis-section" key={section.key}>
          <h5 className="build-chat-analysis-label">{section.label}</h5>
          <ul className="build-chat-analysis-list">
            {section.items.map((item, index) => (
              <li
                className="build-chat-analysis-item"
                key={`${section.key}-${index}`}
              >
                {item}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function BuildChatTranscript({ messages }) {
  const endOfTranscriptRef = useRef(null);
  const messageCount = messages.length;

  useEffect(() => {
    endOfTranscriptRef.current?.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  }, [messageCount]);

  if (messageCount === 0) {
    return null;
  }

  return (
    <>
      <ol
        className="build-chat-transcript"
        aria-label="Build conversation"
        aria-live="polite"
        role="log"
      >
        {messages.map((message) =>
          message.role === BUILD_CHAT_MESSAGE_ROLE.user ? (
            <li className="build-chat-message build-chat-message-user" key={message.id}>
              <span className="build-chat-message-label">You</span>
              <span className="build-chat-message-text">{message.content}</span>
            </li>
          ) : (
            <li
              className="build-chat-message build-chat-message-assistant"
              key={message.id}
            >
              <span className="build-chat-message-label">SPECTRA</span>
              <div className="build-chat-message-text">
                <MarkdownContent markdown={message.content} headingOffset={2} />
              </div>
              <BuildChatEvidence evidence={message.evidence} />
              <BuildChatAnalysis analysis={message.analysis} />
            </li>
          )
        )}
      </ol>
      <div
        aria-hidden="true"
        className="build-chat-transcript-end"
        ref={endOfTranscriptRef}
      />
    </>
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

const BUILD_CONVERSATION_ERROR_COPY = {
  [BUILD_CHAT_CONVERSATION_ERROR_KIND.load]: {
    title: "Saved conversation unavailable",
    message:
      "The stored conversation for this build could not be loaded, so no previous messages are shown. You can retry or ask a new question.",
  },
  [BUILD_CHAT_CONVERSATION_ERROR_KIND.save]: {
    title: "Answer not saved",
    message:
      "This exchange is shown here but was not stored, so it may be missing after a reload.",
  },
  [BUILD_CHAT_CONVERSATION_ERROR_KIND.reset]: {
    title: "New conversation not started",
    message:
      "The previous messages are still stored for this build and may reappear after a reload.",
  },
};

function BuildConversationNotice({ conversation, onRetry }) {
  if (isBuildChatRestoringConversation({ conversation })) {
    return (
      <p className="build-conversation-status" role="status">
        <span className="state-spinner" aria-hidden="true" />
        Loading the saved conversation for this build...
      </p>
    );
  }

  if (conversation?.status !== BUILD_CHAT_CONVERSATION_STATUS.error) {
    return null;
  }

  const copy =
    BUILD_CONVERSATION_ERROR_COPY[conversation.error?.kind] ??
    BUILD_CONVERSATION_ERROR_COPY[BUILD_CHAT_CONVERSATION_ERROR_KIND.load];

  return (
    <div className="build-conversation-notice" role="alert">
      <strong>{copy.title}</strong>
      <span>{conversation.error?.message || copy.message}</span>
      <button
        type="button"
        className="build-conversation-retry"
        onClick={onRetry}
      >
        Retry
      </button>
    </div>
  );
}

function BuildChatSection({
  contextSummary,
  chatState,
  onAsk,
  onRetry,
  onReset,
  onRetryConversation,
}) {
  const started = chatState.messages.length > 0;
  const finished = started || chatState.status !== CHAT_STATUS.idle;

  return (
    <div className="build-chat">
      <div className="build-chat-context">
        <span className="build-chat-context-label">CURRENT BUILD</span>
        <strong>{contextSummary.cpuName}</strong>
        <span className="build-chat-context-join" aria-hidden="true">
          +
        </span>
        <strong>{contextSummary.gpuName}</strong>
        <span className="build-chat-context-values">
          {contextSummary.contextLabel}
        </span>
        {finished && (
          <button
            type="button"
            className="build-chat-reset"
            onClick={onReset}
          >
            New conversation
          </button>
        )}
      </div>

      <BuildConversationNotice
        conversation={chatState.conversation}
        onRetry={onRetryConversation}
      />

      <AiChatSection
        id="build-chat-title"
        eyebrow="ASK ABOUT THIS BUILD"
        title="Ask SPECTRA about this build"
        intro="Ask a question about the selected CPU and GPU together. SPECTRA answers only from the stored specifications and benchmark records in this build context."
        loadingMessage="Asking SPECTRA about this build..."
        loadingDetail={chatState.pendingQuestion}
        composerLabel="Ask about this build"
        composerPlaceholder="Ask a follow-up..."
        submitLabel="Ask SPECTRA"
        prompts={BUILD_CHAT_SUGGESTED_QUESTIONS}
        promptsLabel="Suggested questions about this build"
        promptsSecondary={started}
        transcript={<BuildChatTranscript messages={chatState.messages} />}
        chatState={chatState}
        onAsk={onAsk}
        onRetry={onRetry}
      />
    </div>
  );
}

function BuildComponentCard({
  type,
  selection,
  detail,
  requestState,
  onChange,
  onClear,
  onRetry,
}) {
  const summary = getBuildComponentSummary(detail || selection);
  const specs = getBuildComponentSpecs(detail);
  const busy = requestState.status === BUILD_DETAIL_STATUS.loading;
  const errored = requestState.status === BUILD_DETAIL_STATUS.error;

  return (
    <section className="build-component-card" aria-labelledby={`build-slot-${type}`}>
      <p className="detail-section-label" id={`build-slot-${type}`}>
        {type}
      </p>

      {!selection ? (
        <div className="build-component-empty">
          <strong>Select a {type}</strong>
          <span>
            Use Explore Hardware or a hardware detail page to choose one.
          </span>
          <button
            type="button"
            className="build-component-select-button"
            onClick={onChange}
          >
            Browse {type} catalog
          </button>
        </div>
      ) : (
        <>
          <div className="build-component-head">
            <h3>{summary.name}</h3>
            <span className="build-component-manufacturer">
              {summary.manufacturer}
            </span>
            {summary.subtitle && (
              <span className="build-component-subtitle">{summary.subtitle}</span>
            )}
          </div>

          {busy && (
            <p className="build-component-status" role="status" aria-live="polite">
              <span className="state-spinner" aria-hidden="true" />
              Loading {type} details...
            </p>
          )}

          {errored && (
            <div className="build-component-error" role="alert">
              <strong>{type} details unavailable</strong>
              <span>{requestState.message}</span>
              <button
                type="button"
                className="build-retry-button"
                onClick={onRetry}
              >
                Retry
              </button>
            </div>
          )}

          {!busy && !errored && specs.length > 0 && (
            <div className="spec-grid build-component-specs">
              {specs.map((item) => (
                <div key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          )}

          <div className="build-component-actions">
            <button
              type="button"
              className="build-action-button"
              onClick={onChange}
            >
              Change {type}
            </button>

            <button
              type="button"
              className="build-clear-button"
              onClick={onClear}
            >
              Clear
            </button>
          </div>
        </>
      )}
    </section>
  );
}

const BUILD_INTELLIGENCE_STATUS_CLASS = {
  ready: "performance-status-available",
  partial: "performance-status-partial",
  loading: "performance-status-loading",
  unavailable: "performance-status-error",
  empty: "performance-status-loading",
};

function BuildIntelligenceSignalList({ signals, titleId }) {
  return (
    <ul className="build-intelligence-signals" aria-labelledby={titleId}>
      {signals.map((signal) => (
        <li
          key={signal.key}
          className={`build-intelligence-signal build-intelligence-signal-${signal.state}`}
        >
          <span className="build-intelligence-signal-label">{signal.label}</span>
          <strong className="build-intelligence-signal-value">
            {signal.display}
          </strong>
          <span className="build-intelligence-signal-state">
            {signal.stateLabel}
          </span>
          <span className="build-intelligence-signal-detail">{signal.detail}</span>
        </li>
      ))}
    </ul>
  );
}

function BuildIntelligenceSection({ intelligence }) {
  const { overview, power, completeness, benchmarkCoverage } = intelligence;
  const isEmpty = intelligence.status === BUILD_INTELLIGENCE_STATUS.empty;

  return (
    <section
      className="build-intelligence"
      aria-labelledby="build-intelligence-title"
      aria-busy={intelligence.isLoading}
    >
      <div className="build-intelligence-header">
        <div>
          <p className="detail-section-label">BUILD INTELLIGENCE</p>
          <h3 id="build-intelligence-title">What SPECTRA can verify</h3>
          <p className="build-intelligence-headline">{overview.headline}</p>
          <p className="build-intelligence-slot">{overview.slotLabel}</p>
        </div>

        <span
          className={`performance-status ${
            BUILD_INTELLIGENCE_STATUS_CLASS[intelligence.status]
          }`}
        >
          {intelligence.statusLabel}
        </span>
      </div>

      <p className="build-intelligence-boundary">
        Build Intelligence reports only stored specifications and benchmark
        records for the selected components. It does not estimate frame rate,
        component balance, thermals, or measured power.
      </p>

      {isEmpty ? (
        <p className="build-intelligence-empty">
          Select a CPU or a GPU to build verified intelligence for this build.
        </p>
      ) : (
        <>
          <dl className="build-intelligence-facts">
            <div className="build-intelligence-fact">
              <dt>Reportable signals</dt>
              <dd>
                {completeness.availableCount} of {completeness.expectedCount}
              </dd>
            </div>

            <div className="build-intelligence-fact">
              <dt>Verified benchmark metrics</dt>
              <dd>
                {benchmarkCoverage.totalExpectedCount === 0
                  ? "Not collected"
                  : `${benchmarkCoverage.totalAvailableCount} of ${benchmarkCoverage.totalExpectedCount}`}
              </dd>
            </div>

            <div className="build-intelligence-fact">
              <dt>Populated slots</dt>
              <dd>{overview.populatedSlotCount} of 2</dd>
            </div>

            <div className="build-intelligence-fact">
              <dt>{power.label}</dt>
              <dd>
                {power.listedComponentTdp === null
                  ? "Not available"
                  : `${power.listedComponentTdp} W`}
              </dd>
            </div>
          </dl>

          {intelligence.isLoading && (
            <p className="build-intelligence-status" role="status">
              <span className="state-spinner" aria-hidden="true" />
              Waiting for stored component data before reporting build signals.
            </p>
          )}

          {BUILD_SIGNAL_CATEGORY_ORDER.map((category) => (
            <section
              className="build-intelligence-group"
              key={category}
              aria-labelledby={`build-intelligence-group-${category}`}
            >
              <h4
                className="detail-section-label"
                id={`build-intelligence-group-${category}`}
              >
                {BUILD_SIGNAL_CATEGORY_LABELS[category]}
              </h4>

              <BuildIntelligenceSignalList
                signals={intelligence.signals[category]}
                titleId={`build-intelligence-group-${category}`}
              />
            </section>
          ))}

          <p className="build-intelligence-notice">{power.notice}</p>

          <div className="build-intelligence-block">
            <h4>What the available data shows</h4>
            <ul className="build-intelligence-list">
              {intelligence.interpretations.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>

          {intelligence.known.length > 0 && (
            <div className="build-intelligence-block">
              <h4>Known</h4>
              <ul className="build-intelligence-list">
                {intelligence.known.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          )}

          {BUILD_LIST_SECTIONS.map((section) => (
            <div className="build-intelligence-block" key={section.key}>
              <h4>{section.label}</h4>
              <ul className="build-intelligence-list">
                {intelligence[section.key].map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </section>
  );
}

function BuildConfigurationSection({
  buildConfig,
  buildDetailState,
  buildBenchmarkStates,
  buildUserContext,
  buildChatReady,
  buildChatState,
  buildChatContextSummary,
  onSelectType,
  onClearSlot,
  onRetrySlot,
  onUseCaseChange,
  onResolutionChange,
  onAskBuildQuestion,
  onRetryBuildChat,
  onNewBuildChat,
  onRetryBuildConversation,
}) {
  const summary = getBuildSummary(buildConfig);
  const cpuDetail = getBuildSlotDetail(buildDetailState, "CPU");
  const gpuDetail = getBuildSlotDetail(buildDetailState, "GPU");
  const cpuRequestState = getBuildSlotRequestState(buildDetailState, "CPU");
  const gpuRequestState = getBuildSlotRequestState(buildDetailState, "GPU");
  const facts = getBuildFacts(cpuDetail, gpuDetail);
  const tdpSum = calculateListedTdpSum(cpuDetail, gpuDetail);
  const buildChatChecklist = ["CPU", "GPU"].map((type) =>
    getBuildSlotChecklistItem(
      type,
      type === "CPU" ? buildConfig.cpu : buildConfig.gpu,
      type === "CPU" ? cpuRequestState : gpuRequestState
    )
  );
  const buildIntelligence = buildBuildIntelligence(cpuDetail, gpuDetail, {
    cpuSelected: buildConfig.cpu,
    gpuSelected: buildConfig.gpu,
    cpuRequestStatus: cpuRequestState.status,
    gpuRequestStatus: gpuRequestState.status,
    cpuBenchmarkState: buildBenchmarkStates.CPU,
    gpuBenchmarkState: buildBenchmarkStates.GPU,
  });

  return (
    <section id="build" className="build-section" aria-labelledby="build-title">
      <header className="build-head">
        <p className="eyebrow">BUILD CONFIGURATION</p>

        <h2 id="build-title">Build Configuration</h2>

        <p className="build-relationship">
          <strong>{summary.relationshipLabel}</strong>
          <span>
            SPECTRA lists stored specifications for the selected components. It
            does not assess motherboard, power supply, cooling, or case fit.
          </span>
        </p>
      </header>

      {/* Workspace: configuration on the left, live analysis on the right.
          DOM order matches reading order, so keyboard and screen-reader
          traversal follow the same path as the eye. */}
      <div className="build-workspace">
        <div className="build-column build-column-configuration">
          <div className="build-summary">
            <div className="build-summary-item">
              <span className="build-summary-label">CPU</span>
              <strong>{summary.cpu.name}</strong>
              {summary.cpu.isSelected ? (
                <span>{summary.cpu.manufacturer}</span>
              ) : (
                <span className="build-summary-empty">Empty slot</span>
              )}
            </div>

            <span className="build-summary-join" aria-hidden="true">
              +
            </span>

            <div className="build-summary-item">
              <span className="build-summary-label">GPU</span>
              <strong>{summary.gpu.name}</strong>
              {summary.gpu.isSelected ? (
                <span>{summary.gpu.manufacturer}</span>
              ) : (
                <span className="build-summary-empty">Empty slot</span>
              )}
            </div>
          </div>

          <div className="build-components">
            <BuildComponentCard
              type="CPU"
              selection={buildConfig.cpu}
              detail={cpuDetail}
              requestState={cpuRequestState}
              onChange={() => onSelectType("CPU")}
              onClear={() => onClearSlot("CPU")}
              onRetry={() => onRetrySlot("CPU")}
            />

            <BuildComponentCard
              type="GPU"
              selection={buildConfig.gpu}
              detail={gpuDetail}
              requestState={gpuRequestState}
              onChange={() => onSelectType("GPU")}
              onClear={() => onClearSlot("GPU")}
              onRetry={() => onRetrySlot("GPU")}
            />
          </div>
        </div>

        <div className="build-column build-column-intelligence">
          <BuildIntelligenceSection intelligence={buildIntelligence} />
        </div>
      </div>

      <div className="build-facts">
        <p className="detail-section-label">BUILD FACTS</p>

        {facts.length === 0 ? (
          <p className="build-facts-empty">
            {summary.isComplete
              ? "No listed specification values are available for these components."
              : "Select a CPU and a GPU to list their stored specification values."}
          </p>
        ) : (
          <div className="build-facts-list">
            {facts.map((fact) => (
              <div
                key={fact.id}
                className={`build-fact${
                  fact.id === "listed-tdp-sum" ? " build-fact-highlight" : ""
                }`}
              >
                <span>{fact.label}</span>
                <strong>{fact.value}</strong>
              </div>
            ))}
          </div>
        )}

        {tdpSum !== null && (
          <p className="build-facts-note">
            Listed component TDP values ({`${tdpSum} W`}) are summed for reference
            only. This is not a measurement of system power draw and is not a
            power supply requirement.
          </p>
        )}
      </div>

      <div className="build-lower">
        <div className="build-context">
          <p className="detail-section-label">CONTEXT</p>

          <p className="build-context-note" id="build-context-note">
            Context is recorded for your own reference. SPECTRA does not generate
            frame rate or performance estimates from it.
          </p>

          <div className="build-context-fields">
            <label htmlFor="build-use-case">
              <span>Use case</span>
              <select
                id="build-use-case"
                value={buildUserContext.useCase}
                onChange={(event) => onUseCaseChange(event.target.value)}
              >
                {BUILD_USE_CASES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label htmlFor="build-resolution">
              <span>Resolution</span>
              <select
                id="build-resolution"
                value={buildUserContext.resolution}
                onChange={(event) => onResolutionChange(event.target.value)}
              >
                {BUILD_RESOLUTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {buildChatReady ? (
        <div className="build-conversation">
          <BuildChatSection
            contextSummary={buildChatContextSummary}
            chatState={buildChatState}
            onAsk={onAskBuildQuestion}
            onRetry={onRetryBuildChat}
            onReset={onNewBuildChat}
            onRetryConversation={onRetryBuildConversation}
          />
        </div>
      ) : (
        <div className="build-conversation">
          <div className="build-ai-note">
            <p className="detail-section-label">ASK ABOUT THIS BUILD</p>
            <h3 className="build-ai-note-title">
              Build AI Chat unlocks when both slots are ready
            </h3>
            <ul className="build-ai-note-list">
              {buildChatChecklist.map((item) => (
                <li
                  className={`build-ai-note-item build-ai-note-item-${item.state}`}
                  key={item.type}
                >
                  <span className="build-ai-note-slot">{item.type}</span>
                  <span>{item.label}</span>
                </li>
              ))}
            </ul>
            <p className="build-ai-note-hint">
              SPECTRA answers only from the stored specifications and benchmark
              records of the selected components.
            </p>
          </div>
        </div>
      )}
      </div>
    </section>
  );
}

function App() {
  const [themeState, setThemeState] = useState(() =>
    createThemePreferenceState(
      readStoredThemePreference(typeof window === "undefined" ? null : window.localStorage),
      prefersColorSchemeDark()
    )
  );
  const [apiStatus, setApiStatus] = useState("Checking...");
  const [hardware, setHardware] = useState([]);
  const [hardwareLoading, setHardwareLoading] = useState(true);
  const [hardwareError, setHardwareError] = useState("");
  const [hardwareTypeFilter, setHardwareTypeFilter] = useState("All");
  const [cardSpecsById, setCardSpecsById] = useState({});
  const [search, setSearch] = useState("");
  const [manufacturerFilter, setManufacturerFilter] = useState("All");
  const [visibleCount, setVisibleCount] = useState(12);
  const [selectedHardware, setSelectedHardware] = useState(null);
  const [detailView, setDetailView] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [compareList, setCompareList] = useState([]);
  const [comparisonSelectionNotice, setComparisonSelectionNotice] =
    useState("");
  const [comparisonDetailState, setComparisonDetailState] = useState(
    createComparisonDetailState,
  );
  const [benchmarkStates, setBenchmarkStates] = useState({});
  const [aiAnalysis, setAiAnalysis] = useState({
    status: AI_ANALYSIS_STATUS.idle,
    explanation: "",
  });
  const detailGuardRef = useRef(createDetailRequestGuard());
  const catalogGuardRef = useRef(createCatalogLoadGuard());
  const cardSpecRequestIdsRef = useRef({});
  const comparisonRequestIdRef = useRef(0);
  const benchmarkRequestIdsRef = useRef({});
  const chatGuardRef = useRef(createChatRequestGuard());
  const [hardwareChatState, setHardwareChatState] = useState(
    createHardwareChatState
  );
  const [buildConfig, setBuildConfig] = useState(createBuildConfig);
  const [buildDetailState, setBuildDetailState] = useState(
    createBuildDetailState,
  );
  const [buildUserContext, setBuildUserContext] = useState(createBuildUserContext);
  const buildCpuGuardRef = useRef(createDetailRequestGuard());
  const buildGpuGuardRef = useRef(createDetailRequestGuard());
  const buildChatGuardRef = useRef(createChatRequestGuard());
  const buildConversationGuardRef = useRef(createChatRequestGuard());
  const buildConversationIdRef = useRef(null);

  const compareDetails = getComparisonDetailsInSelectionOrder(
    compareList,
    comparisonDetailState.detailsById,
  );

  const buildCpuDetail = getBuildSlotDetail(buildDetailState, "CPU");
  const buildGpuDetail = getBuildSlotDetail(buildDetailState, "GPU");
  const buildChatReady = isBuildChatContextReady(
    buildCpuDetail,
    buildGpuDetail
  );
  const buildChatSnapshot = getBuildChatSnapshot(
    buildCpuDetail,
    buildGpuDetail,
    buildUserContext
  );
  const buildChatToken = getBuildChatToken(buildChatSnapshot);
  const buildChatContextSummary = getBuildChatContextSummary(
    buildCpuDetail,
    buildGpuDetail,
    buildUserContext
  );
  const buildChatTokenRef = useRef(buildChatToken);
  const [buildChatState, setBuildChatState] = useState(() =>
    createBuildChatState(buildChatToken)
  );

  useEffect(() => {
    buildChatTokenRef.current = buildChatToken;
  });

  const getBuildBenchmarksBySlot = () => ({
    CPU: buildCpuDetail
      ? benchmarkStates[buildCpuDetail.id]?.results ?? []
      : [],
    GPU: buildGpuDetail
      ? benchmarkStates[buildGpuDetail.id]?.results ?? []
      : [],
  });

  const buildBenchmarkStates = {
    CPU: buildCpuDetail ? (benchmarkStates[buildCpuDetail.id] ?? null) : null,
    GPU: buildGpuDetail ? (benchmarkStates[buildGpuDetail.id] ?? null) : null,
  };

  const selectedComparisonType = compareList[0]?.type || null;
  const isGpuComparison = selectedComparisonType === "GPU";

  const signalProfile = buildSignalProfile(hardware);

  /* One effect owns the theme: it writes the attribute, persists an explicit
     choice, and follows the OS while the preference stays on "system". */
  useEffect(() => {
    applyThemeToDocument(themeState.theme, document, themeState.preference);
  }, [themeState.theme, themeState.preference]);

  useEffect(() => {
    const query =
      typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-color-scheme: dark)")
        : null;

    if (!query || typeof query.addEventListener !== "function") {
      return undefined;
    }

    const handleChange = () => {
      setThemeState((prev) =>
        prev.preference === "system"
          ? createThemePreferenceState("system", getPrefersColorSchemeDark(query))
          : prev
      );
    };

    query.addEventListener("change", handleChange);

    return () => query.removeEventListener("change", handleChange);
  }, []);

  const changeThemePreference = (preference) => {
    const normalized = normalizeThemePreference(preference);

    writeStoredThemePreference(
      typeof window === "undefined" ? null : window.localStorage,
      normalized
    );

    setThemeState((prev) => selectThemePreference(prev, normalized));
  };

  const loadBenchmarks = (hardwareId) => {
    const requestId = (benchmarkRequestIdsRef.current[hardwareId] || 0) + 1;
    benchmarkRequestIdsRef.current = {
      ...benchmarkRequestIdsRef.current,
      [hardwareId]: requestId,
    };

    setBenchmarkStates((prev) => setBenchmarkLoading(prev, hardwareId));

    fetch(apiUrl(`/hardware/${hardwareId}/benchmarks`))
      .then((response) => {
        return assertSuccessfulResponse(response).json();
      })
      .then((data) => {
        validateBenchmarkPayload(data);

        if (benchmarkRequestIdsRef.current[hardwareId] !== requestId) {
          return;
        }

        setBenchmarkStates((prev) => setBenchmarkSuccess(prev, hardwareId, data));
      })
      .catch((error) => {
        if (benchmarkRequestIdsRef.current[hardwareId] !== requestId) {
          return;
        }

        console.error("Failed to load benchmark data:", error);
        setBenchmarkStates((prev) =>
          setBenchmarkError(prev, hardwareId, "Benchmark data could not be loaded."),
        );
      });
  };

  const showHardwareDetail = (id) => {
    const requestId = detailGuardRef.current.begin();
    chatGuardRef.current.invalidate();
    setHardwareChatState(createHardwareChatState());
    const detailState = startDetailNavigation({
      selected: selectedHardware,
      view: detailView,
      loading: detailLoading,
      error: detailError,
    });
    setDetailLoading(detailState.loading);
    setDetailError(detailState.error);
    setSelectedHardware(detailState.selected);
    setDetailView(detailState.view);
    loadBenchmarks(id);

    requestHardwareDetail(id)
      .then((data) => {
        if (!detailGuardRef.current.isCurrent(requestId)) {
          return;
        }

        const detailState = completeDetailNavigation(
          { ...createDetailNavigationState(), view: true },
          data,
        );
        setSelectedHardware(detailState.selected);
        setDetailLoading(detailState.loading);
        setDetailError(detailState.error);
      })
      .catch((error) => {
        if (!detailGuardRef.current.isCurrent(requestId)) {
          return;
        }

        console.error("Failed to load hardware detail:", error);
        const detailState = failDetailNavigation(
          { ...createDetailNavigationState(), view: true },
          "Failed to load hardware details.",
        );
        setDetailError(detailState.error);
        setDetailLoading(detailState.loading);
      })
      .finally(() => {
        if (detailGuardRef.current.isCurrent(requestId)) {
          setDetailLoading(false);
        }
      });
  };

  const loadComparisonDetail = (item) => {
    const requestId = comparisonRequestIdRef.current + 1;
    comparisonRequestIdRef.current = requestId;
    setComparisonDetailState((prev) =>
      startComparisonDetailRequest(prev, item.id, requestId),
    );

    fetch(apiUrl(`/hardware/${item.id}`))
      .then((response) => {
        return assertSuccessfulResponse(response).json();
      })
      .then((data) => {
        validateComparisonDetailPayload(data, item.id);

        setComparisonDetailState((prev) =>
          completeComparisonDetailRequest(prev, item.id, requestId, data),
        );
      })
      .catch((error) => {
        console.error("Failed to load comparison data:", error);
        setComparisonDetailState((prev) =>
          failComparisonDetailRequest(prev, item.id, requestId),
        );
      });
  };

  const addToCompare = (item) => {
    const conflict = getComparisonTypeConflict(compareList, item);

    if (conflict) {
      setComparisonSelectionNotice(conflict);
      return;
    }

    const nextCompareList = addComparisonSelection(compareList, item);
    if (nextCompareList === compareList) {
      return;
    }

    setComparisonSelectionNotice("");
    setAiAnalysis({ status: AI_ANALYSIS_STATUS.idle, explanation: "" });
    setCompareList(nextCompareList);
    loadBenchmarks(item.id);
    loadComparisonDetail(item);
  };

  const removeFromCompare = (id) => {
    setComparisonSelectionNotice("");
    setAiAnalysis({ status: AI_ANALYSIS_STATUS.idle, explanation: "" });
    setCompareList((prev) => removeComparisonSelection(prev, id));

    setComparisonDetailState((prev) =>
      removeComparisonDetail(prev, id),
    );

    benchmarkRequestIdsRef.current = {
      ...benchmarkRequestIdsRef.current,
      [id]: (benchmarkRequestIdsRef.current[id] || 0) + 1,
    };

    setBenchmarkStates((prev) => {
      return removeBenchmarkState(prev, id);
    });
  };

  const clearComparison = () => {
    setComparisonSelectionNotice("");
    setAiAnalysis({ status: AI_ANALYSIS_STATUS.idle, explanation: "" });
    setCompareList(clearComparisonSelection());
    setComparisonDetailState(createComparisonDetailState());

    benchmarkRequestIdsRef.current = Object.fromEntries(
      Object.entries(benchmarkRequestIdsRef.current).map(([id, requestId]) => [
        id,
        requestId + 1,
      ]),
    );
    setBenchmarkStates({});
  };

  const loadBuildConversation = (requestToken, cpuId, gpuId) => {
    if (
      typeof cpuId !== "number" ||
      typeof gpuId !== "number" ||
      cpuId <= 0 ||
      gpuId <= 0
    ) {
      return;
    }

    const requestId = buildConversationGuardRef.current.begin();

    setBuildChatState((prev) =>
      startBuildChatConversationLoad(prev, requestToken)
    );

    requestBuildConversation(cpuId, gpuId)
      .then((conversation) =>
        requestBuildConversationMessages(conversation.id).then((messages) => ({
          conversation,
          messages,
        }))
      )
      .then(({ conversation, messages }) => {
        if (!buildConversationGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        buildConversationIdRef.current = conversation.id;
        setBuildChatState((prev) =>
          completeBuildChatConversationLoad(
            prev,
            conversation.id,
            messages,
            requestToken
          )
        );
      })
      .catch((error) => {
        if (!buildConversationGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        console.error("Failed to load the build conversation:", error);
        setBuildChatState((prev) =>
          failBuildChatConversationLoad(prev, error, requestToken)
        );
      });
  };

  const restoreBuildConversationForSlot = (type, detail) => {
    const otherSlot = type === "CPU" ? "GPU" : "CPU";
    const otherDetail = getBuildSlotDetail(buildDetailState, otherSlot);
    const cpuDetail = type === "CPU" ? detail : otherDetail;
    const gpuDetail = type === "GPU" ? detail : otherDetail;

    if (!isBuildChatContextReady(cpuDetail, gpuDetail)) {
      return;
    }

    loadBuildConversation(
      getBuildChatToken(
        getBuildChatSnapshot(cpuDetail, gpuDetail, buildUserContext)
      ),
      cpuDetail.id,
      gpuDetail.id
    );
  };

  const getBuildGuard = (type) =>
    type === "GPU" ? buildGpuGuardRef.current : buildCpuGuardRef.current;

  const loadBuildSlotDetail = (type, hardwareId) => {
    const guard = getBuildGuard(type);
    const requestId = guard.begin();

    setBuildDetailState((prev) =>
      startBuildDetailRequest(prev, type, requestId),
    );

    requestHardwareDetail(hardwareId)
      .then((data) => {
        if (!guard.isCurrent(requestId)) {
          return;
        }

        setBuildDetailState((prev) =>
          completeBuildDetailRequest(prev, type, requestId, data),
        );

        restoreBuildConversationForSlot(type, data);
      })
      .catch((error) => {
        if (!guard.isCurrent(requestId)) {
          return;
        }

        console.error("Failed to load build hardware detail:", error);
        setBuildDetailState((prev) =>
          failBuildDetailRequest(
            prev,
            type,
            requestId,
            `Failed to load ${type} details for the build configuration.`,
          ),
        );
      });
  };

  const getNextBuildChatToken = (changes = {}) =>
    getBuildChatToken({
      ...buildChatSnapshot,
      ...changes,
    });

  const resetBuildChat = (nextBuildToken) => {
    buildChatGuardRef.current.invalidate();
    buildConversationGuardRef.current.invalidate();
    buildConversationIdRef.current = null;
    setBuildChatState(createBuildChatState(nextBuildToken));
  };

  const addToBuild = (hardware) => {
    if (hardware?.type !== "CPU" && hardware?.type !== "GPU") {
      return;
    }

    const alreadySelected =
      getBuildSelection(buildConfig, hardware.type)?.id === hardware.id;

    if (!alreadySelected) {
      resetBuildChat(
        getNextBuildChatToken({
          [hardware.type === "CPU" ? "cpuId" : "gpuId"]: hardware.id,
        })
      );
    }

    setBuildConfig((prev) =>
      hardware.type === "CPU"
        ? setBuildCpu(prev, hardware)
        : setBuildGpu(prev, hardware),
    );

    if (!alreadySelected) {
      loadBuildSlotDetail(hardware.type, hardware.id);
    }
  };

  const retryBuildSlot = (type) => {
    const selection = getBuildSelection(buildConfig, type);

    if (!selection) {
      return;
    }

    loadBuildSlotDetail(type, selection.id);
  };

  const clearBuildSlot = (type) => {
    getBuildGuard(type).invalidate();
    resetBuildChat(
      getNextBuildChatToken({
        [type === "CPU" ? "cpuId" : "gpuId"]: null,
      })
    );

    setBuildConfig((prev) =>
      type === "CPU" ? clearBuildCpu(prev) : clearBuildGpu(prev),
    );
    setBuildDetailState((prev) => clearBuildSlotDetail(prev, type));
  };

  const changeBuildUseCase = (value) => {
    if (value === buildUserContext.useCase) {
      return;
    }

    const next = setBuildUseCase(buildUserContext, value);

    if (next === buildUserContext) {
      return;
    }

    resetBuildChat(
      getNextBuildChatToken({
        useCase: next.useCase,
        resolution: next.resolution,
      })
    );
    setBuildUserContext(next);
  };

  const changeBuildResolution = (value) => {
    if (value === buildUserContext.resolution) {
      return;
    }

    const next = setBuildResolution(buildUserContext, value);

    if (next === buildUserContext) {
      return;
    }

    resetBuildChat(
      getNextBuildChatToken({
        useCase: next.useCase,
        resolution: next.resolution,
      })
    );
    setBuildUserContext(next);
  };

  const browseForBuildType = (type) => {
    setManufacturerFilter("All");
    setSearch("");
    changeHardwareTypeFilter(type);

    scrollToSection("explore-top");
  };

  const returnToCatalog = () => {
    detailGuardRef.current.invalidate();
    chatGuardRef.current.invalidate();
    const catalogState = returnToCatalogState({
      selected: selectedHardware,
      view: detailView,
      loading: detailLoading,
      error: detailError,
    });
    setSelectedHardware(catalogState.selected);
    setDetailError(catalogState.error);
    setDetailLoading(catalogState.loading);
    setDetailView(catalogState.view);

    scrollToSection("explore-top");
  };

  const compareSelectedHardware = () => {
    if (!selectedHardware) {
      return;
    }

    const comparisonAction = getDetailComparisonAction(
      compareList,
      selectedHardware.id
    );

    if (comparisonAction.alreadySelected || comparisonAction.comparisonFull) {
      return;
    }

    addToCompare(selectedHardware);

    if (comparisonAction.shouldNavigateToComparison) {
      chatGuardRef.current.invalidate();
      setSelectedHardware(null);
      setDetailView(false);
      scrollToSection("compare");
    }
  };

  const loadHardwareCatalog = (type) => {
    const requestId = catalogGuardRef.current.begin();

    requestHardwareCatalog(type)
      .then((items) => {
        if (!catalogGuardRef.current.isCurrent(requestId)) {
          return;
        }

        setHardware(items);
        setHardwareLoading(false);
      })
      .catch((error) => {
        if (!catalogGuardRef.current.isCurrent(requestId)) {
          return;
        }

        console.error("Failed to load hardware catalog:", error);
        setHardwareError("Hardware catalog could not be loaded.");
        setHardwareLoading(false);
      });
  };

  const changeHardwareTypeFilter = (type) => {
    setHardwareTypeFilter(type);
    setHardwareLoading(true);
    setHardwareError("");
    setCardSpecsById({});
    cardSpecRequestIdsRef.current = {};
    loadHardwareCatalog(type);
  };

  useEffect(() => {
    loadHardwareCatalog("All");
  }, []);

  useEffect(() => {
    fetch(apiUrl("/"))
      .then((response) => response.json())
      .then((data) => {
        setApiStatus(data.status);
      })
      .catch(() => {
        setApiStatus("offline");
      });
  }, []);

  useEffect(() => {
    if (!selectedHardware) {
      return;
    }

    const detail = document.querySelector(".hardware-detail");
    detail?.scrollIntoView({
      behavior: getScrollBehavior(),
      block: "start",
    });
    detail?.querySelector("h2")?.focus({ preventScroll: true });
  }, [selectedHardware]);

  useEffect(() => {
    setVisibleCount(12);
  }, [search, manufacturerFilter, hardwareTypeFilter]);

  const normalizeSearch = (text) => {
    return text
      .toLowerCase()
      .replace(/[-_]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  };

  const filteredHardware = hardware.filter((item) => {
    const matchesSearch = normalizeSearch(item.name).includes(
      normalizeSearch(search)
    );

    const matchesManufacturer =
      manufacturerFilter === "All" ||
      item.manufacturer === manufacturerFilter;

    return matchesSearch && matchesManufacturer;
  });

  const catalogResultSummary = getCatalogResultSummary({
    loading: hardwareLoading,
    error: hardwareError,
    visibleCount,
    totalCount: filteredHardware.length,
    manufacturerFilter,
    typeFilter: hardwareTypeFilter,
  });

  const comparisonSummary = getComparisonSelectionSummary(compareList);

  useEffect(() => {
    const visibleCards = filteredHardware.slice(0, visibleCount);

    visibleCards.forEach((item) => {
      if (item.type !== "GPU") {
        return;
      }

      if (cardSpecsById[item.id] !== undefined) {
        return;
      }

      if (cardSpecRequestIdsRef.current[item.id]) {
        return;
      }

      const requestId =
        (cardSpecRequestIdsRef.current[item.id] || 0) + 1;
      cardSpecRequestIdsRef.current = {
        ...cardSpecRequestIdsRef.current,
        [item.id]: requestId,
      };

      fetch(apiUrl(`/hardware/${item.id}`))
        .then((response) => {
          return assertSuccessfulResponse(response).json();
        })
        .then((data) => {
          validateHardwareDetailPayload(data, item.id);

          if (cardSpecRequestIdsRef.current[item.id] !== requestId) {
            return;
          }

          setCardSpecsById((prev) => ({
            ...prev,
            [item.id]: data.specifications || {},
          }));
        })
        .catch((error) => {
          if (cardSpecRequestIdsRef.current[item.id] !== requestId) {
            return;
          }

          console.error("Failed to load card specifications:", error);
          setCardSpecsById((prev) => ({
            ...prev,
            [item.id]: null,
          }));
        });
    });
  }, [filteredHardware, visibleCount, cardSpecsById]);

  const comparisonInsights = calculateComparisonInsights(
    compareDetails,
    benchmarkStates
  );
  const benchmarkComparison = getBenchmarkComparisonData(
    compareDetails,
    benchmarkStates
  );
  const comparisonFacts = buildComparisonFacts(compareDetails, benchmarkStates);
  const decisionSummary = buildComparisonDecisionSummary(
    compareDetails,
    benchmarkStates
  );

  const generateAiAnalysis = () => {
    if (!comparisonFacts) {
      return;
    }

    setAiAnalysis({ status: AI_ANALYSIS_STATUS.loading, explanation: "" });
    requestComparisonExplanation(comparisonFacts)
      .then((explanation) => {
        setAiAnalysis({ status: AI_ANALYSIS_STATUS.success, explanation });
      })
      .catch((error) => {
        console.error("Failed to generate AI analysis:", error);
        setAiAnalysis({ status: AI_ANALYSIS_STATUS.error, explanation: "" });
      });
  };

  const askHardwareChat = (question) => {
    const trimmedQuestion = (question ?? "").trim();
    if (!trimmedQuestion || !selectedHardware) {
      return;
    }

    const requestId = chatGuardRef.current.begin();
    const context = buildHardwareChatContext(
      selectedHardware,
      benchmarkStates[selectedHardware.id]?.results ?? []
    );

    setHardwareChatState((prev) =>
      startHardwareChatRequest(prev, trimmedQuestion)
    );

    requestHardwareChatAnswer(context, trimmedQuestion)
      .then((answer) => {
        if (!chatGuardRef.current.isCurrent(requestId)) {
          return;
        }

        setHardwareChatState((prev) =>
          completeHardwareChatRequest(prev, answer)
        );
      })
      .catch((error) => {
        if (!chatGuardRef.current.isCurrent(requestId)) {
          return;
        }

        console.error("Failed to get hardware chat answer:", error);
        setHardwareChatState((prev) =>
          failHardwareChatRequest(prev, error)
        );
      });
  };

  const saveBuildChatTurn = (requestToken, question, result) => {
    const cpuId = buildCpuDetail?.id ?? null;
    const gpuId = buildGpuDetail?.id ?? null;
    const requestId = buildConversationGuardRef.current.begin();

    let turn;

    try {
      turn = buildBuildTurnPayload(question, result);
    } catch (error) {
      console.error("Failed to save the build conversation:", error);
      setBuildChatState((prev) =>
        failBuildChatConversationSave(prev, error, requestToken)
      );
      return;
    }

    ensureBuildConversation(buildConversationIdRef.current, cpuId, gpuId)
      .then((conversationId) => {
        buildConversationIdRef.current = conversationId;
        return appendBuildConversationTurn(conversationId, turn);
      })
      .then(() => {
        if (!buildConversationGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        setBuildChatState((prev) =>
          completeBuildChatConversationSave(
            prev,
            buildConversationIdRef.current,
            requestToken
          )
        );
      })
      .catch((error) => {
        if (!buildConversationGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        console.error("Failed to save the build conversation:", error);
        setBuildChatState((prev) =>
          failBuildChatConversationSave(prev, error, requestToken)
        );
      });
  };

  const askBuildChat = (question) => {
    if (!buildChatReady || isBuildChatBusy(buildChatState)) {
      return;
    }

    let payload;

    try {
      payload = buildChatPayload(
        buildCpuDetail,
        buildGpuDetail,
        buildUserContext,
        question,
        getBuildBenchmarksBySlot(),
        buildChatState.messages,
      );
    } catch (error) {
      setBuildChatState((prev) =>
        failBuildChatRequest(prev, error, prev.buildToken)
      );
      return;
    }

    const requestId = buildChatGuardRef.current.begin();
    const requestToken = buildChatToken;

    setBuildChatState((prev) =>
      startBuildChatRequest(prev, payload.question, requestToken),
    );

    requestBuildChatAnswer(payload)
      .then((result) => {
        if (!buildChatGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        setBuildChatState((prev) =>
          completeBuildChatRequest(
            prev,
            result.answer,
            requestToken,
            result.evidence,
            result.analysis
          )
        );

        saveBuildChatTurn(requestToken, payload.question, result);
      })
      .catch((error) => {
        if (!buildChatGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        console.error("Failed to get build chat answer:", error);
        setBuildChatState((prev) =>
          failBuildChatRequest(prev, error, requestToken)
        );
      });
  };

  const retryBuildChat = () => {
    askBuildChat(buildChatState.pendingQuestion);
  };

  const clearStoredBuildConversation = (requestToken) => {
    const conversationId = buildConversationIdRef.current;

    if (conversationId === null) {
      return;
    }

    const requestId = buildConversationGuardRef.current.begin();

    resetBuildConversationMessages(conversationId)
      .then(() => {
        if (!buildConversationGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        setBuildChatState((prev) =>
          completeBuildChatConversationSave(prev, conversationId, requestToken)
        );
      })
      .catch((error) => {
        if (!buildConversationGuardRef.current.isCurrent(requestId)) {
          return;
        }

        if (!isSameBuildChatToken(buildChatTokenRef.current, requestToken)) {
          return;
        }

        console.error("Failed to start a new build conversation:", error);
        setBuildChatState((prev) =>
          failBuildChatConversationReset(prev, error, requestToken)
        );
      });
  };

  const retryBuildConversation = () => {
    const conversationError = getBuildChatConversationError(buildChatState);

    if (
      conversationError?.kind ===
      BUILD_CHAT_CONVERSATION_ERROR_KIND.save
    ) {
      const turn = getLastBuildChatTurn(buildChatState);

      if (turn) {
        saveBuildChatTurn(buildChatToken, turn.question, turn);
      }

      return;
    }

    if (
      conversationError?.kind ===
      BUILD_CHAT_CONVERSATION_ERROR_KIND.reset
    ) {
      clearStoredBuildConversation(buildChatToken);
      return;
    }

    loadBuildConversation(buildChatToken);
  };

  const startNewBuildChat = () => {
    const requestToken = buildChatToken;

    buildChatGuardRef.current.invalidate();
    buildConversationGuardRef.current.invalidate();
    setBuildChatState((prev) => resetBuildChatConversation(prev));
    clearStoredBuildConversation(requestToken);
  };

  const comparisonSpecRows = buildComparisonSpecRows(compareDetails);

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <nav className="navbar" aria-label="Primary">
        <div className="logo">SPECTRA</div>

        <div className="nav-links">
          <a href="#explore" className="nav-link">
            Explore
          </a>

          <a href="#compare" className="nav-link">
            Compare
          </a>

          <a href="#build" className="nav-link">
            Build
          </a>

          <a href="#about" className="nav-link">
            About
          </a>
        </div>

        <ThemeControl
          preference={themeState.preference}
          onSelect={changeThemePreference}
        />
      </nav>

      <main className="hero" id="main-content">
        <div className="hero-content">
          <div className="hero-eyebrow">
            <p className="eyebrow">
              HARDWARE INTELLIGENCE PLATFORM
            </p>

            <span className="spectra-ref">S-01</span>
          </div>

          <h1>
            Explore hardware.
            <br />
            Understand performance.
          </h1>

          <p className="description">
            Discover detailed specifications and explore
            computer hardware through SPECTRA.
          </p>

          <div className="search-box">
            <span aria-hidden="true">⌕</span>

            <label className="sr-only" htmlFor="catalog-search">
              Search hardware by name
            </label>

            <input
              id="catalog-search"
              type="search"
              autoComplete="off"
              placeholder="Search hardware..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />

            {search && (
              <button
                type="button"
                className="clear-search-icon"
                aria-label="Clear hardware search"
                onClick={() => setSearch("")}
              >
                ×
              </button>
            )}
          </div>

          <div className="catalog-filters">
            <div
              className="filter-group"
              role="group"
              aria-label="Filter hardware by type"
            >
              <span className="filter-group-label" id="filter-type-label">
                Hardware type
              </span>

              <div
                className="filter-buttons filter-buttons-type"
                aria-labelledby="filter-type-label"
              >
                {HARDWARE_TYPES.map((type) => {
                  const filterState = getCatalogFilterState(
                    type,
                    hardwareTypeFilter
                  );

                  return (
                    <button
                      type="button"
                      key={type}
                      className={filterState.className}
                      aria-pressed={filterState.pressed}
                      onClick={() => changeHardwareTypeFilter(type)}
                    >
                      {type === "All" ? "All hardware" : type}
                    </button>
                  );
                })}
              </div>
            </div>

            <div
              className="filter-group"
              role="group"
              aria-label="Filter hardware by manufacturer"
            >
              <span className="filter-group-label" id="filter-maker-label">
                Manufacturer
              </span>

              <div
                className="filter-buttons"
                aria-labelledby="filter-maker-label"
              >
                {MANUFACTURER_FILTERS.map((manufacturer) => {
                  const filterState = getCatalogFilterState(
                    manufacturer,
                    manufacturerFilter
                  );

                  return (
                    <button
                      type="button"
                      key={manufacturer}
                      className={filterState.className}
                      aria-pressed={filterState.pressed}
                      onClick={() => setManufacturerFilter(manufacturer)}
                    >
                      {manufacturer}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <p
            className={`api-status ${
              apiStatus === "online" ? "api-status-online" : ""
            }`}
            role="status"
          >
            <span className="status-dot" aria-hidden="true" />
            Catalog {apiStatus === "online" ? "connected" : apiStatus}
          </p>

          <span className="spectra-spectrum" aria-hidden="true" />
        </div>

        <SignalReadout
          profile={signalProfile}
          loading={hardwareLoading}
          error={hardwareError}
        />
      </main>

      <div className="catalog-readout" aria-live="polite" id="catalog-count">
        <div className="catalog-readout-figure">
          <span className="catalog-readout-value">
            {formatSignalCount(filteredHardware.length)}
          </span>
          <span className="catalog-readout-label">
            matching{" "}
            {hardwareTypeFilter === "All"
              ? "hardware records"
              : `${hardwareTypeFilter} records`}
          </span>
        </div>

        <span className="catalog-readout-meta">
          {manufacturerFilter === "All"
            ? "All manufacturers"
            : manufacturerFilter}
          {" · "}
          {catalogResultSummary}
        </span>
      </div>

      {compareList.length > 0 && (
        <section
          className="comparison-selection"
          aria-labelledby="comparison-selection-title"
        >
          <div className="comparison-selection-heading">
            <div>
              <p className="eyebrow">COMPARISON SET</p>
              <h2 id="comparison-selection-title">Ready to compare</h2>
              <p className="comparison-selection-status" role="status">
                {comparisonSummary.status}
              </p>
            </div>

            <a className="comparison-jump-link" href="#compare">
              View comparison <span aria-hidden="true">↓</span>
            </a>
          </div>

          <div className="comparison-selection-list">
            {compareList.map((item, index) => (
              <div className="comparison-selection-item" key={item.id}>
                <span className="comparison-selection-index">
                  {comparisonSummary.slotLabel(index + 1)}
                </span>
                <div>
                  <strong>{item.name}</strong>
                  <span>
                    {item.manufacturer} · {item.type || "Processor"}
                  </span>
                </div>
                <button
                  type="button"
                  className="selection-remove-button"
                  aria-label={`Remove ${item.name} from comparison`}
                  onClick={() => removeFromCompare(item.id)}
                >
                  Remove
                </button>
              </div>
            ))}

            {comparisonSummary.emptySlot && (
              <div className="comparison-selection-item comparison-selection-slot">
                <span className="comparison-selection-index">
                  {comparisonSummary.emptySlot.indexLabel}
                </span>
                <div>
                  <strong>{comparisonSummary.emptySlot.title}</strong>
                  <span>{comparisonSummary.emptySlot.hint}</span>
                </div>
              </div>
            )}
          </div>

          {comparisonSelectionNotice && (
            <p className="comparison-selection-notice" role="alert">
              {comparisonSelectionNotice}
            </p>
          )}

          <button
            type="button"
            className="selection-clear-button"
            onClick={clearComparison}
          >
            Clear selection
          </button>
        </section>
      )}

      <section id="explore" className="hardware-section">
        <div className="section-head" id="explore-top-wrap">
          <div className="section-head-text">
            <p className="eyebrow">CATALOG</p>

            <h2 id="explore-top" tabIndex={-1} className={detailView ? "detail-hidden" : ""}>
              Explore Hardware
            </h2>
          </div>

          <p className="section-head-meta">
            {filteredHardware.length > 0
              ? `${HARDWARE_TYPES.filter((type) => type !== "All").length} classes indexed`
              : "Awaiting records"}
          </p>
        </div>

        <div
          className={detailView ? "catalog-content detail-hidden" : "catalog-content"}
          aria-busy={hardwareLoading}
        >
          {hardwareLoading ? (
            <div className="catalog-state" role="status" aria-live="polite">
              <span className="state-spinner" aria-hidden="true" />
              <h3>Loading the catalog</h3>
              <p>Fetching verified hardware records.</p>
            </div>
          ) : hardwareError ? (
            <div className="catalog-state catalog-state-error" role="alert">
              <h3>Catalog unavailable</h3>
              <p>{hardwareError}</p>
              <button
                type="button"
                className="secondary-button"
                onClick={() => window.location.reload()}
              >
                Try Again
              </button>
            </div>
          ) : filteredHardware.length === 0 ? (
            <div className="hardware-empty">
              <span className="hardware-empty-icon" aria-hidden="true">
                ◈
              </span>

              <h3>No hardware found</h3>

              <p>
                Try another search term or change your filter.
              </p>

              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setSearch("");
                  setManufacturerFilter("All");
                  setHardwareTypeFilter("All");
                }}
              >
                Clear all filters
              </button>
            </div>
          ) : (
            <div className="hardware-grid">
              {filteredHardware
                .slice(0, visibleCount)
                .map((item) => {
                  const cardSpecRows = getHardwareCardPrimarySpecs(
                    item.type,
                    cardSpecsById[item.id]
                  );
                  const buildAction = getBuildComponentAction(buildConfig, item);
                  const inComparison = compareList.some(
                    (hardware) => hardware.id === item.id
                  );
                  const comparisonFull = !inComparison && compareList.length >= 2;

                  return (
                    <article
                      className={`hardware-card ${
                        inComparison ? "in-comparison" : ""
                      }`}
                      key={item.id}
                    >
                      <button
                        type="button"
                        className="hardware-card-main"
                        onClick={() => showHardwareDetail(item.id)}
                      >
                        <span className="hardware-card-kicker">
                          {item.type || "CPU"}
                        </span>
                        <h3>{item.name}</h3>
                        <span className="hardware-card-manufacturer">
                          {item.manufacturer}
                        </span>

                        {cardSpecRows.length > 0 ? (
                          <div className="hardware-card-specs">
                            {cardSpecRows.map((row) => (
                              <span key={row.label}>
                                <em>{row.label}</em>
                                <strong>{row.value}</strong>
                              </span>
                            ))}
                          </div>
                        ) : (
                          <div className="hardware-card-specs hardware-card-specs-pending">
                            <span>
                              <em>Specs</em>
                              <strong>Loading…</strong>
                            </span>
                          </div>
                        )}

                        <span className="hardware-card-action">
                          View specifications <span aria-hidden="true">→</span>
                        </span>
                      </button>

                      <div className="hardware-card-actions">
                        <button
                          type="button"
                          className={`compare-button ${inComparison ? "added" : ""}`}
                          aria-pressed={inComparison}
                          onClick={(event) => {
                            event.stopPropagation();
                            addToCompare(item);
                          }}
                          disabled={comparisonFull}
                        >
                          {inComparison
                            ? "✓ In Comparison"
                            : comparisonFull
                              ? "Comparison Full"
                              : "Compare"}
                        </button>

                        {buildAction.isBuildSlot && (
                          <button
                            type="button"
                            className={`build-button ${
                              buildAction.alreadySelected ? "added" : ""
                            }`}
                            aria-pressed={buildAction.alreadySelected}
                            onClick={(event) => {
                              event.stopPropagation();
                              addToBuild(item);
                            }}
                          >
                            {buildAction.actionLabel}
                          </button>
                        )}
                      </div>
                    </article>
                  );
                })}
            </div>
          )}
        </div>

        {!detailView && visibleCount < filteredHardware.length && (
          <div className="load-more-container">
            <button
              type="button"
              className="secondary-button load-more-button"
              onClick={() =>
                setVisibleCount((prev) =>
                  Math.min(prev + 12, filteredHardware.length)
                )
              }
            >
              Load more hardware
            </button>
          </div>
        )}

        {!detailView && detailLoading && (
          <p className="detail-status" role="status" aria-live="polite">
            Loading hardware details...
          </p>
        )}

        {!detailView && detailError && (
          <p className="detail-error" role="alert">
            {detailError}
          </p>
        )}

        {detailView && detailLoading && (
          <div className="detail-state" role="status" aria-live="polite">
            <span className="state-spinner" aria-hidden="true" />
            <strong>Loading hardware details</strong>
            <span>Fetching verified specifications and benchmark data.</span>
          </div>
        )}

        {detailView && detailError && !selectedHardware && (
          <div className="detail-state detail-state-error" role="alert">
            <strong>Hardware details unavailable</strong>
            <span>{detailError}</span>
            <button
              type="button"
              className="secondary-button"
              onClick={returnToCatalog}
            >
              Back to catalog
            </button>
          </div>
        )}

        {detailView && selectedHardware && (
          selectedHardware.type === "GPU" ? (
            <GpuHardwareDetail
              hardware={selectedHardware}
              buildAction={getBuildComponentAction(buildConfig, selectedHardware)}
              onBack={returnToCatalog}
              onAddToBuild={() => addToBuild(selectedHardware)}
            />
          ) : (
            <CpuDetailView
              hardware={selectedHardware}
              benchmarkState={benchmarkStates[selectedHardware.id]}
              compareList={compareList}
              buildAction={getBuildComponentAction(buildConfig, selectedHardware)}
              onBack={returnToCatalog}
              onCompare={compareSelectedHardware}
              onAddToBuild={() => addToBuild(selectedHardware)}
              detailError={detailError}
              chatState={hardwareChatState}
              onAskQuestion={askHardwareChat}
            />
          )
        )}

        <BuildConfigurationSection
          buildConfig={buildConfig}
          buildDetailState={buildDetailState}
          buildBenchmarkStates={buildBenchmarkStates}
          buildUserContext={buildUserContext}
          buildChatReady={buildChatReady}
          buildChatState={buildChatState}
          buildChatContextSummary={buildChatContextSummary}
          onSelectType={browseForBuildType}
          onClearSlot={clearBuildSlot}
          onRetrySlot={retryBuildSlot}
          onUseCaseChange={changeBuildUseCase}
          onResolutionChange={changeBuildResolution}
          onAskBuildQuestion={askBuildChat}
          onRetryBuildChat={retryBuildChat}
          onNewBuildChat={startNewBuildChat}
          onRetryBuildConversation={retryBuildConversation}
        />

        <section
          id="compare"
          className={`comparison-section ${detailView ? "detail-hidden" : ""}`}
          aria-labelledby="compare-title"
        >
          <div className="section-head">
            <div className="section-head-text">
              <p className="eyebrow">HARDWARE COMPARISON</p>

              <h2 id="compare-title">{comparisonSummary.heading}</h2>
            </div>

            <p className="section-head-status" role="status">
              {comparisonSummary.status}
            </p>
          </div>

          {compareList.length === 0 ? (
            <div className="comparison-empty">
              <div>
                <span className="comparison-empty-index">01 — 02</span>
                <h3>Build a side-by-side view</h3>
                <p>
                  Choose up to two CPUs or GPUs from Explore Hardware. Selected
                  hardware will appear here with verified specs and benchmark
                  results.
                </p>
              </div>
              <a className="comparison-explore-link" href="#explore">
                Browse hardware <span aria-hidden="true">→</span>
              </a>
            </div>
          ) : (
            <div className="comparison-content">
              {comparisonSummary.needsSecondItem && (
                <p className="comparison-instruction">
                  Select another {selectedComparisonType || "CPU"} to start
                  comparing hardware.
                </p>
              )}

              <button
                type="button"
                className="clear-compare-button"
                onClick={clearComparison}
              >
                Clear Comparison
              </button>

              {compareDetails.length === 2 && (
                <div
                  className="comparison-legend"
                  aria-label="Comparison guidance"
                >
                  <span className="comparison-legend-title">
                    <span
                      className="comparison-legend-swatch"
                      aria-hidden="true"
                    />
                    Highlighted value is better
                  </span>

                  <span>
                    Higher is better:{" "}
                    {isGpuComparison
                      ? "VRAM, Memory Bandwidth, Core Clock, Boost Clock."
                      : "Cores, Threads, Base Clock, Boost Clock."}
                  </span>

                  <span>
                    Lower is better:{" "}
                    {isGpuComparison ? "TDP, Length." : "TDP."}
                  </span>
                </div>
              )}

              {compareDetails.length === 2 && (
                <p className="comparison-scroll-hint">
                  <span aria-hidden="true">↔</span> Scroll horizontally to
                  view the full comparison on smaller screens.
                </p>
              )}

              <div className="comparison-performance">
                {compareList.map((item, index) => {
                  const requestState =
                    comparisonDetailState.requestStatesById[item.id];
                  const detail = comparisonDetailState.detailsById[item.id];
                  // A and B, not the slot label: the pair should read as a
                  // relation. The type is already carried by the section label
                  // and the table headers.
                  const slotLetter = COMPARISON_SLOT_LETTERS[index] || "";

                  if (requestState?.status === "error") {
                    return (
                      <section
                        className="comparison-performance-card comparison-detail-error"
                        key={item.id}
                        role="alert"
                        data-slot={slotLetter}
                      >
                        <p className="detail-section-label">
                          {item.type === "GPU" ? "GPU DETAIL" : "CPU DETAIL"}
                        </p>
                        <h3>{item.name}</h3>
                        <p>
                          Unable to load{" "}
                          {item.type === "GPU" ? "GPU" : "CPU"} details.
                        </p>
                        <div className="comparison-detail-actions">
                          <button
                            type="button"
                            className="secondary-button"
                            onClick={() => loadComparisonDetail(item)}
                          >
                            Retry
                          </button>
                          <button
                            type="button"
                            className="remove-compare-button"
                            onClick={() => removeFromCompare(item.id)}
                          >
                            Remove
                          </button>
                        </div>
                      </section>
                    );
                  }

                  if (!detail || requestState?.status === "loading") {
                    return (
                      <section
                        className="comparison-performance-card"
                        key={item.id}
                        aria-busy={true}
                        role="status"
                        data-slot={slotLetter}
                      >
                        <p className="detail-section-label">
                          {item.type === "GPU" ? "GPU DETAIL" : "CPU DETAIL"}
                        </p>
                        <h3>{item.name}</h3>
                        <div className="comparison-loading">
                          <span className="state-spinner" aria-hidden="true" />
                          Loading selected{" "}
                          {item.type === "GPU" ? "GPU" : "CPU"} details...
                        </div>
                      </section>
                    );
                  }

                  return (
                    <section
                      className="comparison-performance-card"
                      key={item.id}
                      data-slot={slotLetter}
                    >
                      <p className="detail-section-label">PERFORMANCE</p>
                      <h3>{detail.name}</h3>
                      <PerformanceSection
                        benchmarkState={benchmarkStates[detail.id]}
                        hardwareType={item.type || "CPU"}
                        titleId={`comparison-performance-${detail.id}`}
                      />
                    </section>
                  );
                })}
              </div>


{compareDetails.length === 2 && (
                <ComparisonDecisionSupport summary={decisionSummary} />
              )}

              {compareDetails.length === 2 && !isGpuComparison && (
                <BenchmarkComparison
                  comparisonData={benchmarkComparison}
                  compareDetails={compareDetails}
                />
              )}

               {compareDetails.length === 2 && isGpuComparison && (
                 <section
                   className="benchmark-comparison"
                   aria-labelledby="gpu-benchmark-comparison-title"
                 >
                   <div className="benchmark-comparison-header">
                     <div>
                       <p className="detail-section-label">GPU BENCHMARKS</p>
                       <h3 id="gpu-benchmark-comparison-title">
                         No GPU benchmark data
                       </h3>
                     </div>
                     <span className="performance-status">NO DATA</span>
                   </div>
                   <p className="benchmark-comparison-notice">
                     No verified GPU benchmark results are available for these
                     GPUs yet.
                   </p>
                 </section>
               )}

              {compareDetails.length === 2 && (
                <ComparisonInsights
                  insights={comparisonInsights}
                  compareDetails={compareDetails}
                />
              )}

              {compareDetails.length === 2 && !isGpuComparison && (
                <AiAnalysis
                  analysis={aiAnalysis}
                  onGenerate={generateAiAnalysis}
                />
              )}

              {compareDetails.length === 2 && (
                <div className="comparison-table-wrapper" tabIndex={0} role="group" aria-label={`${isGpuComparison ? "GPU" : "CPU"} specification table, scrollable horizontally`}>
                  <table className="comparison-table">
                    <caption className="sr-only">
                      Side-by-side{" "}
                      {isGpuComparison ? "GPU" : "CPU"} specification comparison
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Specification</th>

                        {compareDetails.map((item) => (
                          <th scope="col" key={item.id}>
                            <div className="comparison-header">
                              <span>{item.name}</span>

                              <button
                                type="button"
                                className="remove-compare-button"
                                aria-label={`Remove ${item.name} from comparison`}
                                onClick={() =>
                                  removeFromCompare(item.id)
                                }
                              >
                                Remove
                              </button>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>

                    <tbody>
                      {comparisonSpecRows.map((row) => (
                        <tr key={row.key}>
                          <th scope="row">
                            <span className="comparison-row-label">
                              {row.label}
                            </span>

                            {row.direction && (
                              <span className="comparison-row-direction">
                                {row.direction === "lower"
                                  ? "Lower is better"
                                  : "Higher is better"}
                              </span>
                            )}

                            <span className="comparison-row-summary">
                              {row.summary}
                            </span>
                          </th>

                          {row.cells.map((cell) => (
                            <td key={cell.side} className={cell.className}>
                              <span className="comparison-cell-value">
                                {cell.display}
                              </span>

                              {cell.marker && (
                                <span className="comparison-cell-marker">
                                  {cell.marker}
                                </span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>

        <section id="about" className="about-section" aria-labelledby="about-title">
          <p className="eyebrow">ABOUT SPECTRA</p>
          <h2 id="about-title" className="sr-only">
            About SPECTRA
          </h2>
          <p>
            A focused way to inspect hardware specifications and compare verified
            performance data without filling gaps with estimates.
          </p>
        </section>
      </section>
    </div>
  );
}

export default App;

