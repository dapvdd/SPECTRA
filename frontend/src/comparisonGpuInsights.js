// Maps the backend GPU comparison verdict (POST /comparison/gpu) into the
// comparison-insight shape the ComparisonInsights renderer consumes. The
// backend is the single source of truth for whose value is higher/lower; this
// layer is presentational only (labels, units, and difference percentages
// derived from the two recorded values).
import { GPU_METRICS } from "./comparison.js";

const WIRE_TO_INSIGHT_SIDE = {
  a: "cpuA",
  b: "cpuB",
};

const roundPercentage = (value) =>
  Math.round((value + Number.EPSILON) * 10) / 10;

// The winner side for a metric is decided by the backend. The percentage is
// derived from the two recorded values, relative to the loser value, so it
// matches the client-side convention (a positive % either "higher" or "lower").
const getDifferencePercent = (winnerSide, valueA, valueB, direction) => {
  if (!Number.isFinite(valueA) || !Number.isFinite(valueB) || valueA === valueB) {
    return 0;
  }

  const winnerValue = winnerSide === "cpuA" ? valueA : valueB;
  const loserValue = winnerSide === "cpuA" ? valueB : valueA;

  if (loserValue === 0 || !Number.isFinite(loserValue)) {
    return 0;
  }

  return roundPercentage(
    direction === "lower"
      ? ((loserValue - winnerValue) / loserValue) * 100
      : ((winnerValue - loserValue) / loserValue) * 100
  );
};

const getMetricDefinition = (metricKey) =>
  GPU_METRICS.find((metric) => metric.key === metricKey);

export const buildEmptyGpuInsights = () => ({
  measurableCount: 0,
  wins: { cpuA: 0, cpuB: 0 },
  ties: 0,
  insights: [],
  tieDetails: [],
  unavailableMetrics: [],
  pendingMetrics: [],
});

export const buildGpuInsightsFromStatus = (
  status,
  payload,
  compareDetails,
  loadingDefinitions = null,
) => {
  if (status === "success") {
    return buildGpuInsightsFromBackend(payload, compareDetails);
  }

  const empty = buildEmptyGpuInsights();
  if (status === "loading" && Array.isArray(loadingDefinitions)) {
    return { ...empty, pendingMetrics: loadingDefinitions };
  }

  return empty;
};

export const buildGpuInsightsFromBackend = (payload, compareDetails) => {
  const empty = buildEmptyGpuInsights();

  if (!Array.isArray(payload?.metrics)) {
    return empty;
  }

  const [gpuA, gpuB] = compareDetails ?? [];
  const unavailableMetrics = [];
  const insights = [];
  const tieDetails = [];
  const wins = { cpuA: 0, cpuB: 0 };
  let ties = 0;
  let measurableCount = 0;

  for (const metric of payload.metrics) {
    const definition = getMetricDefinition(metric.name);

    if (!definition) {
      continue;
    }

    const valueA = metric.value_a ?? null;
    const valueB = metric.value_b ?? null;

    if (metric.winner === "unavailable") {
      unavailableMetrics.push(definition);
      continue;
    }

    if (metric.winner === "tie") {
      measurableCount += 1;
      ties += 1;
      tieDetails.push({
        metric: definition.label,
        metricKey: definition.key,
        value: valueA,
        unit: definition.unit,
        format: definition.format,
      });
      continue;
    }

    const side = WIRE_TO_INSIGHT_SIDE[metric.winner];

    if (side !== "cpuA" && side !== "cpuB") {
      continue;
    }

    measurableCount += 1;
    wins[side] += 1;

    insights.push({
      metric: definition.label,
      metricKey: definition.key,
      winner: side,
      winnerName: side === "cpuA" ? gpuA?.name : gpuB?.name,
      differencePercent: getDifferencePercent(
        side,
        valueA,
        valueB,
        definition.direction
      ),
      winnerValue: side === "cpuA" ? valueA : valueB,
      loserValue: side === "cpuA" ? valueB : valueA,
      direction: definition.direction,
      unit: definition.unit,
      format: definition.format,
    });
  }

  return {
    ...empty,
    measurableCount,
    wins,
    ties,
    insights,
    tieDetails,
    unavailableMetrics,
  };
};
