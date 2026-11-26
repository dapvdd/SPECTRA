/**
 * ScenarioRatings (M4 Task 7)
 *
 * Renders the four-scenario rating set (gaming / workstation / daily / value)
 * for one hardware record, from the M4 scenario scoring engine
 * (M4-SCORING-v2.0). Thin presentational component: all formatting lives in
 * the pure `recommendationV2` module (tested under node --test).
 *
 * Evidence policy rendered faithfully:
 * - UNKNOWN scenarios show the named gap, never zero stars.
 * - spec-based scores carry their "spec-based" tag.
 * - The reference population is disclosed via <details> (no tooltips).
 */

import { formatScenarioSet } from "../recommendationV2.js";

export function ScenarioRatings({ payload }) {
  const display = formatScenarioSet(payload);

  if (!display.scenarios.length) {
    return null;
  }

  return (
    <section
      className="scenario-ratings"
      aria-label="Scenario ratings"
    >
      <header className="scenario-ratings-header">
        <h3 className="scenario-ratings-title">Scenario ratings</h3>
        <span
          className={`suitability-confidence ${
            display.dataCoverage !== null && display.dataCoverage >= 0.6
              ? "confidence-high"
              : "confidence-medium"
          }`}
          aria-label={`data coverage ${
            display.dataCoverage === null ? "unknown" : display.dataCoverage
          }`}
        >
          coverage {display.dataCoverage === null ? "unknown" : `${Math.round(display.dataCoverage * 100)}%`}
        </span>
      </header>

      <div className="scenario-ratings-grid">
        {display.scenarios.map((scenario) => (
          <div
            key={scenario.key}
            className={`scenario-rating-card ${scenario.unknown ? "scenario-unknown" : ""} ${
              scenario.specBased ? "spec-based" : ""
            }`}
            aria-label={`Scenario ${scenario.label}`}
          >
            <header className="scenario-rating-header">
              <span className="scenario-rating-label">{scenario.label}</span>
              <span
                className={`suitability-confidence ${scenario.confidenceBadge}`}
                aria-label={`confidence ${scenario.confidence}`}
              >
                {scenario.confidence}
              </span>
            </header>

            {scenario.unknown ? (
              <p className="scenario-rating-unknown">{scenario.unknownText}</p>
            ) : (
              <div
                className="suitability-stars"
                role="img"
                aria-label={scenario.starsLabel}
              >
                <span aria-hidden="true" className="suitability-stars-filled">
                  {"★".repeat(scenario.stars)}
                </span>
                <span aria-hidden="true" className="suitability-stars-empty">
                  {"★".repeat(5 - scenario.stars)}
                </span>
                <span className="scenario-rating-score">{scenario.scoreLabel}</span>
              </div>
            )}

            {scenario.specBased && (
              <p className="suitability-spec-based-tag">
                Spec-based (no benchmark)
              </p>
            )}

            {scenario.limitations.length > 0 && (
              <ul className="scenario-rating-limitations">
                {scenario.limitations.map((limitation, index) => (
                  <li key={`${scenario.key}-limitation-${index}`}>{limitation}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {display.referencePopulation && (
        <details className="scenario-ratings-population">
          <summary>How these ratings are derived</summary>
          <p>{display.referencePopulation}</p>
          <p>Scoring version: {display.scoringVersion}</p>
        </details>
      )}
    </section>
  );
}

export default ScenarioRatings;
