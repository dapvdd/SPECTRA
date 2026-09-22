import { apiUrl } from "./api.js";

export const AI_ANALYSIS_STATUS = {
  idle: "idle",
  loading: "loading",
  success: "success",
  error: "error",
};

const EXPLANATION_ENDPOINT = apiUrl("/comparison/explanation");

export const requestComparisonExplanation = async (
  comparison,
  fetchImplementation = fetch
) => {
  const response = await fetchImplementation(EXPLANATION_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ comparison }),
  });

  if (!response.ok) {
    throw new Error(`Explanation request failed with status ${response.status}`);
  }

  const payload = await response.json();

  if (typeof payload.explanation !== "string" || payload.explanation.trim() === "") {
    throw new Error("Explanation response did not contain text.");
  }

  return payload.explanation;
};
