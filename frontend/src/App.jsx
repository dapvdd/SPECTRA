import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [apiStatus, setApiStatus] = useState("Checking...");
  const [hardware, setHardware] = useState([]);
  const [search, setSearch] = useState("");
  const [selectedHardware, setSelectedHardware] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

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

const normalizeSearch = (text) => {
  return text
    .toLowerCase()
    .replace(/[-_]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
};

const filteredHardware = hardware.filter((item) =>
  normalizeSearch(item.name).includes(normalizeSearch(search))
);

  return (
    <div className="app">
      <nav className="navbar">
        <div className="logo">SPECTRA</div>

        <div className="nav-links">
          <span>Explore</span>
          <span>Compare</span>
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

          <p className="api-status">
            API Status: {apiStatus}
          </p>
          <section className="hardware-section">
            <h2>Explore Hardware</h2>

            <div className="hardware-grid">
            {filteredHardware.slice(0, 6).map((item) => (
                <div
                  className="hardware-card"
                  key={item.id}
                  onClick={() => showHardwareDetail(item.id)}
                >
                  <h3>{item.name}</h3>
                  <p>{item.manufacturer}</p>
                  <span>{item.type}</span>
                </div>
              ))}
            </div>

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
                onClick={() => setSelectedHardware(null)}
              >
                ← Back to hardware
              </button>
              <p className="eyebrow">HARDWARE DETAIL</p>

              <h2>{selectedHardware.name}</h2>

              <p>
                {selectedHardware.manufacturer} •{" "}
                {selectedHardware.type}
              </p>

              <div className="spec-grid">
                <div>
                  <span>Cores</span>
                  <strong>
                    {selectedHardware.specifications.cores}
                  </strong>
                </div>

                <div>
                  <span>Threads</span>
                  <strong>
                    {selectedHardware.specifications.threads}
                  </strong>
                </div>

                <div>
                  <span>Base Clock</span>
                  <strong>
                    {selectedHardware.specifications.base_clock_ghz} GHz
                  </strong>
                </div>

                <div>
                  <span>Boost Clock</span>
                  <strong>
                    {selectedHardware.specifications.boost_clock_ghz} GHz
                  </strong>
                </div>

                <div>
                  <span>TDP</span>
                  <strong>
                    {selectedHardware.specifications.tdp_w} W
                  </strong>
                </div>

                <div>
                  <span>Process Node</span>
                  <strong>
                    {selectedHardware.specifications.process_node_nm} nm
                  </strong>
                </div>

                <div>
                  <span>Socket</span>
                  <strong>
                    {selectedHardware.specifications.socket}
                  </strong>
                </div>
              </div>
            </section>
          )}
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;