/**
 * BuildIntelligencePanel (M4 Task 7)
 *
 * Renders the M4 build intelligence payload (M4-BUILD-v1.0) inside the
 * existing Build Intelligence section: balance, power reference, workload
 * suitability, compatibility summary, and evidence-gated upgrades.
 *
 * Boundary contract preserved from the M3 section this extends:
 * - No frame rate, thermal, or measured power claims are added.
 * - UNKNOWN balance / missing slots are named, never papered over.
 * - Every upgrade hint carries its evidence basis and compatibility label.
 */

const BALANCE_LABELS = {
  cpu_bound: "CPU-leaning workload balance",
  gpu_bound: "GPU-leaning workload balance",
  balanced: "Balanced",
  unknown: "Balance unknown",
};

export function BuildIntelligencePanel({ intelligence }) {
  if (!intelligence) {
    return null;
  }

  const balance = intelligence.balance || {};
  const power = intelligence.power || {};
  const summary = intelligence.compatibility_summary || {};
  const suitability = intelligence.workload_suitability || {};
  const upgrades = Array.isArray(intelligence.upgrades)
    ? intelligence.upgrades
    : [];
  const limitations = Array.isArray(intelligence.limitations)
    ? intelligence.limitations
    : [];
  const missingSlots = Array.isArray(intelligence.missing_slots)
    ? intelligence.missing_slots
    : [];

  return (
    <section
      className="build-intelligence-panel"
      aria-label="Build intelligence analysis"
    >
      <header className="build-intelligence-panel-header">
        <h3 className="build-intelligence-panel-title">
          Intelligence analysis
        </h3>
        <span className="build-intelligence-version">
          {intelligence.build_intelligence_version}
        </span>
      </header>

      <div className="build-intelligence-grid">
        <div className="build-intelligence-card" aria-label="Balance">
          <h4>Balance</h4>
          <p className="build-intelligence-balance-class">
            {BALANCE_LABELS[balance.classification] || balance.classification}
          </p>
          <p className="build-intelligence-balance-note">{balance.explanation}</p>
        </div>

        <div className="build-intelligence-card" aria-label="Power reference">
          <h4>Power reference</h4>
          {power.mode === "reference" ? (
            <p className="build-intelligence-power-reference">
              {power.reference_w} W reference
              {power.sum_listed_tdp_w != null && (
                <span className="build-intelligence-power-sum">
                  {" "}
                  (sum of listed TDPs {power.sum_listed_tdp_w} W)
                </span>
              )}
            </p>
          ) : (
            <p className="build-intelligence-power-unknown">
              Reference unavailable
            </p>
          )}
          <p className="build-intelligence-power-note">{power.basis}</p>
          {(power.limitations || []).map((limitation, index) => (
            <p
              key={`power-limitation-${index}`}
              className="build-intelligence-limitation"
            >
              {limitation}
            </p>
          ))}
        </div>

        <div className="build-intelligence-card" aria-label="Compatibility">
          <h4>Compatibility</h4>
          <p className="build-intelligence-compat-overall">
            {summary.overall || "NOT_EVALUATED"}
          </p>
          {missingSlots.length > 0 && (
            <p className="build-intelligence-missing-slots">
              Missing slots: {missingSlots.join(", ")}
            </p>
          )}
          {(summary.unknown_rules || []).length > 0 && (
            <details className="build-intelligence-details">
              <summary>
                {summary.unknown_rules.length} unresolved check
                {summary.unknown_rules.length === 1 ? "" : "s"}
              </summary>
              <ul>
                {summary.unknown_rules.map((rule) => (
                  <li key={rule}>{rule}</li>
                ))}
              </ul>
            </details>
          )}
          {(summary.incompatible_rules || []).length > 0 && (
            <details className="build-intelligence-details">
              <summary>
                {summary.incompatible_rules.length} incompatible check
                {summary.incompatible_rules.length === 1 ? "" : "s"}
              </summary>
              <ul>
                {summary.incompatible_rules.map((rule) => (
                  <li key={rule}>{rule}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>

      <section
        className="build-intelligence-workloads"
        aria-label="Workload suitability"
      >
        <h4>Workload suitability</h4>
        <div className="build-intelligence-workload-grid">
          {Object.entries(suitability).map(([key, entry]) => {
            const unknown = entry.score == null;
            return (
              <div
                key={key}
                className={`build-intelligence-workload ${unknown ? "scenario-unknown" : ""}`}
              >
                <span className="build-intelligence-workload-label">
                  {entry.profile_label || key}
                </span>
                {unknown ? (
                  <span className="build-intelligence-workload-score">
                    Unknown
                  </span>
                ) : (
                  <span className="build-intelligence-workload-score">
                    {entry.score}
                    <span
                      className={`suitability-confidence ${
                        entry.confidence === "high"
                          ? "confidence-high"
                          : entry.confidence === "low"
                            ? "confidence-low"
                            : "confidence-medium"
                      }`}
                    >
                      {entry.confidence}
                    </span>
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {upgrades.length > 0 && (
        <section
          className="build-intelligence-upgrades"
          aria-label="Upgrade suggestions"
        >
          <h4>Upgrade hints</h4>
          <ul className="build-intelligence-upgrade-list">
            {upgrades.map((upgrade, index) => (
              <li
                key={`upgrade-${upgrade.target_slot}-${index}`}
                className="build-intelligence-upgrade"
              >
                <span className="build-intelligence-upgrade-slot">
                  {upgrade.target_slot}
                </span>
                <span className="build-intelligence-upgrade-text">
                  {upgrade.rationale}
                  {upgrade.evidence === "spec" && (
                    <em className="build-intelligence-upgrade-spec">
                      {" "}
                      (spec-based)
                    </em>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {limitations.length > 0 && (
        <details className="build-intelligence-limitations">
          <summary>What this analysis does not claim</summary>
          <ul>
            {limitations.map((limitation, index) => (
              <li key={`limitation-${index}`}>{limitation}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

export default BuildIntelligencePanel;
