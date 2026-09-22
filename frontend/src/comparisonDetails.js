export const createComparisonDetailState = () => ({
  detailsById: {},
  requestStatesById: {},
});

const isCurrentRequest = (state, hardwareId, requestId) =>
  state.requestStatesById[hardwareId]?.requestId === requestId;

export const startComparisonDetailRequest = (state, hardwareId, requestId) => {
  const detailsById = { ...state.detailsById };
  delete detailsById[hardwareId];

  return {
    detailsById,
    requestStatesById: {
      ...state.requestStatesById,
      [hardwareId]: { status: "loading", requestId },
    },
  };
};

export const completeComparisonDetailRequest = (
  state,
  hardwareId,
  requestId,
  detail,
) => {
  if (!isCurrentRequest(state, hardwareId, requestId)) {
    return state;
  }

  return {
    detailsById: {
      ...state.detailsById,
      [hardwareId]: detail,
    },
    requestStatesById: {
      ...state.requestStatesById,
      [hardwareId]: { status: "success", requestId },
    },
  };
};

export const failComparisonDetailRequest = (
  state,
  hardwareId,
  requestId,
  message = "Unable to load CPU details.",
) => {
  if (!isCurrentRequest(state, hardwareId, requestId)) {
    return state;
  }

  return {
    detailsById: state.detailsById,
    requestStatesById: {
      ...state.requestStatesById,
      [hardwareId]: { status: "error", requestId, message },
    },
  };
};

export const removeComparisonDetail = (state, hardwareId) => {
  const detailsById = { ...state.detailsById };
  const requestStatesById = { ...state.requestStatesById };
  delete detailsById[hardwareId];
  delete requestStatesById[hardwareId];

  return { detailsById, requestStatesById };
};

export const getComparisonDetailsInSelectionOrder = (
  compareList,
  detailsById,
) => compareList.map((item) => detailsById[item.id]).filter(Boolean);
