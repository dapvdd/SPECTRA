export const PERFORMANCE_METRICS = [
  {
    key: "cpu",
    title: "CPU Performance",
    description: "A broad view of processor performance across supported tests.",
  },
  {
    key: "single_core",
    title: "Single-Core Performance",
    description: "How the processor performs on workloads using one core.",
  },
  {
    key: "multi_core",
    title: "Multi-Core Performance",
    description: "How the processor performs when work is spread across cores.",
  },
  {
    key: "gaming",
    title: "Gaming Performance",
    description: "Gaming-focused results from supported benchmark sources.",
  },
];

const GEEKBENCH_NAME = "Geekbench 7";
const GEEKBENCH_UNIT = "points";
const GEEKBENCH_TEST_TYPES = {
  "single-core": "single_core",
  "multi-core": "multi_core",
};

export const BENCHMARK_COMPARISON_METRICS = [
  {
    key: "multi_core",
    title: "Geekbench 7 Multi-Core",
  },
  {
    key: "single_core",
    title: "Geekbench 7 Single-Core",
  },
];

const hasValidScore = (benchmark) =>
  typeof benchmark?.score === "number" &&
  Number.isFinite(benchmark.score) &&
  benchmark.score > 0;

const getBenchmarkRecords = (payload) => {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (!payload || typeof payload !== "object") {
    return [];
  }

  if (Array.isArray(payload.benchmark_results)) {
    return payload.benchmark_results;
  }

  if (Array.isArray(payload.benchmarks)) {
    return payload.benchmarks;
  }

  if (Array.isArray(payload.results)) {
    return payload.results;
  }

  if (payload.performance && Array.isArray(payload.performance.results)) {
    return payload.performance.results;
  }

  return [];
};

const isEarlierResult = (candidate, current) => {
  const candidateId = candidate?.id;
  const currentId = current?.id;

  if (
    typeof candidateId === "number" &&
    Number.isFinite(candidateId) &&
    typeof currentId === "number" &&
    Number.isFinite(currentId)
  ) {
    return candidateId < currentId;
  }

  return false;
};

export const normalizeBenchmarkResults = (benchmarks) => {
  return getBenchmarkRecords(benchmarks).reduce((results, benchmark) => {
    if (
      benchmark?.benchmark_name !== GEEKBENCH_NAME ||
      benchmark?.unit !== GEEKBENCH_UNIT ||
      !Object.hasOwn(GEEKBENCH_TEST_TYPES, benchmark?.test_type) ||
      !hasValidScore(benchmark)
    ) {
      return results;
    }

    const metricKey = GEEKBENCH_TEST_TYPES[benchmark.test_type];
    const current = results[metricKey];

    if (!current || isEarlierResult(benchmark, current)) {
      results[metricKey] = benchmark;
    }

    return results;
  }, {});
};

export const getPerformanceState = (benchmarkState) => {
  if (!benchmarkState || benchmarkState.status === "loading") {
    return { status: "loading", results: {} };
  }

  if (benchmarkState.status === "error") {
    return {
      status: "error",
      message: benchmarkState.message || "Performance data could not be loaded.",
      results: {},
    };
  }

  const results = normalizeBenchmarkResults(
    benchmarkState.results ?? benchmarkState
  );
  const resultCount = Object.keys(results).length;

  return {
    status:
      resultCount === 0
        ? "unavailable"
        : resultCount === Object.keys(GEEKBENCH_TEST_TYPES).length
          ? "available"
          : "partial",
    results,
  };
};

const roundBarWidth = (value) => Math.round(value * 10) / 10;

export const getBenchmarkComparisonData = (
  compareDetails,
  benchmarkStates = {}
) => {
  if (!Array.isArray(compareDetails) || compareDetails.length !== 2) {
    return { status: "unavailable", metrics: [] };
  }

  const states = compareDetails.map((hardware) =>
    getPerformanceState(benchmarkStates[hardware.id])
  );
  const isLoading = states.some((state) => state.status === "loading");

  const metrics = BENCHMARK_COMPARISON_METRICS.map((metric) => {
    const values = states.map((state) => state.results[metric.key]?.score ?? null);
    const validValues = values.filter(
      (value) => typeof value === "number" && Number.isFinite(value) && value > 0
    );
    const maximum = validValues.length > 0 ? Math.max(...validValues) : null;
    const hasBothValues = validValues.length === 2;
    const winner = hasBothValues
      ? values[0] === values[1]
        ? "tie"
        : values[0] > values[1]
          ? "cpuA"
          : "cpuB"
      : null;

    return {
      ...metric,
      winner,
      rows: values.map((value, index) => ({
        cpu: index === 0 ? "cpuA" : "cpuB",
        value,
        width: value != null && maximum != null
          ? roundBarWidth((value / maximum) * 100)
          : null,
      })),
    };
  });

  const availableValueCount = metrics.reduce(
    (count, metric) =>
      count + metric.rows.filter((row) => row.value != null).length,
    0
  );

  return {
    status: isLoading
      ? "loading"
      : availableValueCount === 0
        ? "unavailable"
        : availableValueCount === metrics.length * 2
          ? "available"
          : "partial",
    metrics,
  };
};
