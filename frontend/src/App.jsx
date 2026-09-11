import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [apiStatus, setApiStatus] = useState("Checking...");
  const [hardware, setHardware] = useState([]);
  const [search, setSearch] = useState("");
  const [manufacturerFilter, setManufacturerFilter] = useState("All");
  const [visibleCount, setVisibleCount] = useState(12);
  const [selectedHardware, setSelectedHardware] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [compareList, setCompareList] = useState([]);
  const [compareDetails, setCompareDetails] = useState([]);

  const showHardwareDetail = (id) => {
    setDetailLoading(true);
    setDetailError("");

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
  };

  const clearComparison = () => {
    setCompareList([]);
    setCompareDetails([]);
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
      .then((response) => response.json())
      .then((data) => {
        setHardware(data);
      })
      .catch((error) => {
        console.error("Failed to load hardware:", error);
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

  return (
    <div className="app">
      <nav className="navbar">
        <div className="logo">SPECTRA</div>

        <div className="nav-links">
          <span
            onClick={() => {
              document
                .getElementById("explore")
                ?.scrollIntoView({
                  behavior: "smooth",
                });
            }}
          >
            Explore
          </span>

          <span
            onClick={() => {
              document
                .getElementById("compare")
                ?.scrollIntoView({
                  behavior: "smooth",
                });
            }}
          >
            Compare
          </span>

          <span>About</span>
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
            <span>⌕</span>

            <input
              type="text"
              placeholder="Search for a CPU..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className="filter-buttons">
            {["All", "Intel", "AMD"].map((manufacturer) => (
              <button
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

          <p className="api-status">
            API Status: {apiStatus}
          </p>
        </div>
      </main>

      <p className="hardware-result-count">
        Showing{" "}
        {Math.min(visibleCount, filteredHardware.length)}{" "}
        of {filteredHardware.length}{" "}
        {manufacturerFilter === "All"
          ? "CPUs"
          : `${manufacturerFilter} CPUs`}
      </p>

      <section id="explore" className="hardware-section">
        <h2 id="explore-top">Explore Hardware</h2>

        {filteredHardware.length === 0 ? (
          <div className="hardware-empty">
            <span className="hardware-empty-icon">
              ◈
            </span>

            <h3>No hardware found</h3>

            <p>
              Try another search term or change your filter.
            </p>

            <button
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
                  className="hardware-card"
                  key={item.id}
                  onClick={() => showHardwareDetail(item.id)}
                >
                  <h3>{item.name}</h3>

                  <p>{item.manufacturer}</p>

                  <span>{item.type}</span>

                  <button
                    className="compare-button"
                    onClick={(event) => {
                      event.stopPropagation();
                      addToCompare(item);
                    }}
                  >
                    Compare
                  </button>
                </div>
              ))}
          </div>
        )}

        {visibleCount < filteredHardware.length && (
          <div className="load-more-container">
            <button
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
          <p className="detail-status">
            Loading hardware details...
          </p>
        )}

        {detailError && (
          <p className="detail-error">
            {detailError}
          </p>
        )}

        {selectedHardware && (
          <section className="hardware-detail">
            <button
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
                <p className="eyebrow">
                  {selectedHardware.type}
                </p>

                <h2>{selectedHardware.name}</h2>

                <p className="hardware-meta">
                  {selectedHardware.manufacturer}
                </p>
              </div>

              <button
                className="detail-compare-button"
                onClick={() => addToCompare(selectedHardware)}
              >
                Add to Comparison
              </button>
            </div>

            <div className="detail-specifications">
              <p className="detail-section-label">
                KEY SPECIFICATIONS
              </p>

              <div className="spec-grid">
                <div>
                  <span>Cores</span>

                  <strong>
                    {selectedHardware.specifications.cores ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Threads</span>

                  <strong>
                    {selectedHardware.specifications.threads ?? "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Base Clock</span>

                  <strong>
                    {selectedHardware.specifications.base_clock_ghz != null
                      ? `${selectedHardware.specifications.base_clock_ghz} GHz`
                      : "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Boost Clock</span>

                  <strong>
                    {selectedHardware.specifications.boost_clock_ghz != null
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
                    {selectedHardware.specifications.tdp_w != null
                      ? `${selectedHardware.specifications.tdp_w} W`
                      : "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Process Node</span>

                  <strong>
                    {selectedHardware.specifications.process_node_nm != null
                      ? `${selectedHardware.specifications.process_node_nm} nm`
                      : "N/A"}
                  </strong>
                </div>

                <div>
                  <span>Socket</span>

                  <strong>
                    {selectedHardware.specifications.socket ?? "N/A"}
                  </strong>
                </div>
              </div>
            </div>

            <div className="performance-section">
              <p className="detail-section-label">
                PERFORMANCE
              </p>

              <div className="performance-empty">
                <span className="performance-icon">
                  ◈
                </span>

                <h3>
                  Benchmark data is not available yet.
                </h3>

                <p>
                  SPECTRA is currently building its hardware
                  performance dataset.
                </p>

                <span className="coming-soon-badge">
                  COMING SOON
                </span>
              </div>
            </div>
          </section>
        )}

        <section id="compare" className="comparison-section">
          <p className="eyebrow">
            HARDWARE COMPARISON
          </p>

          <h2>Compare Hardware</h2>

          {compareDetails.length === 0 ? (
            <p className="comparison-empty">
              Select up to 2 CPUs to compare.
            </p>
          ) : (
            <div className="comparison-content">
              <button
                className="clear-compare-button"
                onClick={clearComparison}
              >
                Clear Comparison
              </button>

              <div className="comparison-table-wrapper">
                <table className="comparison-table">
                  <thead>
                    <tr>
                      <th>Specification</th>

                      {compareDetails.map((item) => (
                        <th key={item.id}>
                          <div className="comparison-header">
                            <span>{item.name}</span>

                            <button
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
                        <td key={item.id}>
                          {item.specifications.cores ?? "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Threads</td>

                      {compareDetails.map((item) => (
                        <td key={item.id}>
                          {item.specifications.threads ?? "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Base Clock</td>

                      {compareDetails.map((item) => (
                        <td key={item.id}>
                          {item.specifications.base_clock_ghz != null
                            ? `${item.specifications.base_clock_ghz} GHz`
                            : "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>Boost Clock</td>

                      {compareDetails.map((item) => (
                        <td key={item.id}>
                          {item.specifications.boost_clock_ghz != null
                            ? `${item.specifications.boost_clock_ghz} GHz`
                            : "N/A"}
                        </td>
                      ))}
                    </tr>

                    <tr>
                      <td>TDP</td>

                      {compareDetails.map((item) => (
                        <td key={item.id}>
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
            </div>
          )}
        </section>
      </section>
    </div>
  );
}

export default App;