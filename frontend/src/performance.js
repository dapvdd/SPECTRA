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

const hasFiniteScore = (benchmark) =>
  typeof benchmark?.score === "number" && Number.isFinite(benchmark.score);

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
  if (!Array.isArray(benchmarks)) {
    return {};
  }

  return benchmarks.reduce((results, benchmark) => {
    if (
      benchmark?.benchmark_name !== GEEKBENCH_NAME ||
      benchmark?.unit !== GEEKBENCH_UNIT ||
      !Object.hasOwn(GEEKBENCH_TEST_TYPES, benchmark?.test_type) ||
      !hasFiniteScore(benchmark)
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

  const results = normalizeBenchmarkResults(benchmarkState.results);
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
