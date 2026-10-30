import { apiUrl } from "./api.js";
import {
  assertSuccessfulResponse,
  validateCatalogPayload,
} from "./apiValidation.js";

export const HARDWARE_TYPES = ["All", "CPU", "GPU"];

/* Derived from the current DB snapshot (3,501 CPU + 1,879 GPU records):
   CPU vendors: Intel (2,784), AMD (717)
   GPU vendors: NVIDIA (876), AMD (722), Intel (175), ATI (106 legacy)
   All GPU ATI records carry manufacturer "ATI"; they are AMD-branded legacy parts
   kept distinct for provenance accuracy. */
export const MANUFACTURER_FILTERS = [
  "All",
  "Intel",
  "AMD",
  "NVIDIA",
  "ATI",
];

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

/* The catalog result count belongs to the catalog, so its label and scope are
   derived here next to the summary rather than hand-assembled in the view.
   Keeping one owner means the count, its noun and its filter scope can never
   disagree with the summary line printed beside them. */
export const getCatalogReadout = ({
  totalCount = 0,
  manufacturerFilter = "All",
  typeFilter = "All",
} = {}) => {
  const recordNoun =
    typeFilter === "All" ? "hardware records" : `${typeFilter} records`;

  return {
    value: totalCount,
    label: `matching ${recordNoun}`,
    meta:
      manufacturerFilter === "All" ? "All manufacturers" : manufacturerFilter,
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

export const getHardwareCatalogUrl = (
  type = "All",
  {
    q = "",
    manufacturer = "All",
    segment = "",
    limit,
    offset = 0,
  } = {}
) => {
  const params = new URLSearchParams();

  if (type && type !== "All") {
    params.set("type", type);
  }

  if (q) {
    params.set("q", q);
  }

  if (manufacturer && manufacturer !== "All") {
    params.set("manufacturer", manufacturer);
  }

  if (segment) {
    params.set("segment", segment);
  }

  if (limit != null) {
    params.set("limit", String(limit));
  }

  if (offset > 0) {
    params.set("offset", String(offset));
  }

  const query = params.toString();
  return query ? apiUrl(`/hardware?${query}`) : apiUrl("/hardware");
};

export const requestHardwareCatalog = async (
  type = "All",
  fetchImplementation = fetch
) => {
  const response = await fetchImplementation(getHardwareCatalogUrl(type));
  const payload = await assertSuccessfulResponse(response).json();
  return validateCatalogPayload(payload);
};

/* Server-driven page: sends filters + pagination to the backend and honors the
   X-Total-Count header so the UI can page without guessing totals. This is the
   Phase 1.3 frontend entry point; the plain requestHardwareCatalog above stays
   backward-compatible for callers that do not need pagination. */
export const requestHardwareCatalogPage = async (
  type = "All",
  {
    q = "",
    manufacturer = "All",
    segment = "",
    limit,
    offset = 0,
  } = {},
  fetchImplementation = fetch
) => {
  const response = await fetchImplementation(
    getHardwareCatalogUrl(type, { q, manufacturer, segment, limit, offset })
  );

  const totalCountHeader = response.headers?.get?.("x-total-count");

  const payload = await assertSuccessfulResponse(response).json();
  const items = validateCatalogPayload(payload);

  const totalCount =
    totalCountHeader != null && !Number.isNaN(Number(totalCountHeader))
      ? Number(totalCountHeader)
      : items.length;

  return { items, totalCount };
};

/* Facet counts tell the UI what the next click would do before it clicks: the
   counts are computed server-side under the *same* filters the catalog query
   uses, so they stay accurate even when those filters change. */
export const getHardwareFacetsUrl = (
  {
    type = "All",
    q = "",
    manufacturer = "All",
    segment = "",
  } = {}
) => {
  const params = new URLSearchParams();

  if (type && type !== "All") {
    params.set("type", type);
  }

  if (q) {
    params.set("q", q);
  }

  if (manufacturer && manufacturer !== "All") {
    params.set("manufacturer", manufacturer);
  }

  if (segment) {
    params.set("segment", segment);
  }

  const query = params.toString();
  return query ? apiUrl(`/hardware/facets?${query}`) : apiUrl("/hardware/facets");
};

export const requestHardwareFacets = async (
  filters = {},
  fetchImplementation = fetch
) => {
  const response = await fetchImplementation(getHardwareFacetsUrl(filters));
  const payload = await assertSuccessfulResponse(response).json();
  return payload;
};

export const createCatalogLoadGuard = () => {
  let currentRequestId = 0;

  return {
    begin: () => (currentRequestId += 1),
    isCurrent: (requestId) => requestId === currentRequestId,
    invalidate: () => (currentRequestId += 1),
  };
};