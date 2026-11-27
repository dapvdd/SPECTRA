/**
 * useScenarioRatings (M4 Task 7)
 *
 * Fetches per-hardware scenario ratings from the backend endpoint served by
 * the M4 scenario scoring engine (M4-SCORING-v2.0). Returns a stable loader
 * state; UNKNOWN scenarios stay UNKNOWN (never rendered as 0 stars by the
 * caller — see formatScenarioEntry).
 */

import { useEffect, useState } from "react";
import { apiUrl } from "../api.js";

export const getScenarioRatingsEndpoint = (hardwareId) =>
  `/hardware/${hardwareId}/scenarios`;

export function useScenarioRatings(hardwareId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isCancelled = false;

    if (!hardwareId) {
      setLoading(false);
      return undefined;
    }

    setLoading(true);
    setError(null);

    fetch(apiUrl(getScenarioRatingsEndpoint(hardwareId)))
      .then((response) => {
        if (!response.ok) {
          throw new Error(`scenario ratings request failed (${response.status})`);
        }
        return response.json();
      })
      .then((json) => {
        if (!isCancelled) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err);
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
      setLoading(false);
    };
  }, [hardwareId]);

  return { data, loading, error };
}

export default useScenarioRatings;
