import { getPerformanceState } from "./performance.js";

export const COMPARISON_METRICS = [
  {
    key: "multi_core",
    label: "Geekbench 7 Multi-Core",
    direction: "higher",
    source: "benchmark",
    unit: "points",
    format: "integer",
  },
  {
    key: "single_core",
    label: "Geekbench 7 Single-Core",
    direction: "higher",
    source: "benchmark",
    unit: "points",
    format: "integer",
  },
  {
    key: "cores",
    label: "Cores",
    direction: "higher",
    source: "specification",
    unit: "",
    format: "integer",
  },
  {
    key: "threads",
    label: "Threads",
    direction: "higher",
    source: "specification",
    unit: "",
    format: "integer",
  },
  {
    key: "boost_clock_ghz",
    label: "Boost Clock",
    direction: "higher",
    source: "specification",
    unit: "GHz",
    format: "decimal",
  },
  {
    key: "base_clock_ghz",
    label: "Base Clock",
    direction: "higher",
    source: "specification",
    unit: "GHz",
    format: "decimal",
  },
  {
    key: "tdp_w",
    label: "TDP",
    direction: "lower",
    source: "specification",
    unit: "W",
    format: "integer",
  },
];

const emptyInsights = () => ({
  measurableCount: 0,
  wins: { cpuA: 0, cpuB: 0 },
  ties: 0,
  insights: [],
  tieDetails: [],
  unavailableMetrics: [],
  pendingMetrics: [],
});

const getMetricDefinition = (metricKey) =>
  COMPARISON_METRICS.find((metric) => metric.key === metricKey);

export const isValidComparisonValue = (value) =>
  typeof value === "number" && Number.isFinite(value) && value > 0;

export const getComparisonWinner = (firstValue, secondValue, direction) => {
  if (
    !isValidComparisonValue(firstValue) ||
    !isValidComparisonValue(secondValue)
  ) {
    return null;
  }

  if (firstValue === secondValue) {
    return "tie";
  }

  if (direction === "lower") {
    return firstValue < secondValue ? "cpuA" : "cpuB";
  }

  return firstValue > secondValue ? "cpuA" : "cpuB";
};

const getSpecificationValue = (hardware, metric) =>
  hardware?.specifications?.[metric.key];

const getBenchmarkValue = (benchmarkState, metric) => {
  const performanceState = getPerformanceState(benchmarkState);
  return performanceState.results[metric.key]?.score;
};

export const getComparisonMetricValue = (hardware, metric, benchmarkState) =>
  metric.source === "benchmark"
    ? getBenchmarkValue(benchmarkState, metric)
    : getSpecificationValue(hardware, metric);

const getMetricStatus = (metric, benchmarkState) => {
  if (metric.source !== "benchmark") {
    return "ready";
  }

  if (benchmarkState?.status === "loading") {
    return "pending";
  }

  return "ready";
};

const roundPercentage = (value) => Math.round((value + Number.EPSILON) * 10) / 10;

const getDifferencePercent = (winnerValue, loserValue, direction) => {
  const difference =
    direction === "lower"
      ? ((loserValue - winnerValue) / loserValue) * 100
      : ((winnerValue - loserValue) / loserValue) * 100;

  return roundPercentage(difference);
};

export const calculateComparisonInsights = (
  compareDetails,
  benchmarkStates = {}
) => {
  if (!Array.isArray(compareDetails) || compareDetails.length !== 2) {
    return emptyInsights();
  }

  const [cpuA, cpuB] = compareDetails;
  const result = emptyInsights();

  for (const metric of COMPARISON_METRICS) {
    const benchmarkStateA = benchmarkStates[cpuA.id];
    const benchmarkStateB = benchmarkStates[cpuB.id];
    const statusA = getMetricStatus(metric, benchmarkStateA);
    const statusB = getMetricStatus(metric, benchmarkStateB);

    if (statusA === "pending" || statusB === "pending") {
      result.pendingMetrics.push(metric);
      continue;
    }

    const valueA = getComparisonMetricValue(cpuA, metric, benchmarkStateA);
    const valueB = getComparisonMetricValue(cpuB, metric, benchmarkStateB);
    const winner = getComparisonWinner(valueA, valueB, metric.direction);

    if (!winner) {
      result.unavailableMetrics.push(metric);
      continue;
    }

    result.measurableCount += 1;

    if (winner === "tie") {
      result.ties += 1;
      result.tieDetails.push({
        metric: metric.label,
        metricKey: metric.key,
        value: valueA,
        unit: metric.unit,
        format: metric.format,
      });
      continue;
    }

    const winnerValue = winner === "cpuA" ? valueA : valueB;
    const loserValue = winner === "cpuA" ? valueB : valueA;
    result.wins[winner] += 1;
    result.insights.push({
      metric: metric.label,
      metricKey: metric.key,
      winner,
      winnerName: winner === "cpuA" ? cpuA.name : cpuB.name,
      differencePercent: getDifferencePercent(
        winnerValue,
        loserValue,
        metric.direction
      ),
      winnerValue,
      loserValue,
      direction: metric.direction,
      unit: metric.unit,
      format: metric.format,
    });
  }

  return result;
};

const getFactWinner = (winner) => {
  if (winner === "cpuA") {
    return "cpu_a";
  }

  if (winner === "cpuB") {
    return "cpu_b";
  }

  return "tie";
};

export const buildComparisonFacts = (compareDetails, benchmarkStates = {}) => {
  if (!Array.isArray(compareDetails) || compareDetails.length !== 2) {
    return null;
  }

  const [cpuA, cpuB] = compareDetails;
  const insights = calculateComparisonInsights(compareDetails, benchmarkStates);
  const facts = {
    cpu_a: {
      name: cpuA.name,
      manufacturer: cpuA.manufacturer,
    },
    cpu_b: {
      name: cpuB.name,
      manufacturer: cpuB.manufacturer,
    },
    metrics: insights.insights.map((insight) => {
      const metric = getMetricDefinition(insight.metricKey);
      const valueA = insight.winner === "cpuA" ? insight.winnerValue : insight.loserValue;
      const valueB = insight.winner === "cpuB" ? insight.winnerValue : insight.loserValue;

      return {
        metric_key: insight.metricKey,
        name: insight.metric,
        value_a: valueA,
        value_b: valueB,
        unit: insight.unit,
        source: metric.source,
        direction: insight.direction,
        winner: getFactWinner(insight.winner),
        difference_percent: insight.differencePercent,
      };
    }),
    ties: insights.tieDetails.map((tie) => {
      const metric = getMetricDefinition(tie.metricKey);

      return {
        metric_key: tie.metricKey,
        name: tie.metric,
        value_a: tie.value,
        value_b: tie.value,
        unit: tie.unit,
        source: metric.source,
        direction: metric.direction,
        winner: "tie",
        difference_percent: 0,
      };
    }),
    unavailable_metrics: [
      ...insights.unavailableMetrics.map((metric) => ({
        metric_key: metric.key,
        name: metric.label,
        source: metric.source,
        reason: "unavailable",
      })),
      ...insights.pendingMetrics.map((metric) => ({
        metric_key: metric.key,
        name: metric.label,
        source: metric.source,
        reason: "pending",
      })),
    ],
  };

  return facts;
};
