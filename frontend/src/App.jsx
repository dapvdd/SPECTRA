import "./App.css";

function App() {
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
        </div>
      </main>
    </div>
  );
}

export default App;