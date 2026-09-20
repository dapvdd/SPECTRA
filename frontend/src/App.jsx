import { useEffect, useState } from "react";
import "./App.css";
import {
  getBenchmarkComparisonData,
  getPerformanceState,
  PERFORMANCE_METRICS,
} from "./performance.js";
import {
  calculateComparisonInsights,
  buildComparisonFacts,
  getComparisonWinner,
} from "./comparison.js";
import {
  AI_ANALYSIS_STATUS,
  requestComparisonExplanation,
} from "./comparisonExplanation.js";
import {
  getCpuDetailViewModel,
  getDetailComparisonAction,
} from "./detail.js";

const formatBenchmarkScore = (score) =>
  Number.isInteger(score) ? score.toLocaleString() : score.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });

const PERFORMANCE_STATUS_LABELS = {
  available: "DATA AVAILABLE",
  partial: "PARTIAL DATA",
  unavailable: "NOT AVAILABLE",
  loading: "LOADING",
  error: "UNAVAILABLE",
};

function PerformanceSection({ benchmarkState }) {
  const performanceState = getPerformanceState(benchmarkState);

  return (
    <div className="performance-section">
      <p className="detail-section-label">PERFORMANCE</p>

      <div className="performance-intro">
        <div>
          <h3>Performance signals, when verified</h3>

          <p>
            Benchmark scores are shown only when returned by a verified data
            source. No score is estimated or substituted here.
          </p>
        </div>

        <span
          className={`performance-status performance-status-${performanceState.status}`}
        >
          {PERFORMANCE_STATUS_LABELS[performanceState.status]}
        </span>
      </div>

      {performanceState.status === "unavailable" && (
        <div className="performance-notice">
          <strong>Benchmark data is not available yet.</strong>
          <span>
            No supported Geekbench 7 result has been returned for this CPU.
          </span>
        </div>
      )}

      {performanceState.status === "partial" && (
        <div className="performance-notice">
          <strong>Some benchmark data is unavailable.</strong>
          <span>
            Available results are shown below; missing metrics remain clearly
            marked until verified data is returned.
          </span>
        </div>
      )}

      {performanceState.status === "loading" && (
        <div className="performance-notice performance-notice-loading">
          <strong>Loading performance data</strong>
          <span>Waiting for the benchmark data source to respond.</span>
        </div>
      )}

      {performanceState.status === "error" && (
        <div className="performance-notice performance-notice-error">
          <strong>Performance data could not be loaded.</strong>
          <span>{performanceState.message}</span>
        </div>
      )}

      <div className="performance-grid">
        {PERFORMANCE_METRICS.map((metric, index) => {
          const result = performanceState.results[metric.key];
          const sourceName = result?.source?.name || result?.source_name;

          return (
            <article
              className={`performance-card ${
                result ? "performance-card-available" : ""
              }`}
              key={metric.key}
            >
              <div className="performance-card-header">
                <div>
                  <span className="performance-card-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3>{metric.title}</h3>
                </div>

                <span
                  className={`performance-badge ${
                    result ? "performance-badge-available" : ""
                  }`}
                >
                  {result ? "AVAILABLE" : "NO DATA"}
                </span>
              </div>

              {result ? (
                <div className="performance-result">
                  <div className="performance-value">
                    <strong>{formatBenchmarkScore(result.score)}</strong>
                    <span>{result.unit}</span>
                  </div>

                  <p>{metric.description}</p>

                  {(result.benchmark_name || sourceName || result.recorded_at) && (
                    <small>
                      <span>{result.benchmark_name || "Benchmark result"}</span>
                      {sourceName && <span>Source: {sourceName}</span>}
                    </small>
                  )}
                </div>
              ) : (
                <div className="performance-result performance-result-unavailable">
                  <div className="performance-value">
                    <strong>--</strong>
                    <span>score</span>
                  </div>

                  <p>{metric.description}</p>

                  <small>
                    No verified result has been returned for this metric.
                  </small>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

function BenchmarkComparison({ comparisonData, compareDetails }) {
  if (comparisonData.status === "loading") {
    return (
      <section className="benchmark-comparison" aria-labelledby="benchmark-comparison-title">
        <div className="benchmark-comparison-header">
          <div>
            <p className="detail-section-label">BENCHMARK COMPARISON</p>
            <h3 id="benchmark-comparison-title">Geekbench 7 scores</h3>
          </div>
          <span className="performance-status performance-status-loading">LOADING</span>
        </div>
        <div className="benchmark-comparison-notice" role="status">
          <span className="state-spinner" aria-hidden="true" />
          Waiting for verified benchmark data.
        </div>
      </section>
    );
  }

  const hasAvailableScore = comparisonData.metrics.some((metric) =>
    metric.rows.some((row) => row.value != null)
  );

  return (
    <section className="benchmark-comparison" aria-labelledby="benchmark-comparison-title">
      <div className="benchmark-comparison-header">
        <div>
          <p className="detail-section-label">BENCHMARK COMPARISON</p>
          <h3 id="benchmark-comparison-title">Geekbench 7 scores</h3>
        </div>
        <span className="performance-status">
          {hasAvailableScore ? "VERIFIED DATA" : "NO DATA"}
        </span>
      </div>

      {!hasAvailableScore ? (
        <p className="benchmark-comparison-notice">
          Benchmark data unavailable.
        </p>
      ) : (
        <div className="benchmark-comparison-grid">
          {comparisonData.metrics.map((metric) => (
            <article className="benchmark-comparison-card" key={metric.key}>
              <div className="benchmark-comparison-card-heading">
                <h4>{metric.title}</h4>
                {metric.winner === "tie" && (
                  <span className="benchmark-comparison-result">TIE</span>
                )}
                {metric.winner && metric.winner !== "tie" && (
                  <span className="benchmark-comparison-result">
                    {metric.winner === "cpuA" ? compareDetails[0].name : compareDetails[1].name} leads
                  </span>
                )}
              </div>

              <div className="benchmark-bars">
                {metric.rows.map((row, index) => {
                  const cpu = compareDetails[index];
                  const isWinner = metric.winner === row.cpu;

                  return (
                    <div className="benchmark-bar-row" key={row.cpu}>
                      <div className="benchmark-bar-label">
                        <span title={cpu.name}>{cpu.name}</span>
                        {row.value != null ? (
                          <strong>{formatBenchmarkScore(row.value)} points</strong>
                        ) : (
                          <strong className="benchmark-bar-unavailable">No data</strong>
                        )}
                      </div>
                      <div className="benchmark-bar-track" aria-hidden="true">
                        {row.width != null && (
                          <span
                            className={`benchmark-bar-fill ${isWinner ? "benchmark-bar-fill-winner" : ""}`}
                            style={{ width: `${row.width}%` }}
                          />
                        )}
                      </div>
                      {isWinner && <span className="sr-only">Higher score</span>}
                    </div>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function DetailSpecGrid({ items }) {
  return (
    <div className="spec-grid">
      {items.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

function CpuDetailView({
  hardware,
  benchmarkState,
  compareList,
  onBack,
  onCompare,
  detailError,
}) {
  const viewModel = getCpuDetailViewModel(hardware);
  const comparisonAction = getDetailComparisonAction(compareList, hardware.id);

  return (
    <section className="hardware-detail" aria-labelledby="cpu-detail-title">
      <button type="button" className="back-button" onClick={onBack}>
        ← Back to CPUs
      </button>

      {detailError && (
        <div className="detail-state detail-state-error" role="alert">
          <strong>CPU details unavailable</strong>
          <span>{detailError}</span>
        </div>
      )}

      <div className="hardware-detail-header">
        <div>
          <p className="eyebrow detail-type">CPU DETAIL</p>
          <h2 id="cpu-detail-title">{viewModel.name}</h2>
          <p className="hardware-meta">
            <span className="manufacturer-mark" aria-hidden="true">
              {viewModel.manufacturer.slice(0, 1)}
            </span>
            {viewModel.manufacturer} · {viewModel.type}
          </p>
        </div>

        <button
          type="button"
          className="detail-compare-button"
          onClick={onCompare}
          disabled={comparisonAction.comparisonFull}
        >
          {comparisonAction.alreadySelected
            ? `✓ CPU ${comparisonAction.comparisonSlot} selected`
            : comparisonAction.comparisonFull
              ? "Comparison Full"
              : "Compare CPU"}
        </button>
      </div>

      <div className="detail-specifications">
        <p className="detail-section-label">OVERVIEW</p>
        <DetailSpecGrid items={viewModel.overview} />

        <p className="detail-section-label technical-label">
          KEY SPECIFICATIONS
        </p>
        <DetailSpecGrid items={viewModel.keySpecifications} />

        <p className="detail-section-label technical-label">
          TECHNICAL SPECIFICATIONS
        </p>
        <DetailSpecGrid items={viewModel.technicalSpecifications} />
      </div>

      <PerformanceSection benchmarkState={benchmarkState} />
    </section>
  );
}

const formatInsightValue = (value, format, unit) => {
  const formattedValue =
    format === "integer"
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

  return unit ? `${formattedValue} ${unit}` : formattedValue;
};

function ComparisonInsights({ insights, compareDetails }) {
  if (insights.pendingMetrics.length > 0) {
    return (
      <section className="comparison-insights" aria-labelledby="insights-title">
        <div className="comparison-insights-header">
          <div>
            <p className="detail-section-label">COMPARISON INSIGHTS</p>
            <h3 id="insights-title">Waiting for comparable data</h3>
          </div>
          <span className="comparison-insights-mark" aria-hidden="true">?</span>
        </div>
        <p className="comparison-insights-message">
          Verified benchmark data is still loading. Insights will appear when
          both CPUs have finished loading their supported metrics.
        </p>
      </section>
    );
  }

  if (insights.measurableCount === 0) {
    return (
      <section className="comparison-insights" aria-labelledby="insights-title">
        <div className="comparison-insights-header">
          <div>
            <p className="detail-section-label">COMPARISON INSIGHTS</p>
            <h3 id="insights-title">No measurable lead yet</h3>
          </div>
          <span className="comparison-insights-mark" aria-hidden="true">—</span>
        </div>
        <p className="comparison-insights-message">
          Not enough comparable data to generate insights.
        </p>
      </section>
    );
  }

  const [cpuA, cpuB] = compareDetails;
  const unavailableLabel =
    insights.unavailableMetrics.length === 1
      ? "1 metric could not be compared because data is unavailable."
      : `${insights.unavailableMetrics.length} metrics could not be compared because data is unavailable.`;

  return (
    <section className="comparison-insights" aria-labelledby="insights-title">
      <div className="comparison-insights-header">
        <div>
          <p className="detail-section-label">COMPARISON INSIGHTS</p>
          <h3 id="insights-title">Why the numbers differ</h3>
        </div>
        <span className="comparison-insights-mark" aria-hidden="true">+</span>
      </div>

      <div className="comparison-insights-summary">
        {insights.wins.cpuA > 0 && (
          <p>
            <strong>{cpuA.name}</strong> leads in {insights.wins.cpuA} of{" "}
            {insights.measurableCount} measurable metrics.
          </p>
        )}
        {insights.wins.cpuB > 0 && (
          <p>
            <strong>{cpuB.name}</strong> leads in {insights.wins.cpuB} of{" "}
            {insights.measurableCount} measurable metrics.
          </p>
        )}
        {insights.wins.cpuA === 0 && insights.wins.cpuB === 0 && (
          <p>All {insights.measurableCount} measurable metrics are tied.</p>
        )}
      </div>

      {insights.insights.length > 0 && (
        <ul className="comparison-insight-list">
          {insights.insights.map((insight) => (
            <li className="comparison-insight-item" key={insight.metricKey}>
              <span className="comparison-insight-icon" aria-hidden="true">+</span>
              <div>
                <strong>{insight.metric}</strong>
                <span>{insight.winnerName}</span>
              </div>
              <span className="comparison-insight-difference">
                {insight.direction === "lower" ? "" : "+"}
                {insight.differencePercent.toFixed(1)}%{" "}
                {insight.direction === "lower" ? "lower" : "higher"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {insights.tieDetails.length > 0 && (
        <div className="comparison-insight-ties">
          <strong>Ties</strong>
          {insights.tieDetails.map((tie) => (
            <span key={tie.metricKey}>
              {tie.metric} — Tie at {formatInsightValue(tie.value, tie.format, tie.unit)}
            </span>
          ))}
        </div>
      )}

      {insights.unavailableMetrics.length > 0 && (
        <p className="comparison-insights-unavailable">{unavailableLabel}</p>
      )}
    </section>
  );
}

function AiAnalysis({ analysis, onGenerate }) {
  return (
    <section className="ai-analysis" aria-labelledby="ai-analysis-title">
      <div className="ai-analysis-header">
        <div>
          <p className="detail-section-label">AI ANALYSIS</p>
          <h3 id="ai-analysis-title">A concise explanation of the comparison</h3>
        </div>
        <span className="ai-analysis-mark" aria-hidden="true">AI</span>
      </div>

      {analysis.status === AI_ANALYSIS_STATUS.idle && (
        <div className="ai-analysis-empty">
          <p>Generate an AI explanation of this comparison.</p>
          <button type="button" className="ai-analysis-button" onClick={onGenerate}>
            Generate Analysis
          </button>
        </div>
      )}

      {analysis.status === AI_ANALYSIS_STATUS.loading && (
        <div className="ai-analysis-message" role="status">
          <span className="state-spinner" aria-hidden="true" />
          <span>Analyzing comparison...</span>
        </div>
      )}

      {analysis.status === AI_ANALYSIS_STATUS.success && (
        <div className="ai-analysis-result">
          <p>{analysis.explanation}</p>
          <button type="button" className="ai-analysis-button" onClick={onGenerate}>
            Regenerate Analysis
          </button>
        </div>
      )}

      {analysis.status === AI_ANALYSIS_STATUS.error && (
        <div className="ai-analysis-error" role="alert">
          <p>Unable to generate analysis.</p>
          <button type="button" className="ai-analysis-button" onClick={onGenerate}>
            Try Again
          </button>
        </div>
      )}
    </section>
  );
}

function App() {
  const [apiStatus, setApiStatus] = useState("Checking...");
  const [hardware, setHardware] = useState([]);
  const [hardwareLoading, setHardwareLoading] = useState(true);
  const [hardwareError, setHardwareError] = useState("");
  const [search, setSearch] = useState("");
  const [manufacturerFilter, setManufacturerFilter] = useState("All");
  const [visibleCount, setVisibleCount] = useState(12);
  const [selectedHardware, setSelectedHardware] = useState(null);
  const [detailView, setDetailView] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [compareList, setCompareList] = useState([]);
  const [compareDetails, setCompareDetails] = useState([]);
  const [benchmarkStates, setBenchmarkStates] = useState({});
  const [aiAnalysis, setAiAnalysis] = useState({
    status: AI_ANALYSIS_STATUS.idle,
    explanation: "",
  });

  const loadBenchmarks = (hardwareId) => {
    setBenchmarkStates((prev) => ({
      ...prev,
      [hardwareId]: { status: "loading", results: null },
    }));

    fetch(`http://127.0.0.1:8000/hardware/${hardwareId}/benchmarks`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        return response.json();
      })
      .then((data) => {
        setBenchmarkStates((prev) => ({
          ...prev,
          [hardwareId]: { status: "success", results: data },
        }));
      })
      .catch((error) => {
        console.error("Failed to load benchmark data:", error);
        setBenchmarkStates((prev) => ({
          ...prev,
          [hardwareId]: {
            status: "error",
            message: "Benchmark data could not be loaded.",
            results: null,
          },
        }));
      });
  };

  const showHardwareDetail = (id) => {
    setDetailLoading(true);
    setDetailError("");
    setSelectedHardware(null);
    setDetailView(true);
    loadBenchmarks(id);

    fetch(`http://127.0.0.1:8000/hardware/${id}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        return response.json();
      })
      .then((data) => {
        setSelectedHardware(data);
      })
      .catch((error) => {
        console.error("Failed to load hardware detail:", error);
        setDetailError("Failed to load hardware details.");
      })
      .finally(() => {
        setDetailLoading(false);
      });
  };

  const addToCompare = (item) => {
    if (compareList.some((hardware) => hardware.id === item.id)) {
      return;
    }

    if (compareList.length >= 2) {
      return;
    }

    setAiAnalysis({ status: AI_ANALYSIS_STATUS.idle, explanation: "" });
    setCompareList([...compareList, item]);
    loadBenchmarks(item.id);

    fetch(`http://127.0.0.1:8000/hardware/${item.id}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        return response.json();
      })
      .then((data) => {
        setCompareDetails((prev) => [...prev, data]);
      })
      .catch((error) => {
        console.error("Failed to load comparison data:", error);
      });
  };

  const removeFromCompare = (id) => {
    setAiAnalysis({ status: AI_ANALYSIS_STATUS.idle, explanation: "" });
    setCompareList((prev) =>
      prev.filter((item) => item.id !== id)
    );

    setCompareDetails((prev) =>
      prev.filter((item) => item.id !== id)
    );

    setBenchmarkStates((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  const clearComparison = () => {
    setAiAnalysis({ status: AI_ANALYSIS_STATUS.idle, explanation: "" });
    setCompareList([]);
    setCompareDetails([]);

    setBenchmarkStates({});
  };

  const returnToCatalog = () => {
    setSelectedHardware(null);
    setDetailError("");
    setDetailView(false);

    setTimeout(() => {
      document.getElementById("explore-top")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 0);
  };

  const compareSelectedHardware = () => {
    if (!selectedHardware) {
      return;
    }

    const comparisonAction = getDetailComparisonAction(
      compareList,
      selectedHardware.id
    );

    if (comparisonAction.alreadySelected || comparisonAction.comparisonFull) {
      return;
    }

    addToCompare(selectedHardware);

    if (comparisonAction.shouldNavigateToComparison) {
      setSelectedHardware(null);
      setDetailView(false);
      setTimeout(() => {
        document.getElementById("compare")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 0);
    }
  };

  useEffect(() => {
    fetch("http://127.0.0.1:8000/")
      .then((response) => response.json())
      .then((data) => {
        setApiStatus(data.status);
      })
      .catch(() => {
        setApiStatus("offline");
      });

    fetch("http://127.0.0.1:8000/hardware")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        return response.json();
      })
      .then((data) => {
        setHardware(data);
      })
      .catch((error) => {
        console.error("Failed to load hardware:", error);
        setHardwareError("Hardware catalog could not be loaded.");
      })
      .finally(() => {
        setHardwareLoading(false);
      });
  }, []);

  useEffect(() => {
    if (selectedHardware) {
      document
        .querySelector(".hardware-detail")
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
    }
  }, [selectedHardware]);

  useEffect(() => {
    setVisibleCount(12);
  }, [search, manufacturerFilter]);

  const normalizeSearch = (text) => {
    return text
      .toLowerCase()
      .replace(/[-_]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  };

  const filteredHardware = hardware.filter((item) => {
    const matchesSearch = normalizeSearch(item.name).includes(
      normalizeSearch(search)
    );

    const matchesManufacturer =
      manufacturerFilter === "All" ||
      item.manufacturer === manufacturerFilter;

    return matchesSearch && matchesManufacturer;
  });

  const comparisonInsights = calculateComparisonInsights(
    compareDetails,
    benchmarkStates
  );
  const benchmarkComparison = getBenchmarkComparisonData(
    compareDetails,
    benchmarkStates
  );
  const comparisonFacts = buildComparisonFacts(compareDetails, benchmarkStates);

  const generateAiAnalysis = () => {
    if (!comparisonFacts) {
      return;
    }

    setAiAnalysis({ status: AI_ANALYSIS_STATUS.loading, explanation: "" });
    requestComparisonExplanation(comparisonFacts)
      .then((explanation) => {
        setAiAnalysis({ status: AI_ANALYSIS_STATUS.success, explanation });
      })
      .catch((error) => {
        console.error("Failed to generate AI analysis:", error);
        setAiAnalysis({ status: AI_ANALYSIS_STATUS.error, explanation: "" });
      });
  };

  const getComparisonCellClass = (
    specification,
    itemIndex,
    lowerIsBetter = false
  ) => {
    if (compareDetails.length !== 2) {
      return "";
    }

    const values = compareDetails.map(
      (item) => item.specifications?.[specification]
    );
    const winner = getComparisonWinner(
      values[0],
      values[1],
      lowerIsBetter ? "lower" : "higher"
    );

    return winner === "tie" || winner === (itemIndex === 0 ? "cpuA" : "cpuB")
      ? "comparison-winner"
      : "";
  };

  return (
    <div className="app">
      <nav className="navbar">
        <div className="logo">SPECTRA</div>

        <div className="nav-links">
          <a href="#explore" className="nav-link">
            Explore
          </a>

          <a href="#compare" className="nav-link">
            Compare
          </a>

          <a href="#about" className="nav-link">
            About
          </a>
        </div>
      </nav>

      <main className="hero">
        <div className="hero-content">
          <p className="eyebrow">
            HARDWARE INTELLIGENCE PLATFORM
          </p>

          <h1>
            Explore hardware.
            <br />
            Understand performance.
          </h1>

          <p className="description">
            Discover detailed specifications and explore
            computer hardware through SPECTRA.
          </p>

          <div className="search-box">
            <span aria-hidden="true">⌕</span>

            <input
              type="text"
              aria-label="Search CPUs"
              placeholder="Search for a CPU..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />

            {search && (
              <button
                type="button"
                className="clear-search-icon"
                aria-label="Clear CPU search"
                onClick={() => setSearch("")}
              >
                ×
              </button>
            )}
          </div>

          <div className="filter-buttons">
            {["All", "Intel", "AMD"].map((manufacturer) => (
              <button
                type="button"
                key={manufacturer}
                className={
                  manufacturerFilter === manufacturer
                    ? "filter-button active"
                    : "filter-button"
                }
                onClick={() => setManufacturerFilter(manufacturer)}
              >
                {manufacturer}
              </button>
            ))}
          </div>

          <p
            className={`api-status ${
              apiStatus === "online" ? "api-status-online" : ""
            }`}
          >
            <span className="status-dot" aria-hidden="true" />
            Catalog {apiStatus === "online" ? "connected" : apiStatus}
          </p>
        </div>
      </main>

      <p className="hardware-result-count" aria-live="polite">
        {hardwareLoading
          ? "Loading hardware catalog..."
          : hardwareError
            ? "Hardware catalog unavailable"
            : `Showing ${Math.min(visibleCount, filteredHardware.length)} of ${
                filteredHardware.length
              } ${manufacturerFilter === "All" ? "CPUs" : `${manufacturerFilter} CPUs`}`}
      </p>

      {compareList.length > 0 && (
        <section
          className="comparison-selection"
          aria-labelledby="comparison-selection-title"
        >
          <div className="comparison-selection-heading">
            <div>
              <p className="eyebrow">COMPARISON SET</p>
              <h2 id="comparison-selection-title">Ready to compare</h2>
            </div>

            <a className="comparison-jump-link" href="#compare">
              View comparison <span aria-hidden="true">↓</span>
            </a>
          </div>

          <div className="comparison-selection-list">
            {compareList.map((item, index) => (
              <div className="comparison-selection-item" key={item.id}>
                <span className="comparison-selection-index">
                  CPU {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <strong>{item.name}</strong>
                  <span>
                    {item.manufacturer} · {item.type || "Processor"}
                  </span>
                </div>
                <button
                  type="button"
                  className="selection-remove-button"
                  aria-label={`Remove ${item.name} from comparison`}
                  onClick={() => removeFromCompare(item.id)}
                >
                  Remove
                </button>
              </div>
            ))}

            {compareList.length === 1 && (
              <div className="comparison-selection-item comparison-selection-slot">
                <span className="comparison-selection-index">CPU 02</span>
                <div>
                  <strong>Choose a second CPU</strong>
                  <span>Use Explore Hardware below to complete the comparison.</span>
                </div>
              </div>
            )}
          </div>

          <button
            type="button"
            className="selection-clear-button"
            onClick={clearComparison}
          >
            Clear selection
          </button>
        </section>
      )}

      <section id="explore" className="hardware-section">
        <h2 id="explore-top" className={detailView ? "detail-hidden" : ""}>
          Explore Hardware
        </h2>

        <div className={detailView ? "catalog-content detail-hidden" : "catalog-content"}>
          {hardwareLoading ? (
          <div className="catalog-state" role="status" aria-live="polite">
            <span className="state-spinner" aria-hidden="true" />
            <h3>Loading the catalog</h3>
            <p>Fetching verified hardware records.</p>
          </div>
        ) : hardwareError ? (
          <div className="catalog-state catalog-state-error" role="alert">
            <h3>Catalog unavailable</h3>
            <p>{hardwareError}</p>
            <button
              type="button"
              className="clear-search-button"
              onClick={() => window.location.reload()}
            >
              Try Again
            </button>
          </div>
        ) : filteredHardware.length === 0 ? (
          <div className="hardware-empty">
            <span className="hardware-empty-icon">
              ◈
            </span>

            <h3>No hardware found</h3>

            <p>
              Try another search term or change your filter.
            </p>

             <button
               type="button"
               className="clear-search-button"
              onClick={() => {
                setSearch("");
                setManufacturerFilter("All");
              }}
            >
              Clear Search
            </button>
          </div>
        ) : (
          <div className="hardware-grid">
            {filteredHardware
              .slice(0, visibleCount)
              .map((item) => (
           <article
             className={`hardware-card ${
               compareList.some((hardware) => hardware.id === item.id)
                 ? "in-comparison"
                 : ""
             }`}
             key={item.id}
           >
             <button
               type="button"
               className="hardware-card-main"
               onClick={() => showHardwareDetail(item.id)}
             >
               <span className="hardware-card-kicker">{item.type || "CPU"}</span>
               <h3>{item.name}</h3>
               <span className="hardware-card-manufacturer">
                 {item.manufacturer}
               </span>
               <span className="hardware-card-action">
                 View specifications <span aria-hidden="true">→</span>
               </span>
             </button>

             <button
               type="button"
               className={`compare-button ${
                compareList.some((hardware) => hardware.id === item.id)
                  ? "added"
                  : ""
              }`}
              onClick={(event) => {
                event.stopPropagation();
                addToCompare(item);
              }}
              disabled={
                !compareList.some((hardware) => hardware.id === item.id) &&
                compareList.length >= 2
              }
            >
              {compareList.some((hardware) => hardware.id === item.id)
                ? "✓ In Comparison"
                : compareList.length >= 2
                  ? "Comparison Full"
                  : "Compare"}
            </button>
           </article>
              ))}
          </div>
          )}
        </div>

        {!detailView && visibleCount < filteredHardware.length && (
          <div className="load-more-container">
             <button
               type="button"
               className="load-more-button"
              onClick={() =>
                setVisibleCount((prev) =>
                  Math.min(prev + 12, filteredHardware.length)
                )
              }
            >
              Load More
            </button>
          </div>
        )}

        {!detailView && detailLoading && (
          <p className="detail-status" role="status" aria-live="polite">
            Loading hardware details...
          </p>
        )}

        {!detailView && detailError && (
          <p className="detail-error" role="alert">
            {detailError}
          </p>
        )}

        {detailView && detailLoading && (
          <div className="detail-state" role="status" aria-live="polite">
            <span className="state-spinner" aria-hidden="true" />
            <strong>Loading CPU details</strong>
            <span>Fetching verified specifications and benchmark data.</span>
          </div>
        )}

        {detailView && detailError && !selectedHardware && (
          <div className="detail-state detail-state-error" role="alert">
            <strong>CPU details unavailable</strong>
            <span>{detailError}</span>
            <button type="button" className="clear-search-button" onClick={returnToCatalog}>
              Back to CPUs
            </button>
          </div>
        )}

        {detailView && selectedHardware && (
          <CpuDetailView
            hardware={selectedHardware}
            benchmarkState={benchmarkStates[selectedHardware.id]}
            compareList={compareList}
            onBack={returnToCatalog}
            onCompare={compareSelectedHardware}
            detailError={detailError}
          />
        )}

        <section
          id="compare"
          className={`comparison-section ${detailView ? "detail-hidden" : ""}`}
        >
          <p className="eyebrow">
            HARDWARE COMPARISON
          </p>

          <h2>Compare Hardware</h2>

          <p className="comparison-status">
            <strong>{compareList.length} of 2</strong> hardware selected
          </p>

           {compareList.length === 0 ? (
             <div className="comparison-empty">
               <div>
                 <span className="comparison-empty-index">01 — 02</span>
                 <h3>Build a side-by-side view</h3>
                 <p>
                   Choose up to two CPUs from Explore Hardware. Selected CPUs
                   will appear here with verified specs and benchmark results.
                 </p>
               </div>
               <a className="comparison-explore-link" href="#explore">
                 Browse CPUs <span aria-hidden="true">→</span>
               </a>
             </div>
           ) : (
            <div className="comparison-content">
              {compareList.length === 1 && (
                <p className="comparison-instruction">
                  Select another CPU to start comparing hardware.
                </p>
              )}

              <button
                type="button"
                className="clear-compare-button"
                onClick={clearComparison}
              >
                Clear Comparison
              </button>

               {compareDetails.length === 2 && (
                 <div
                  className="comparison-legend"
                  aria-label="Comparison guidance"
                >
                  <span className="comparison-legend-title">
                    <span
                      className="comparison-legend-swatch"
                      aria-hidden="true"
                    />
                    Highlighted value is better
                  </span>

                  <span>
                    Higher is better: Cores, Threads, Base Clock, Boost Clock.
                  </span>

                   <span>Lower is better: TDP.</span>
                 </div>
               )}

               {compareDetails.length === 2 && (
                 <p className="comparison-scroll-hint">
                   <span aria-hidden="true">↔</span> Scroll horizontally to
                   view the full comparison on smaller screens.
                 </p>
               )}

               {compareDetails.length < compareList.length && (
                 <div className="comparison-loading" role="status">
                   <span className="state-spinner" aria-hidden="true" />
                   Loading selected CPU details...
                 </div>
               )}

               <div className="comparison-performance">
                {compareDetails.map((item) => (
                  <section className="comparison-performance-card" key={item.id}>
                    <p className="detail-section-label">PERFORMANCE</p>
                    <h3>{item.name}</h3>
                    <PerformanceSection
                      benchmarkState={benchmarkStates[item.id]}
                    />
                  </section>
                 ))}
               </div>

               {compareDetails.length === 2 && (
                 <BenchmarkComparison
                   comparisonData={benchmarkComparison}
                   compareDetails={compareDetails}
                 />
               )}

                {compareDetails.length === 2 && (
                  <ComparisonInsights
                   insights={comparisonInsights}
                   compareDetails={compareDetails}
                  />
                )}

                {compareDetails.length === 2 && (
                  <AiAnalysis
                    analysis={aiAnalysis}
                    onGenerate={generateAiAnalysis}
                  />
                )}

                {compareDetails.length === 2 && (
                 <div className="comparison-table-wrapper">
                 <table className="comparison-table">
                   <caption className="sr-only">
                     Side-by-side CPU specification comparison
                   </caption>
                  <thead>
                    <tr>
                      <th>Specification</th>

                      {compareDetails.map((item) => (
                        <th key={item.id}>
                          <div className="comparison-header">
                            <span>{item.name}</span>

                            <button
                              type="button"
                              className="remove-compare-button"
                              onClick={() =>
                                removeFromCompare(item.id)
                              }
                            >
                              Remove
                            </button>
                           </div>
                         </th>
                       ))}
                    </tr>
                  </thead>

                  <tbody>
                    <tr>
                      <td>Cores</td>

                      {compareDetails.map((item) => (
                        <td
                          key={item.id}
                          className={getComparisonCellClass(
                            "cores",
                            compareDetails.indexOf(item)
                          )}
                        >
                          {item.specifications.cores ?? "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Threads</td>

                      {compareDetails.map((item) => (
                        <td
                          key={item.id}
                          className={getComparisonCellClass(
                            "threads",
                            compareDetails.indexOf(item)
                          )}
                        >
                          {item.specifications.threads ?? "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Base Clock</td>

                      {compareDetails.map((item) => (
                        <td
                          key={item.id}
                          className={getComparisonCellClass(
                            "base_clock_ghz",
                            compareDetails.indexOf(item)
                          )}
                        >
                          {item.specifications.base_clock_ghz != null
                            ? `${item.specifications.base_clock_ghz} GHz`
                            : "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Boost Clock</td>

                      {compareDetails.map((item) => (
                        <td
                          key={item.id}
                          className={getComparisonCellClass(
                            "boost_clock_ghz",
                            compareDetails.indexOf(item)
                          )}
                        >
                          {item.specifications.boost_clock_ghz != null
                            ? `${item.specifications.boost_clock_ghz} GHz`
                            : "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>TDP</td>

                      {compareDetails.map((item) => (
                        <td
                          key={item.id}
                          className={getComparisonCellClass(
                            "tdp_w",
                            compareDetails.indexOf(item),
                            true
                          )}
                        >
                          {item.specifications.tdp_w != null
                            ? `${item.specifications.tdp_w} W`
                            : "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Process Node</td>

                      {compareDetails.map((item) => (
                        <td key={item.id}>
                          {item.specifications.process_node_nm != null
                            ? `${item.specifications.process_node_nm} nm`
                            : "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Socket</td>

                      {compareDetails.map((item) => (
                        <td key={item.id}>
                          {item.specifications.socket ?? "N/A"}
                        </td>
                      ))}
                    </tr>
                 </tbody>
                </table>
              </div>
           )}
             </div>
           )}
          </section>

        <section id="about" className="about-section">
          <p className="eyebrow">ABOUT SPECTRA</p>
          <p>
            A focused way to inspect hardware specifications and compare verified
            performance data without filling gaps with estimates.
          </p>
        </section>
       </section>
    </div>
  );
}

export default App;
