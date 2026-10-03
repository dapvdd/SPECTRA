import {
  GPU_TABLE_SPECS,
  calculateComparisonInsights,
  getComparisonMetricValue,
  getComparisonMetrics,
  getComparisonWinner,
  getComparisonWinnerClass,
  isValidComparisonValue,
} from "./comparison.js";
import { formatDetailValue } from "./detail.js";
import { formatReleaseDate } from "./hardwareCard.js";

export const COMPARISON_SIDES = ["cpuA", "cpuB"];

export const DECISION_STATUS = {
  empty: "empty",
  loading: "loading",
  ready: "ready",
};

export const AVAILABILITY_STATUS = {
  loading: "loading",
  complete: "complete",
  partial: "partial",
  unavailable: "unavailable",
};

export const CPU_TABLE_SPECS = [
  { key: "cores", label: "Cores", unit: "", direction: "higher" },
  { key: "threads", label: "Threads", unit: "", direction: "higher" },
  { key: "base_clock_ghz", label: "Base Clock", unit: "GHz", direction: "higher" },
  { key: "boost_clock_ghz", label: "Boost Clock", unit: "GHz", direction: "higher" },
  { key: "tdp_w", label: "TDP", unit: "W", direction: "lower" },
  { key: "process_node_nm", label: "Process Node", unit: "nm" },
  { key: "socket", label: "Socket", unit: "" },
];

export const COMPARISON_COMPLETENESS_LABELS = {
  loading: "LOADING VERIFIED DATA",
  complete: "COMPLETE DATA",
  partial: "PARTIAL DATA",
  unavailable: "NOT COMPARABLE YET",
};

export const BENCHMARK_SUPPORT_LABELS = {
  loading: "LOADING",
  available: "VERIFIED DATA",
  partial: "PARTIAL DATA",
  unavailable: "NO DATA",
};

const isComparablePair = (compareDetails) =>
  Array.isArray(compareDetails) && compareDetails.length === 2;

const pluralizeMetrics = (count) => `${count} ${count === 1 ? "metric" : "metrics"}`;

const formatMetricValue = (value, format, unit) => {
  const formatted =
    format === "integer"
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

  return unit ? `${formatted} ${unit}` : formatted;
};

const formatDifferenceLabel = (differencePercent, direction) =>
  `${direction === "lower" ? "" : "+"}${differencePercent.toFixed(1)}% ${
    direction === "lower" ? "lower" : "higher"
  }`;

const getMetricValuesBySide = (compareDetails, metrics, benchmarkStates) =>
  compareDetails.map((hardware) => {
    const benchmarkState = benchmarkStates?.[hardware?.id];

    return metrics.reduce((values, metric) => {
      values[metric.key] = getComparisonMetricValue(
        hardware,
        metric,
        benchmarkState
      );
      return values;
    }, {});
  });

export const buildComparisonOverview = (compareDetails) => {
  if (!isComparablePair(compareDetails)) {
    return null;
  }

  const [first, second] = compareDetails;
  const slotType = first?.type || null;
  const noun = slotType || "hardware";
  const manufacturers = [first?.manufacturer, second?.manufacturer].filter(
    (manufacturer) => typeof manufacturer === "string" && manufacturer !== ""
  );

  return {
    slotType,
    noun,
    heading: slotType ? `${slotType} Comparison` : "Compare Hardware",
    headline: `${first?.name ?? "N/A"} vs ${second?.name ?? "N/A"}`,
    subhead:
      manufacturers.length === 2
        ? `${noun} comparison · ${manufacturers[0]} vs ${manufacturers[1]}`
        : `${noun} comparison`,
    participants: compareDetails.map((hardware, index) => ({
      side: COMPARISON_SIDES[index],
      name: hardware?.name ?? "N/A",
      manufacturer: hardware?.manufacturer ?? "N/A",
      type: hardware?.type ?? "N/A",
    })),
  };
};

