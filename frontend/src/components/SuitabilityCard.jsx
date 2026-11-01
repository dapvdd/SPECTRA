/**
 * SuitabilityCard
 *
 * Thin presentational wrapper: renders one workload category's suitability
 * rating delivered by GET /hardware/{id}/suitability. All formatting lives in
 * the pure `suitabilityDisplay` module (tested under node --test); this
 * component only maps that display data to markup.
 */

import { formatSuitabilityRating } from "../suitabilityDisplay.js";

export function SuitabilityCard({ rating }) {
  const display = formatSuitabilityRating(rating);

  return (
    <section
      className={`suitability-card ${display.specBased ? "spec-based" : ""} ${
        display.unrated ? "unrated" : ""
      }`}
      aria-label={`Suitability for ${display.category}`}
    >
      <header className="suitability-card-header">
        <h3 className="suitability-card-category">{display.category}</h3>
        <span
          className={`suitability-confidence ${display.confidenceBadge}`}
          aria-label={`confidence ${display.confidence}`}
        >
          {display.confidence}
        </span>
      </header>

      <div className="suitability-card-body">
        {display.unrated ? (
          <p className="suitability-unrated-reason">{display.unratedText}</p>
        ) : (
          <div
            className="suitability-stars"
            role="img"
            aria-label={display.starsAccessibleLabel}
            abbr={`${display.starsLabel}/5 stars`}
          >
            <span aria-hidden="true" className="suitability-stars-filled">
              {"★".repeat(display.stars)}
            </span>
            <span aria-hidden="true" className="suitability-stars-empty">
              {"★".repeat(5 - display.stars)}
            </span>
          </div>
        )}

        {display.specBased && (
          <p className="suitability-spec-based-tag">{display.specBasedLabel}</p>
        )}
      </div>

      {display.rationale.length > 0 && (
        <ul className="suitability-rationale">
          {display.rationale.slice(0, 3).map((reason, index) => (
            <li key={`${display.category}-reason-${index}`}>{reason}</li>
          ))}
        </ul>
      )}

      {display.caveats.length > 0 && (
        <ul className="suitability-caveats">
          {display.caveats.map((caveat, index) => (
            <li key={`${display.category}-caveat-${index}`}>{caveat}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default SuitabilityCard;
