import { apiUrl } from "./api.js";
import {
  assertSuccessfulResponse,
  validateCatalogPayload,
} from "./apiValidation.js";

export const HARDWARE_TYPES = ["All", "CPU", "GPU"];

export const getHardwareCatalogUrl = (type = "All") =>
  type && type !== "All"
    ? apiUrl(`/hardware?type=${encodeURIComponent(type)}`)
    : apiUrl("/hardware");

export const requestHardwareCatalog = async (
  type = "All",
  fetchImplementation = fetch
) => {
  const response = await fetchImplementation(getHardwareCatalogUrl(type));
  const payload = await assertSuccessfulResponse(response).json();
  return validateCatalogPayload(payload);
};

export const createCatalogLoadGuard = () => {
  let currentRequestId = 0;

  return {
    begin: () => (currentRequestId += 1),
    isCurrent: (requestId) => requestId === currentRequestId,
    invalidate: () => (currentRequestId += 1),
  };
};