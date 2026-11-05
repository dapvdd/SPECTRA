/**
 * useRecommendation
 *
 * Fetches ranked hardware recommendations from the backend
 * `GET /hardware/recommend` endpoint for a workload. Returns a stable loader
 * state so the HardwareFit modal can render without guessing.
 */

import { useEffect, useState } from "react";
import { apiUrl } from "../api.js";
import { getRecommendationEndpoint } from "../recommendationDisplay.js";

export function useRecommendation({ hardwareType, workload, limit }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isCancelled = false;

    if (!hardwareType || !workload) {
      setLoading(false);
      return undefined;
    }

    setLoading(true);
    setError(null);

    const endpoint = getRecommendationEndpoint(hardwareType, workload, limit);

    fetch(apiUrl(endpoint))
      .then((response) => {
        if (!response.ok) {
          throw new Error(`recommendation request failed (${response.status})`);
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
  }, [hardwareType, workload, limit]);

  return { data, loading, error };
}

export default useRecommendation;
