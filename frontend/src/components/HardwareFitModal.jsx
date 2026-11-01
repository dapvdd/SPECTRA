/**
 * HardwareFitModal
 *
 * Interactive Hardware Fit experience: pick a workload and see how the current
 * hardware suits it plus the top recommended alternatives. The current
 * hardware's ratings come from GET /hardware/{id}/suitability; alternatives
 * come from GET /hardware/recommend.
 *
 * Accessible: aria-modal, ESC to close, closing button, focus returned by the
 * caller. All formatting is delegated to the pure suitability/recommendation
 * display modules (tested under node --test).
 */

import { useEffect, useRef, useState } from "react";
import { CATEGORIES } from "../suitabilityDisplay.js";
import {
  formatRecommendationCandidate,
} from "../recommendationDisplay.js";
import { useSuitability } from "../hooks/useSuitability.js";
import { useRecommendation } from "../hooks/useRecommendation.js";
import { SuitabilityCard } from "./SuitabilityCard.jsx";

const RESOLUTIONS = [null, "1080p", "1440p", "4k"];

export function HardwareFitModal({
  hardwareId,
  hardwareName,
  hardwareType,
  onClose,
  onCompare,
}) {
  const [workload, setWorkload] = useState("gaming");
  const [resolution, setResolution] = useState(null);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose?.();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const { data: suitability, loading: loadingFit, error: fitError } =
    useSuitability(hardwareId);
  const { data: recommendations, loading: loadingRec, error: recError } =
    useRecommendation({
      hardwareType: hardwareType || suitability?.hardware_type,
      workload,
      limit: 3,
    });

  const currentRatings = suitability?.ratings || [];
  const candidates = (recommendations?.candidates || []).map(
    formatRecommendationCandidate,
  );

  return (
    <div
      className="hardware-fit-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Hardware Fit"
    >
      <div className="hardware-fit-modal-panel">
        <header className="hardware-fit-modal-header">
          <h2>Hardware Fit</h2>
          <p className="hardware-fit-modal-name">{hardwareName}</p>
          <button
            ref={closeButtonRef}
            type="button"
            className="hardware-fit-close"
            onClick={onClose}
            aria-label="Close Hardware Fit"
          >
            ×
          </button>
        </header>

        <div className="hardware-fit-workloads" role="tablist">
          {CATEGORIES.map((category) => (
            <button
              key={category}
              type="button"
              role="tab"
              aria-selected={workload === category}
              className={
                workload === category ? "hardware-fit-workload active" : "hardware-fit-workload"
              }
              onClick={() => setWorkload(category)}
            >
              {category.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="hardware-fit-options">
          <label>
            Resolution
            <select
              value={resolution ?? ""}
              onChange={(event) =>
                setResolution(event.target.value || null)
              }
            >
              <option value="">Any</option>
              {RESOLUTIONS.filter(Boolean).map((res) => (
                <option key={res} value={res}>
                  {res}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="hardware-fit-section">
          <h3>This hardware · {workload.replace("_", " ")}</h3>
          {fitError && <p className="hardware-fit-error">{String(fitError)}</p>}
          {loadingFit && <p className="hardware-fit-loading">Loading…</p>}
          {!loadingFit && !fitError && (
            <SuitabilityCard
              rating={
                currentRatings.find((r) => r.category === workload) || {
                  category: workload,
                  stars: 0,
                  confidence: "unrated",
                  rationale: [],
                  caveats: [],
                }
              }
            />
          )}
        </div>

        <div className="hardware-fit-section">
          <h3>Recommended alternatives</h3>
          {recError && <p className="hardware-fit-error">{String(recError)}</p>}
          {loadingRec && <p className="hardware-fit-loading">Loading…</p>}
          {!loadingRec && !recError && candidates.length === 0 && (
            <p className="hardware-fit-empty">
              No candidates passed the evidence threshold for this workload.
            </p>
          )}
          {!loadingRec &&
            !recError &&
            candidates.map((candidate) => (
              <div key={candidate.id} className="hardware-fit-candidate">
                <div className="hardware-fit-candidate-head">
                  <strong>{candidate.name}</strong>
                  <span
                    className={`suitability-confidence ${candidate.confidenceBadge}`}
                  >
                    {candidate.confidence}
                  </span>
                </div>
                <div
                  className="suitability-stars"
                  role="img"
                  aria-label={candidate.starsAccessibleLabel}
                >
                  <span aria-hidden="true">{"★".repeat(candidate.stars)}</span>
                  <span aria-hidden="true">
                    {"★".repeat(5 - candidate.stars)}
                  </span>
                </div>
                {candidate.primaryRationale && (
                  <p className="hardware-fit-candidate-rationale">
                    {candidate.primaryRationale}
                  </p>
                )}
                {onCompare && (
                  <button
                    type="button"
                    className="hardware-fit-compare"
                    onClick={() =>
                      onCompare?.(candidate.id, workload, resolution)
                    }
                  >
                    Compare
                  </button>
                )}
              </div>
            ))}
        </div>

        <footer className="hardware-fit-modal-footer">
          <button type="button" className="hardware-fit-close-btn" onClick={onClose}>
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}

export default HardwareFitModal;
