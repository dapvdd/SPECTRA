import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [apiStatus, setApiStatus] = useState("Checking...");
  const [hardware, setHardware] = useState([]);
  const [search, setSearch] = useState("");

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

  const filteredHardware = hardware.filter((item) =>
    item.name.toLowerCase().includes(search.toLowerCase())
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
                >
                  <h3>{item.name}</h3>

                  <p>{item.manufacturer}</p>

                  <span>{item.type}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;