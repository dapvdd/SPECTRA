/**
 * M4 Task 7: pure display/request logic for the intelligent recommendation
 * and scenario-rating panels. Free of React so it runs under `node --test`.
 *
 * Evidence policy mirrors the backend (M4-SCORING-v2.0 / M4-REC-v2.0):
 * - UNKNOWN scenarios are rendered as "unknown", never as 0 stars.
 * - spec-based scores carry their limitations.
 * - No price, FPS, or availability value is ever fabricated here.
 */

import { getConfidenceBadge } from "./suitabilityDisplay.js";
import { formatProfileLabel } from "./intelligenceDisplay.js";

export const RECOMMEND_V2_ENDPOINT = "/hardware/recommend/v2";
export const BUILD_INTELLIGENCE_ENDPOINT = "/build/intelligence";
export const BUILD_OPTIMIZE_ENDPOINT = "/build/optimize";

export const SCENARIO_LABELS = {
  gaming: "Gaming",
  workstation: "Workstation",
  daily: "Daily use",
  value: "Value",
};

export const SCENARIO_ORDER = ["gaming", "workstation", "daily", "value"];

export const CONSTRAINT_CLASSIFICATIONS = [
  "hard",
  "soft",
  "unknown",
  "estimated",
];

/**
 * Build the /hardware/recommend/v2 endpoint with query params. Only set
 * params are included; the backend validates profile keys and bounds.
 */
export const getRecommendationV2Endpoint = ({
  hardwareType,
  profileKey,
  budgetMax,
  resolution,
  powerLimitW,
  priority,
  limit,
}) => {
  const params = new URLSearchParams();
  if (hardwareType) {
    params.set("type", hardwareType);
  }
  if (profileKey) {
    params.set("profile_key", profileKey);
  }
  if (typeof budgetMax === "number" && Number.isFinite(budgetMax)) {
    params.set("budget_max", String(budgetMax));
  }
  if (resolution) {
    params.set("resolution", resolution);
  }
  if (typeof powerLimitW === "number" && Number.isFinite(powerLimitW)) {
    params.set("power_limit_w", String(powerLimitW));
  }
  if (priority) {
    params.set("priority", priority);
  }
  if (typeof limit === "number" && Number.isFinite(limit)) {
    params.set("limit", String(limit));
  }
  const query = params.toString();
  return query ? `${RECOMMEND_V2_ENDPOINT}?${query}` : RECOMMEND_V2_ENDPOINT;
};

/**
 * Build the POST body for /build/intelligence. The wire contract is
 * slot->hardware-id at the TOP LEVEL (BuildIntelligenceRequest has
 * extra="forbid"): a {"components": ...} wrapper is a 422.
 */
export const buildIntelligenceRequestBody = (components) => {
  const parsed = components || {};
  const body = {};
  for (const slot of [
    "cpu",
    "gpu",
    "ram",
    "storage",
    "motherboard",
    "psu",
  ]) {
    const value = parsed[slot];
    if (value == null) {
      continue;
    }
    /* Build config stores either a hardware id or the full detail object;
       the wire contract wants the id. */
    const id = typeof value === "object" ? value.id : value;
    if (id != null) {
      body[slot] = id;
    }
  }
  return body;
};

/**
 * Normalize one scenario entry. UNKNOWN (score null) is rendered honestly:
 * stars stay 0, `unknown` is true, and the limitation text names the gap.
 */
export const formatScenarioEntry = (key, entry) => {
  const score = typeof entry?.score === "number" ? entry.score : null;
  const unknown = score === null;
  const stars = unknown ? 0 : Math.max(0, Math.min(5, Number(entry?.stars ?? 0)));
  const confidence = entry?.confidence || (unknown ? "unknown" : "low");
  const limitations = Array.isArray(entry?.limitations)
    ? entry.limitations
    : [];
  const unknownText = unknown
    ? limitations.length
      ? limitations[0].replace(/[:_]+/g, " ").replace(/ — /g, ": ").trim()
      : "insufficient data"
    : "";

  return {
    key,
    label: SCENARIO_LABELS[key] || key,
    score,
    scoreLabel: score === null ? "Unknown" : String(score),
    stars,
    starsLabel: unknown ? "Unrated" : `${stars} out of 5 stars`,
    unknown,
    unknownText,
    confidence,
    confidenceBadge: unknown ? "confidence-unrated" : getConfidenceBadge(confidence),
    specBased: Boolean(entry?.spec_based),
    limitations,
    contributingFactors: Array.isArray(entry?.contributing_factors)
      ? entry.contributing_factors
      : [],
  };
};

/**
 * Normalize a full ScenarioSetResponse; scenarios keep canonical order.
 */
export const formatScenarioSet = (payload) => {
  const scenarios = payload?.scenarios || {};
  return {
    scoringVersion: payload?.scoring_version || null,
    referencePopulation: payload?.reference_population || "",
    dataCoverage: typeof payload?.data_coverage === "number"
      ? payload.data_coverage
      : null,
    scenarios: SCENARIO_ORDER.filter((key) => scenarios[key]).map((key) =>
      formatScenarioEntry(key, scenarios[key]),
    ),
  };
};

/**
 * Normalize one /hardware/recommend/v2 candidate.
 */
export const formatRecommendationV2Candidate = (candidate) => {
  const scenarioScores = candidate?.scenario_scores || {};
  const rank = typeof candidate?.rank === "number" ? candidate.rank : null;
  const evidence = candidate?.evidence || {};
  return {
    rank,
    hardwareId: candidate?.hardware_id ?? null,
    hardwareType: candidate?.hardware_type || null,
    name: candidate?.hardware_name || "",
    stars: Math.max(0, Math.min(5, Number(candidate?.stars ?? 0))),
    confidence: candidate?.confidence || "unknown",
    scenarios: SCENARIO_ORDER.filter((key) => scenarioScores[key]).map((key) =>
      formatScenarioEntry(key, scenarioScores[key]),
    ),
    explanation: Array.isArray(candidate?.rank_explanation)
      ? candidate.rank_explanation
      : [],
    tradeOffs: Array.isArray(candidate?.trade_offs) ? candidate.trade_offs : [],
    coverage: typeof evidence.coverage === "number" ? evidence.coverage : null,
    benchmarkFamilies: Array.isArray(evidence.benchmark_families)
      ? evidence.benchmark_families
      : [],
    profileLabel: formatProfileLabel(candidate?.profile_key),
  };
};
