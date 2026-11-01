/**
 * useSuitability
 *
 * Fetches a hardware record's workload suitability ratings from the backend
 * `GET /hardware/{id}/suitability` endpoint. Returns a stable loader state so
 * the UI can render without guessing at values while a request is in flight.
 */

import { useEffect, useState } from "react";
import { apiUrl } from "../api.js";
import { getSuitabilityEndpoint } from "../suitabilityDisplay.js";

export function useSuitability(hardwareId, { enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isCancelled = false;

    if (!enabled) {
      return undefined;
    }

    if (hardwareId === undefined || hardwareId === null) {
      setError(new Error("hardwareId is required"));
      setLoading(false);
      return undefined;
    }

    setLoading(true);
    setError(null);

    fetch(apiUrl(getSuitabilityEndpoint(hardwareId)))
      .then((response) => {
        if (!response.ok) {
          throw new Error(`suitability request failed (${response.status})`);
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
    };
  }, [hardwareId, enabled]);

  return { data, loading, error };
}

export default useSuitability;
