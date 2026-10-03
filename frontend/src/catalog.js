import { apiUrl } from "./api.js";
import {
  assertSuccessfulResponse,
  validateCatalogPayload,
} from "./apiValidation.js";

export const HARDWARE_TYPES = ["All", "CPU", "GPU"];

export const MANUFACTURER_FILTERS = ["All", "Intel", "AMD"];

const TYPE_LABELS = {
  CPU: "CPUs",
  GPU: "GPUs",
};

export const getCatalogTypeLabel = (type) => TYPE_LABELS[type] || "hardware records";

export const getCatalogFilterState = (value, activeValue) => {
  const isActive = value === activeValue;

  return {
    isActive,
    className: isActive ? "filter-button active" : "filter-button",
    pressed: isActive,
  };
};

export const getCatalogResultSummary = ({
  loading = false,
  error = "",
  visibleCount = 0,
  totalCount = 0,
  manufacturerFilter = "All",
  typeFilter = "All",
} = {}) => {
  if (loading) {
    return "Loading hardware catalog...";
  }

  if (error) {
    return "Hardware catalog unavailable";
  }

  const typeLabel = getCatalogTypeLabel(typeFilter);
  const scope =
    manufacturerFilter === "All" ? typeLabel : `${manufacturerFilter} ${typeLabel}`;

  if (totalCount === 0) {
    return `No ${scope} match the current filters`;
  }

  return `Showing ${Math.min(visibleCount, totalCount)} of ${totalCount} ${scope}`;
};

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