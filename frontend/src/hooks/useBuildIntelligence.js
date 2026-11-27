/**
 * useBuildIntelligence (M4 Task 7)
 *
 * POSTs a build context to /build/intelligence (M4-BUILD-v1.0) and exposes
 * the analyze payload. Balance UNKNOWN / power reference labeling / MISSING
 * slots pass through untouched: this hook never substitutes values.
 */

import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "../api.js";
import {
  BUILD_INTELLIGENCE_ENDPOINT,
  buildIntelligenceRequestBody,
} from "../recommendationV2.js";

export function useBuildIntelligence(components) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const serialized = JSON.stringify(components || {});

  const analyze = useCallback(
    (nextComponents) => {
      const body = JSON.stringify(buildIntelligenceRequestBody(nextComponents));
      setLoading(true);
      setError(null);
      return fetch(apiUrl(BUILD_INTELLIGENCE_ENDPOINT), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(
              `build intelligence request failed (${response.status})`,
            );
          }
          return response.json();
        })
        .then((json) => {
          setData(json);
          setLoading(false);
          return json;
        })
        .catch((err) => {
          setError(err);
          setLoading(false);
          return null;
        });
    },
    [],
  );

  useEffect(() => {
    let isCancelled = false;
    const parsed = JSON.parse(serialized);
    const hasAny = Object.values(parsed || {}).some((v) => v != null);
    if (!hasAny) {
      setData(null);
      setLoading(false);
      setError(null);
      return undefined;
    }
    setLoading(true);
    setError(null);
    fetch(apiUrl(BUILD_INTELLIGENCE_ENDPOINT), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildIntelligenceRequestBody(parsed)),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(
            `build intelligence request failed (${response.status})`,
          );
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
  }, [serialized]);

  return { data, loading, error, analyze };
}

export default useBuildIntelligence;
