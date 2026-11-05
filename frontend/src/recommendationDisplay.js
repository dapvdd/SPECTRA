/**
 * Pure display/request logic for the Hardware Fit modal's recommendation
 * feature (Objective E). Free of React so it runs under `node --test`.
 */

import { getConfidenceBadge } from "./suitabilityDisplay.js";

export const RECOMMEND_ENDPOINT = "/hardware/recommend";

/**
 * Build the recommend endpoint path with query params for the workload.
 * `budget_max` is included only when provided: the backend accepts it but this
 * dataset has no pricing data, so it is informational only.
 */
export const getRecommendationEndpoint = (
  hardwareType,
  workload,
  limit,
  budgetMax,
) => {
  const params = new URLSearchParams();
  if (workload) {
    params.set("type", hardwareType);
    params.set("workload", workload);
  }
  if (typeof limit === "number" && Number.isFinite(limit)) {
    params.set("limit", String(limit));
  }
  if (
    typeof budgetMax === "number" &&
    Number.isFinite(budgetMax)
  ) {
    params.set("budget_max", String(budgetMax));
  }
  const query = params.toString();
  return query ? `${RECOMMEND_ENDPOINT}?${query}` : RECOMMEND_ENDPOINT;
};

/**
 * Normalize one recommend response candidate into display-ready fields.
 * Handles both the full object and the star count without assuming structure.
 */
export const formatRecommendationCandidate = (candidate) => {
  const suitability = candidate?.suitability || {};
  const stars = Number(suitability.stars ?? 0);
  const confidence = suitability.confidence || "low";
  const specBased = Boolean(suitability.spec_based);
  const caveats = Array.isArray(suitability.caveats)
    ? suitability.caveats
    : [];
  const explanation = Array.isArray(candidate?.explanation)
    ? candidate.explanation
    : [];

  return {
    id: candidate?.hardware_id ?? 0,
    name: candidate?.hardware_name || "Unknown hardware",
    type: candidate?.hardware_type || "Unknown",
    stars,
    starsLabel: String(stars),
    starsAccessibleLabel: `${stars} out of 5 stars`,
    confidence,
    confidenceBadge: getConfidenceBadge(confidence),
    specBased,
    specBasedLabel: "Spec-based (no benchmark)",
    caveats,
    primaryRationale:
      explanation[0] ??
      (Array.isArray(suitability.rationale) ? suitability.rationale[0] : "") ??
      "",
  };
};

/**
 * Build the presentation list of recommendation candidates, sorting by stars
 * descending (the backend already ranks, this is a defensive re-sort).
 */
export const getRecommendationCandidates = (candidates = []) =>
  [...candidates].sort((a, b) => {
    const aStars = a?.suitability?.stars ?? 0;
    const bStars = b?.suitability?.stars ?? 0;
    if (aStars !== bStars) {
      return bStars - aStars;
    }
    return (a?.hardware_id ?? 0) - (b?.hardware_id ?? 0);
  });
