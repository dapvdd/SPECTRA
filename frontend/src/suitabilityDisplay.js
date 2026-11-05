/**
 * Pure display/formatting logic for the Hardware Fit / suitability UI.
 *
 * Kept free of React so it runs under `node --test` like the rest of the
 * frontend. Components consume these helpers to render ratings without
 * encoding business rules in markup.
 */

export const CATEGORIES = [
  "gaming",
  "workstation",
  "productivity",
  "content_creation",
  "ai_ml",
];

/**
 * The suitability endpoint path for a hardware record. Centralized so the hook
 * and any tests agree on the exact contract.
 */
export const getSuitabilityEndpoint = (hardwareId) =>
  `/hardware/${hardwareId}/suitability`;

const CONFIDENCE_BADGES = {
  high: "confidence-high",
  medium: "confidence-medium",
  low: "confidence-low",
  unrated: "confidence-unrated",
};

export const getConfidenceBadge = (confidence) =>
  CONFIDENCE_BADGES[confidence] || "confidence-unknown";

/**
 * Normalize one suitability rating into display-ready fields the component
 * renders. Handles both rated (0-5 stars) and unrated states.
 */
export const formatSuitabilityRating = (rating) => {
  const stars = Number(rating?.stars ?? 0);
  const confidence = rating?.confidence || "low";
  const unrated = confidence === "unrated";

  const unratedText = rating?.unrated_reason
    ? rating.unrated_reason.replace(/[:_-]+/g, " ").trim()
    : "insufficient data";

  return {
    category: rating?.category || "unknown",
    stars,
    starsLabel: String(stars),
    starsAccessibleLabel: `${stars} out of 5 stars`,
    confidence,
    confidenceBadge: getConfidenceBadge(confidence),
    specBased: Boolean(rating?.spec_based),
    specBasedLabel: "Spec-based (no benchmark)",
    unrated,
    unratedText,
    rationale: Array.isArray(rating?.rationale) ? rating.rationale : [],
    caveats: Array.isArray(rating?.caveats) ? rating.caveats : [],
  };
};

/**
 * Summarize a full HardwareSuitabilityResponse.ratings array for the modal's
 * overview strip.
 */
export const getSuitabilitySummary = (ratings = []) => {
  const rated = ratings.filter((r) => r?.confidence !== "unrated");
  const best = rated.length
    ? rated.reduce(
        (a, b) => ((b?.stars ?? 0) > (a?.stars ?? 0) ? b : a),
        rated[0],
      )
    : null;

  return {
    ratedCount: rated.length,
    unratedCount: ratings.length - rated.length,
    bestCategory: best?.category || null,
    bestStars: best?.stars ?? 0,
  };
};
