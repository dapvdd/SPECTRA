export const createCatalogState = () => ({
  items: [],
  loading: true,
  error: "",
});

export const completeCatalogLoad = (state, items) => ({
  ...state,
  items,
  loading: false,
  error: "",
});

export const failCatalogLoad = (state, message) => ({
  ...state,
  loading: false,
  error: message,
});

export const createDetailNavigationState = () => ({
  selected: null,
  view: false,
  loading: false,
  error: "",
});

export const startDetailNavigation = (state) => ({
  ...state,
  selected: null,
  view: true,
  loading: true,
  error: "",
});

export const completeDetailNavigation = (state, detail) => ({
  ...state,
  selected: detail,
  loading: false,
  error: "",
});

export const failDetailNavigation = (state, message) => ({
  ...state,
  loading: false,
  error: message,
});

export const returnToCatalogState = (state) => ({
  ...state,
  selected: null,
  view: false,
  loading: false,
  error: "",
});

export const addComparisonSelection = (compareList, item) => {
  if (
    compareList.some((hardware) => hardware.id === item.id) ||
    compareList.length >= 2
  ) {
    return compareList;
  }

  return [...compareList, item];
};

export const removeComparisonSelection = (compareList, id) =>
  compareList.filter((item) => item.id !== id);

export const clearComparisonSelection = () => [];

export const setBenchmarkLoading = (states, hardwareId) => ({
  ...states,
  [hardwareId]: { status: "loading", results: null },
});

export const setBenchmarkSuccess = (states, hardwareId, results) => ({
  ...states,
  [hardwareId]: { status: "success", results },
});

export const setBenchmarkError = (states, hardwareId, message) => ({
  ...states,
  [hardwareId]: { status: "error", message, results: null },
});

export const removeBenchmarkState = (states, hardwareId) => {
  const next = { ...states };
  delete next[hardwareId];
  return next;
};
