import { useEffect, useState } from "react";
import "./App.css";
import {
  getPerformanceState,
  PERFORMANCE_METRICS,
} from "./performance.js";

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

function App() {
  const [apiStatus, setApiStatus] = useState("Checking...");
  const [hardware, setHardware] = useState([]);
  const [hardwareLoading, setHardwareLoading] = useState(true);
  const [hardwareError, setHardwareError] = useState("");
  const [search, setSearch] = useState("");
  const [manufacturerFilter, setManufacturerFilter] = useState("All");
  const [visibleCount, setVisibleCount] = useState(12);
  const [selectedHardware, setSelectedHardware] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [compareList, setCompareList] = useState([]);
  const [compareDetails, setCompareDetails] = useState([]);
  const [benchmarkStates, setBenchmarkStates] = useState({});

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
    setCompareList([]);
    setCompareDetails([]);

    setBenchmarkStates({});
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
    const numericValues = values.filter(
      (value) => typeof value === "number" && Number.isFinite(value)
    );
    const value = values[itemIndex];

    if (
      typeof value !== "number" ||
      !Number.isFinite(value) ||
      numericValues.length !== 2
    ) {
      return "";
    }

    const winner = lowerIsBetter
      ? Math.min(...numericValues)
      : Math.max(...numericValues);

    return value === winner ? "comparison-winner" : "";
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

      <section id="explore" className="hardware-section">
        <h2 id="explore-top">Explore Hardware</h2>

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
          <div
            className={`hardware-card ${
              compareList.some((hardware) => hardware.id === item.id)
                ? "in-comparison"
                : ""
            }`}
            key={item.id}
            role="button"
            tabIndex={0}
            aria-label={`View details for ${item.name}`}
            onClick={() => showHardwareDetail(item.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                showHardwareDetail(item.id);
              }
            }}
          >
            <h3>{item.name}</h3>

            <p>{item.manufacturer}</p>

            <span>{item.type}</span>

            <button
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
          </div>
              ))}
          </div>
        )}

        {visibleCount < filteredHardware.length && (
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

        {detailLoading && (
          <p className="detail-status" role="status" aria-live="polite">
            Loading hardware details...
          </p>
        )}

        {detailError && (
          <p className="detail-error" role="alert">
            {detailError}
          </p>
        )}

        {selectedHardware && (
          <section className="hardware-detail">
             <button
               type="button"
               className="back-button"
              onClick={() => {
                setSelectedHardware(null);

                setTimeout(() => {
                  document
                    .getElementById("explore-top")
                    ?.scrollIntoView({
                      behavior: "smooth",
                      block: "start",
                    });
                }, 0);
              }}
            >
              ← Back to Explore
            </button>

            <div className="hardware-detail-header">
              <div>
                <p className="eyebrow detail-type">
                  {selectedHardware.type}
                </p>

                <h2>{selectedHardware.name}</h2>

                <p className="hardware-meta">
                  <span className="manufacturer-mark" aria-hidden="true">
                    {selectedHardware.manufacturer?.slice(0, 1)}
                  </span>
                  {selectedHardware.manufacturer}
                </p>
              </div>

               <button
                 type="button"
                 className="detail-compare-button"
                onClick={() => addToCompare(selectedHardware)}
                disabled={
                  !compareList.some(
                    (hardware) => hardware.id === selectedHardware.id
                  ) && compareList.length >= 2
                }
              >
                {compareList.some(
                  (hardware) => hardware.id === selectedHardware.id
                )
                  ? "✓ In Comparison"
                  : compareList.length >= 2
                    ? "Comparison Full"
                    : "Add to Comparison"}
              </button>
            </div>

            <div className="detail-specifications">
              <p className="detail-section-label">
                OVERVIEW
              </p>

              <div className="spec-grid">
                <div>
                  <span>Manufacturer</span>

                  <strong>
                    {selectedHardware.manufacturer ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Type</span>

                  <strong>
                    {selectedHardware.type ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Release Date</span>

                  <strong>
                    {selectedHardware.release_date ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Architecture</span>

                  <strong>
                    {selectedHardware.architecture ?? "N/A"}
                  </strong>
                </div>
              </div>

              <p className="detail-section-label technical-label">
                KEY SPECIFICATIONS
              </p>

              <div className="spec-grid">
                <div>
                  <span>Cores</span>

                  <strong>
                    {selectedHardware.specifications?.cores ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Threads</span>

                  <strong>
                    {selectedHardware.specifications?.threads ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Base Clock</span>

                  <strong>
                    {selectedHardware.specifications?.base_clock_ghz != null
                      ? `${selectedHardware.specifications.base_clock_ghz} GHz`
                      : "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Boost Clock</span>

                  <strong>
                    {selectedHardware.specifications?.boost_clock_ghz != null
                      ? `${selectedHardware.specifications.boost_clock_ghz} GHz`
                      : "N/A"}
                  </strong>
                </div>
              </div>

              <p className="detail-section-label technical-label">
                TECHNICAL SPECIFICATIONS
              </p>

              <div className="spec-grid">
                <div>
                  <span>TDP</span>

                  <strong>
                    {selectedHardware.specifications?.tdp_w != null
                      ? `${selectedHardware.specifications.tdp_w} W`
                      : "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Process Node</span>

                  <strong>
                    {selectedHardware.specifications?.process_node_nm != null
                      ? `${selectedHardware.specifications.process_node_nm} nm`
                      : "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Socket</span>

                  <strong>
                    {selectedHardware.specifications?.socket ?? "N/A"}
                  </strong>
                </div>
              </div>
            </div>

            <PerformanceSection
              benchmarkState={benchmarkStates[selectedHardware.id]}
            />
          </section>
          )}

        <section id="compare" className="comparison-section">
          <p className="eyebrow">
            HARDWARE COMPARISON
          </p>

          <h2>Compare Hardware</h2>

          <p className="comparison-status">
            <strong>{compareList.length} of 2</strong> hardware selected
          </p>

          {compareList.length === 0 ? (
            <p className="comparison-empty">
               Choose up to two CPUs from Explore Hardware. Your selected CPUs
               will appear here with verified specs and benchmark results.
            </p>
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
