import test from "node:test";
import assert from "node:assert/strict";

import {
  CATEGORIES,
  getSuitabilitySummary,
  formatSuitabilityRating,
  getSuitabilityEndpoint,
} from "./suitabilityDisplay.js";

test("suitability exposes the five supported workload categories", () => {
  assert.deepEqual(CATEGORIES, [
    "gaming",
    "workstation",
    "productivity",
    "content_creation",
    "ai_ml",
  ]);
});

test("getSuitabilityEndpoint matches the backend route contract", () => {
  assert.equal(getSuitabilityEndpoint(7), "/hardware/7/suitability");
});

test("formatSuitabilityRating renders stars for a rated category", () => {
  const display = formatSuitabilityRating({
    category: "gaming",
    stars: 4,
    raw_score: 4.0,
    confidence: "medium",
    spec_based: false,
    rationale: ["Benchmark evidence present"],
    caveats: [],
  });
  assert.equal(display.starsLabel, "4");
  assert.equal(display.starsAccessibleLabel, "4 out of 5 stars");
  assert.equal(display.confidenceBadge, "confidence-medium");
  assert.equal(display.specBased, false);
  assert.equal(display.unrated, false);
});

test("formatSuitabilityRating flags unrated with a human reason", () => {
  const display = formatSuitabilityRating({
    category: "ai_ml",
    stars: 0,
    raw_score: 0,
    confidence: "unrated",
    spec_based: false,
    rationale: [],
    caveats: ["insufficient_data: no GPU/VRAM benchmark evidence"],
    unrated_reason: "insufficient_data:no_gpu_benchmarks",
  });
  assert.equal(display.unrated, true);
  assert.match(display.unratedText, /insufficient data/i);
  assert.equal(display.starsLabel, "0");
});

test("formatSuitabilityRating marks spec-based ratings clearly", () => {
  const display = formatSuitabilityRating({
    category: "gaming",
    stars: 3,
    raw_score: 3.0,
    confidence: "low",
    spec_based: true,
    rationale: [],
    caveats: ["Spec-based, capped at 3 stars"],
  });
  assert.equal(display.specBased, true);
  assert.equal(display.specBasedLabel, "Spec-based (no benchmark)");
});

test("getSuitabilitySummary counts rated vs unrated categories", () => {
  const ratings = [
    { category: "gaming", confidence: "medium", stars: 4 },
    { category: "productivity", confidence: "low", stars: 2 },
    { category: "ai_ml", confidence: "unrated", stars: 0 },
  ];
  const summary = getSuitabilitySummary(ratings);
  assert.equal(summary.ratedCount, 2);
  assert.equal(summary.unratedCount, 1);
  assert.equal(summary.bestCategory, "gaming");
});

test("fallback text for an unknown confidence", () => {
  const display = formatSuitabilityRating({
    category: "workstation",
    stars: 3,
    raw_score: 3,
    confidence: "low",
    spec_based: false,
    rationale: [],
    caveats: [],
  });
  assert.equal(display.confidenceBadge, "confidence-low");
});
