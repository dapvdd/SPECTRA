import {
  calculateComparisonInsights,
  getComparisonMetrics,
} from "./comparison.js";
import { getPerformanceState } from "./performance.js";

const getMetricDefinition = (metricKey, hardwareType) =>
  getComparisonMetrics(hardwareType).find((metric) => metric.key === metricKey);

const emptyEvidenceGroup = () => ({
  wins: { cpuA: 0, cpuB: 0 },
  ties: 0,
  measurableCount: 0,
  metrics: [],
  tieDetails: [],
});

const partitionInsightsBySource = (insights, hardwareType) => {
  const benchmark = emptyEvidenceGroup();
  const specification = emptyEvidenceGroup();

  for (const insight of insights.insights) {
    const metricDef = getMetricDefinition(insight.metricKey, hardwareType);
    const group = metricDef?.source === "benchmark" ? benchmark : specification;

    group.wins[insight.winner] += 1;
    group.measurableCount += 1;
    group.metrics.push({
      key: insight.metricKey,
      label: insight.metric,
      winner: insight.winner,
      winnerName: insight.winnerName,
      differencePercent: insight.differencePercent,
      direction: insight.direction,
      unit: insight.unit,
      format: insight.format,
    });
  }

  for (const tie of insights.tieDetails) {
    const metricDef = getMetricDefinition(tie.metricKey, hardwareType);
    const group = metricDef?.source === "benchmark" ? benchmark : specification;

    group.ties += 1;
    group.measurableCount += 1;
    group.tieDetails.push({
      key: tie.metricKey,
      label: tie.metric,
      value: tie.value,
      unit: tie.unit,
      format: tie.format,
    });
  }

  return { benchmark, specification };
};

const getBenchmarkCoverage = (compareDetails, benchmarkStates) => {
  const coverage = compareDetails.map((hardware) => {
    const state = benchmarkStates?.[hardware.id];
    const performanceState = getPerformanceState(state);
    const hasData = performanceState.status === "available" || performanceState.status === "partial";
    const scoreCount = Object.keys(performanceState.results).length;

    return {
      id: hardware.id,
      name: hardware.name,
      hasData,
      scoreCount,
      status: performanceState.status,
    };
  });

  const withData = coverage.filter((item) => item.hasData).length;
  const total = coverage.length;

  return {
    coverage,
    withData,
    total,
    isPartial: withData > 0 && withData < total,
    isNone: withData === 0,
    isComplete: withData === total,
  };
};

export const buildComparisonEvidence = (
  compareDetails,
  benchmarkStates = {}
) => {
  if (!Array.isArray(compareDetails) || compareDetails.length !== 2) {
    return null;
  }

  const [cpuA] = compareDetails;
  const metrics = getComparisonMetrics(cpuA?.type);
  const insights = calculateComparisonInsights(compareDetails, benchmarkStates);
  const { benchmark, specification } = partitionInsightsBySource(insights, cpuA?.type);
  const benchmarkCoverage = getBenchmarkCoverage(compareDetails, benchmarkStates);

  const benchmarkMetrics = metrics.filter((metric) => metric.source === "benchmark");
  const specMetrics = metrics.filter((metric) => metric.source !== "benchmark");

  const benchmarkUnavailable = insights.unavailableMetrics.filter(
    (metric) => metric.source === "benchmark"
  );
  const specUnavailable = insights.unavailableMetrics.filter(
    (metric) => metric.source !== "benchmark"
  );

  return {
    benchmark: {
      ...benchmark,
      label: "Measured benchmarks",
      metricCount: benchmarkMetrics.length,
      unavailable: benchmarkUnavailable,
      coverage: benchmarkCoverage,
    },
    specification: {
      ...specification,
      label: "Specifications",
      metricCount: specMetrics.length,
      unavailable: specUnavailable,
    },
  };
};
