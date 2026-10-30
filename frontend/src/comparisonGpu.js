import { apiUrl } from "./api.js";

const GPU_COMPARISON_ENDPOINT = apiUrl("/comparison/gpu");

export const requestGpuComparison = async (
  hardwareIdA,
  hardwareIdB,
  fetchImplementation = fetch,
  signal = null
) => {
  const response = await fetchImplementation(GPU_COMPARISON_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      hardware_id_a: hardwareIdA,
      hardware_id_b: hardwareIdB,
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`GPU comparison request failed with status ${response.status}`);
  }

  return response.json();
};