const buildSourceAvailability = (definitions, valuesBySide) => {
  const missing = [];
  const metrics = [];
  let presentCount = 0;

  for (const metric of definitions) {
    const values = valuesBySide.map((sideValues) => sideValues[metric.key]);
    const availableValueCount = values.filter(isValidComparisonValue).length;
    const isMeasurable = availableValueCount === values.length;

    metrics.push({
      key: metric.key,
      label: metric.label,
      availableValueCount,
      isMeasurable,
    });

    if (isMeasurable) {
      presentCount += 1;
    } else {
      missing.push({ key: metric.key, label: metric.label });
    }
  }

  const expectedCount = definitions.length;

  return {
    expectedCount,
    presentCount,
    metrics,
    missing,
    missingLabels: missing.map((metric) => metric.label),
    status:
      expectedCount === 0 || presentCount === 0
        ? AVAILABILITY_STATUS.unavailable
        : presentCount === expectedCount
          ? AVAILABILITY_STATUS.complete
          : AVAILABILITY_STATUS.partial,
  };
};

const getBenchmarkSupportStatus = (availability) => {
  if (availability.isLoading) {
    return "loading";
  }

  if (availability.benchmark.presentCount === 0) {
    return "unavailable";
  }

  return availability.benchmark.status === AVAILABILITY_STATUS.complete
    ? "available"
    : "partial";
};

export const buildComparisonAvailability = (
  compareDetails,
  benchmarkStates = {}
) => {
  const overview = buildComparisonOverview(compareDetails);

  if (!overview) {
    return null;
  }

  const metrics = getComparisonMetrics(compareDetails[0]?.type);
  const benchmarkDefinitions = metrics.filter(
    (metric) => metric.source === "benchmark"
  );
  const specificationDefinitions = metrics.filter(
    (metric) => metric.source !== "benchmark"
  );
  const valuesBySide = getMetricValuesBySide(
    compareDetails,
    metrics,
    benchmarkStates
  );

  const benchmark = buildSourceAvailability(benchmarkDefinitions, valuesBySide);
  const specification = buildSourceAvailability(
    specificationDefinitions,
    valuesBySide
  );
  const isLoading = compareDetails.some(
    (hardware) => benchmarkStates?.[hardware?.id]?.status === "loading"
  );
  const totalExpected = benchmark.expectedCount + specification.expectedCount;
  const totalPresent = benchmark.presentCount + specification.presentCount;

  const completeness =
    totalPresent === 0
      ? AVAILABILITY_STATUS.unavailable
      : totalPresent === totalExpected
        ? AVAILABILITY_STATUS.complete
        : AVAILABILITY_STATUS.partial;

  const notes = [];

  if (isLoading) {
    notes.push("Verified benchmark data is still loading.");
  }

  if (overview.slotType === "GPU" && benchmark.expectedCount === 0) {
    notes.push("GPU benchmark scores are not collected for these GPUs yet.");
  }

  if (benchmark.missingLabels.length > 0) {
    notes.push(
      `${pluralizeMetrics(
        benchmark.missingLabels.length
      )} could not be compared because verified benchmark data is unavailable: ${benchmark.missingLabels.join(
        ", "
      )}.`
    );
  }

  if (specification.missingLabels.length > 0) {
    notes.push(
      `${pluralizeMetrics(
        specification.missingLabels.length
      )} could not be compared because specification data is unavailable: ${specification.missingLabels.join(
        ", "
      )}.`
    );
  }

  if (notes.length === 0) {
    notes.push(
      "Every supported metric has a verified value for both sides of this comparison."
    );
  }

  return {
    isLoading,
    completeness,
    statusLabel: isLoading
      ? COMPARISON_COMPLETENESS_LABELS.loading
      : COMPARISON_COMPLETENESS_LABELS[completeness],
    measurableCount: totalPresent,
    totalCount: totalExpected,
    benchmark,
    specification,
    notes,
  };
};

export const buildComparisonLeadGroups = (insights, compareDetails) => {
  const names = {
    cpuA: compareDetails?.[0]?.name,
    cpuB: compareDetails?.[1]?.name,
  };
  const groups = new Map();

  for (const insight of insights?.insights ?? []) {
    if (!groups.has(insight.winner)) {
      groups.set(insight.winner, {
        winner: insight.winner,
        winnerName: names[insight.winner],
        count: 0,
        metrics: [],
      });
    }

    const group = groups.get(insight.winner);
    group.count += 1;
    group.metrics.push({
      key: insight.metricKey,
      label: insight.metric,
      differenceLabel: formatDifferenceLabel(
        insight.differencePercent,
        insight.direction
      ),
    });
  }

  return {
    groups: [...groups.values()],
    tieCount: insights?.ties ?? 0,
    ties: (insights?.tieDetails ?? []).map((tie) => ({
      key: tie.metricKey,
      label: tie.metric,
      valueLabel: formatMetricValue(tie.value, tie.format, tie.unit),
    })),
  };
};

