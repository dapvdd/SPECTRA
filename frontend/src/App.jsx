import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [apiStatus, setApiStatus] = useState("Checking...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/")
      .then((response) => response.json())
      .then((data) => {
        setApiStatus(data.status);
      })
      .catch(() => {
        setApiStatus("offline");
      });
  }, []);

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
            />
          </div>

          <p className="api-status">
            API Status: {apiStatus}
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;