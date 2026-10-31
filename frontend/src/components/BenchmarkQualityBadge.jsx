/**
 * BenchmarkQualityBadge
 *
 * Renders the benchmark quality indicator returned by the backend's
 * GET /hardware/{id}/benchmarks (Phase 1.2/2.3). The `quality` field is an
 * additive, compute-only heuristic over provenance signals; it is never
 * authored client-side, so no data is fabricated here.
 *
 * Tiers (from backend score_benchmark_quality / quality_to_response_field):
 *   high   -> green "High"
 *   medium -> amber "Medium"
 *   low    -> red "Low"
 *   null   -> grey "No score" (evidence vetoed / unscored row)
 */

const BADGE_LABELS = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

const BADGE_LONG_LABELS = {
  high: "High quality evidence",
  medium: "Medium quality evidence",
  low: "Low quality evidence",
};

function _getQualityBadgeClass(quality) {
  if (!quality || typeof quality !== "object") {
    return "badge-none";
  }

  const band = quality.band;

  if (band === "high" || band === "medium" || band === "low") {
    return `badge-${band}`;
  }

  return "badge-none";
}

export function BenchmarkQualityBadge({ quality, className = "" }) {
  const badgeClass = _getQualityBadgeClass(quality);
  const label = !quality
    ? "No score"
    : BADGE_LABELS[quality.band] ?? "No score";
  const longLabel = !quality
    ? "No quality score for this benchmark record."
    : (BADGE_LONG_LABELS[quality.band] ??
      "No quality score for this benchmark record.");

  return (
    <span
      className={`benchmark-quality-badge ${badgeClass} ${className}`.trim()}
      title={longLabel}
      aria-label={longLabel}
      role="text"
    >
      <span aria-hidden="true" className="benchmark-quality-dot" />
      {label}
    </span>
  );
}

export default BenchmarkQualityBadge;
