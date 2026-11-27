/**
 * M4 Task 7 tests: intelligence display layer (pure functions, node --test).
 * Covers scenarioRatings.js formatting, profile metadata, and the
 * recommendation v2 endpoint builder — including honest UNKNOWN handling.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  PROFILES,
  WORKLOAD_PROFILE_KEYS,
  formatProfileLabel,
  formatWorkloadProfile,
} from "./intelligenceDisplay.js";
import {
  RECOMMEND_V2_ENDPOINT,
  BUILD_INTELLIGENCE_ENDPOINT,
  getRecommendationV2Endpoint,
  buildIntelligenceRequestBody,
  formatRecommendationV2Candidate,
  formatScenarioEntry,
  formatScenarioSet,
  SCENARIO_LABELS,
  CONSTRAINT_CLASSIFICATIONS,
} from "./recommendationV2.js";

// ---------------------------------------------------------------- profiles --

test("eight workload profiles with stable keys and labels", () => {
  assert.equal(WORKLOAD_PROFILE_KEYS.length, 8);
  for (const key of WORKLOAD_PROFILE_KEYS) {
    const profile = formatWorkloadProfile(PROFILES[key]);
    assert.ok(profile.label.length > 0);
    assert.ok(Array.isArray(profile.assumptions));
    assert.ok(profile.assumptions.length >= 2);
  }
});

test("formatProfileLabel falls back for unknown keys", () => {
  assert.equal(formatProfileLabel("software_development"), "Software development");
  assert.equal(formatProfileLabel("not_a_profile"), "not_a_profile");
});

// ------------------------------------------------------- scenario entries ---

test("formatScenarioEntry renders scored scenarios with confidence", () => {
  const entry = formatScenarioEntry("gaming", {
    score: 3.42, stars: 3, confidence: "high", spec_based: false,
    limitations: [], contributing_factors: [
      { feature: "multi_core_score", weight: 0.5, present: true },
    ],
  });
  assert.equal(entry.stars, 3);
  assert.equal(entry.confidence, "high");
  assert.equal(entry.specBased, false);
  assert.equal(entry.label, SCENARIO_LABELS.gaming);
});

test("formatScenarioEntry renders UNKNOWN honestly, never as zero stars", () => {
  const entry = formatScenarioEntry("value", {
    score: null, stars: 0, confidence: "unknown",
    limitations: ["missing_data:price — no price data in this dataset"],
    contributing_factors: [],
  });
  assert.equal(entry.unknown, true);
  assert.equal(entry.stars, 0);
  assert.ok(entry.unknownText.includes("price"));
  assert.equal(entry.confidenceBadge, "confidence-unrated");
});

test("formatScenarioEntry keeps limitations for spec-based scores", () => {
  const entry = formatScenarioEntry("gaming", {
    score: 2.5, stars: 3, confidence: "medium", spec_based: true,
    limitations: ["spec_based: capped at 3.0"],
  });
  assert.equal(entry.specBased, true);
  assert.ok(entry.limitations.length === 1);
});

// ------------------------------------------------------------ scenario set --

test("formatScenarioSet orders scenarios canonically", () => {
  const set = formatScenarioSet({
    scoring_version: "M4-SCORING-v2.0",
    reference_population: "Geekbench 7 ...",
    data_coverage: 0.8,
    scenarios: {
      value: { score: null, confidence: "unknown", stars: 0, limitations: [] },
      gaming: { score: 4.0, confidence: "high", stars: 4, limitations: [] },
      daily: { score: 2.0, confidence: "medium", stars: 2, limitations: [] },
      workstation: { score: 3.0, confidence: "medium", stars: 3, limitations: [] },
    },
  });
  assert.deepEqual(
    set.scenarios.map((s) => s.key),
    ["gaming", "workstation", "daily", "value"],
  );
  assert.equal(set.dataCoverage, 0.8);
});

// ---------------------------------------------------- build intelligence ----

test("buildIntelligenceRequestBody sends slots at top level (no wrapper)", () => {
  const body = buildIntelligenceRequestBody({
    cpu: 101,
    gpu: null,
    motherboard: null,
    ram: null,
    storage: null,
    psu: null,
  });
  assert.deepEqual(body, { cpu: 101 });
});

test("buildIntelligenceRequestBody keeps every selected slot", () => {
  const body = buildIntelligenceRequestBody({
    cpu: 101,
    gpu: 300,
    motherboard: 920,
    ram: null,
    storage: null,
    psu: null,
  });
  assert.deepEqual(body, { cpu: 101, gpu: 300, motherboard: 920 });
});

// --------------------------------------------------------- recommend v2 -----

test("getRecommendationV2Endpoint builds query params", () => {
  const endpoint = getRecommendationV2Endpoint({
    hardwareType: "CPU",
    profileKey: "software_development",
    limit: 5,
  });
  assert.ok(endpoint.startsWith(RECOMMEND_V2_ENDPOINT + "?"));
  assert.ok(endpoint.includes("type=CPU"));
  assert.ok(endpoint.includes("profile_key=software_development"));
  assert.ok(endpoint.includes("limit=5"));
});

test("getRecommendationV2Endpoint omits unset params", () => {
  const endpoint = getRecommendationV2Endpoint({ hardwareType: "GPU" });
  assert.equal(endpoint, `${RECOMMEND_V2_ENDPOINT}?type=GPU`);
});

test("buildIntelligenceRequestBody normalizes full hardware objects to ids", () => {
  const body = buildIntelligenceRequestBody({
    cpu: { id: 1, name: "AMD Athlon Gold 7220C", type: "CPU" },
    gpu: { id: 300, name: "GPU X", specifications: {} },
    motherboard: null,
    ram: null,
    storage: null,
    psu: null,
  });
  assert.deepEqual(body, { cpu: 1, gpu: 300 });
});

test("formatRecommendationV2Candidate normalizes rank + scenario scores", () => {
  const formatted = formatRecommendationV2Candidate({
    rank: 1, hardware_id: 42, hardware_name: "CPU X",
    scenario_scores: {
      gaming: { score: 4.1, stars: 4, confidence: "high", spec_based: false, limitations: [] },
      value: { score: null, stars: 0, confidence: "unknown", limitations: ["no price"] },
    },
    stars: 4, confidence: "high",
    rank_explanation: ["weighted scenario score 3.8"],
    trade_offs: ["value unknown: no price data in this dataset"],
    evidence: { coverage: 0.9, benchmark_families: ["multi-core"] },
  });
  assert.equal(formatted.rank, 1);
  assert.equal(formatted.name, "CPU X");
  assert.equal(formatted.scenarios.length, 2);
  assert.equal(formatted.scenarios[0].key, "gaming");
  assert.equal(formatted.explanation.length, 1);
  assert.equal(formatted.tradeOffs.length, 1);
  assert.equal(formatted.coverage, 0.9);
});

test("formatRecommendationV2Candidate tolerates missing fields", () => {
  const formatted = formatRecommendationV2Candidate({ hardware_id: 7 });
  assert.equal(formatted.rank, null);
  assert.equal(formatted.scenarios.length, 0);
  assert.equal(formatted.coverage, null);
});

// ------------------------------------------------------------ constraints ---

test("constraint classification vocabulary is closed", () => {
  assert.deepEqual(CONSTRAINT_CLASSIFICATIONS, ["hard", "soft", "unknown", "estimated"]);
});
