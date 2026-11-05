import test from "node:test";
import assert from "node:assert/strict";

import {
  getRecommendationEndpoint,
  formatRecommendationCandidate,
} from "./recommendationDisplay.js";

test("getRecommendationEndpoint builds the recommend query", () => {
  const url = getRecommendationEndpoint("GPU", "gaming", 10);
  assert.equal(url, "/hardware/recommend?type=GPU&workload=gaming&limit=10");
});

test("getRecommendationEndpoint omits limit when not provided", () => {
  const url = getRecommendationEndpoint("CPU", "productivity");
  assert.equal(url, "/hardware/recommend?type=CPU&workload=productivity");
});

test("getRecommendationEndpoint appends budget when provided", () => {
  const url = getRecommendationEndpoint("GPU", "gaming", 5, 800);
  assert.equal(
    url,
    "/hardware/recommend?type=GPU&workload=gaming&limit=5&budget_max=800",
  );
});

test("formatRecommendationCandidate exposes stars and hardware name", () => {
  const formatted = formatRecommendationCandidate({
    hardware_id: 12,
    hardware_name: "NVIDIA RTX 5070 Ti",
    hardware_type: "GPU",
    suitability: {
      category: "gaming",
      stars: 4,
      confidence: "medium",
      spec_based: true,
      rationale: ["No driver/benchmark evidence; rating based on specs"],
      caveats: ["Spec-based, capped at 3 stars"],
    },
    explanation: ["Spec-based"],
  });
  assert.equal(formatted.id, 12);
  assert.equal(formatted.name, "NVIDIA RTX 5070 Ti");
  assert.equal(formatted.stars, 4);
  assert.equal(formatted.confidence, "medium");
  assert.equal(formatted.specBased, true);
  assert.equal(formatted.primaryRationale, "Spec-based");
  assert.ok(formatted.caveats.length >= 1);
});

test("formatRecommendationCandidate tolerates a raw response item", () => {
  const formatted = formatRecommendationCandidate({
    hardware_id: 1,
    hardware_name: "AMD Ryzen 9 7950X",
    hardware_type: "CPU",
    suitability: { stars: 5, confidence: "high", spec_based: false },
    explanation: [],
  });
  assert.equal(formatted.stars, 5);
  assert.equal(formatted.confidenceBadge, "confidence-high");
});