const buildLeadLines = (lead, measurableCount) => {
  const lines = lead.groups.map(
    (group) =>
      `${group.winnerName ?? "One side"} leads in ${group.count} of ${measurableCount} measurable metrics.`
  );

  if (lines.length === 0 && measurableCount > 0) {
    lines.push(`All ${measurableCount} measurable metrics are tied.`);
  }

  return lines;
};

export const buildComparisonDecisionSummary = (
  compareDetails,
  benchmarkStates = {}
) => {
  const overview = buildComparisonOverview(compareDetails);

  if (!overview) {
    return {
      status: DECISION_STATUS.empty,
      overview: null,
      availability: null,
      benchmarkSupport: null,
      lead: { groups: [], tieCount: 0, ties: [] },
      measurableCount: 0,
      tieCount: 0,
      unavailableCount: 0,
      canCompare: false,
      leadLines: [],
      limitations: [],
    };
  }

  const insights = calculateComparisonInsights(compareDetails, benchmarkStates);
  const availability = buildComparisonAvailability(
    compareDetails,
    benchmarkStates
  );
  const benchmarkStatus = getBenchmarkSupportStatus(availability);
  const lead = buildComparisonLeadGroups(insights, compareDetails);

  return {
    status: availability.isLoading
      ? DECISION_STATUS.loading
      : DECISION_STATUS.ready,
    overview,
    availability,
    benchmarkSupport: {
      status: benchmarkStatus,
      label: BENCHMARK_SUPPORT_LABELS[benchmarkStatus],
      metrics: availability.benchmark.metrics.map((metric) => ({
        key: metric.key,
        label: metric.label,
        availableValueCount: metric.availableValueCount,
      })),
    },
    lead,
    measurableCount: insights.measurableCount,
    tieCount: insights.ties,
    unavailableCount: insights.unavailableMetrics.length,
    canCompare: insights.measurableCount > 0,
    leadLines: buildLeadLines(lead, insights.measurableCount),
    limitations: availability.notes,
  };
};

export const getComparisonTableSpecs = (hardwareType) =>
  hardwareType === "GPU" ? GPU_TABLE_SPECS : CPU_TABLE_SPECS;

const formatSpecCellValue = (spec, value) => {
  if (spec.key === "release_date") {
    return formatReleaseDate(value);
  }

  return formatDetailValue(value, spec.unit);
};

export const buildComparisonSpecRows = (compareDetails) => {
  if (!isComparablePair(compareDetails)) {
    return [];
  }

  const specs = getComparisonTableSpecs(compareDetails[0]?.type);

  return specs.map((spec) => {
    const values = compareDetails.map((hardware) =>
      spec.source === "hardware"
        ? hardware?.[spec.key]
        : hardware?.specifications?.[spec.key]
    );
    const direction = spec.direction ?? null;
    const winner = direction
      ? getComparisonWinner(values[0], values[1], direction)
      : null;
    const state = !direction
      ? "informational"
      : winner
        ? winner
        : "unavailable";

    const cells = compareDetails.map((hardware, index) => ({
      side: COMPARISON_SIDES[index],
      value: values[index],
      display: formatSpecCellValue(spec, values[index]),
      state:
        values[index] === null || values[index] === undefined || values[index] === ""
          ? "unavailable"
          : "value",
      className: getComparisonWinnerClass(winner, index),
      marker:
        winner === COMPARISON_SIDES[index]
          ? direction === "lower"
            ? "Lower is better"
            : "Higher is better"
          : "",
    }));

    const leaderName =
      winner === "cpuA" ? compareDetails[0]?.name : compareDetails[1]?.name;

    return {
      key: spec.key,
      label: spec.label,
      unit: spec.unit ?? "",
      direction,
      state,
      cells,
      summary: !direction
        ? "Informational only"
        : winner === "tie"
          ? "Equal on both sides"
          : winner
            ? `${leaderName} is ${direction === "lower" ? "lower" : "higher"}`
            : "Not comparable",
    };
  });
};