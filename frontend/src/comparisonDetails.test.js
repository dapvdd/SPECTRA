import test from "node:test";
import assert from "node:assert/strict";

import {
  completeComparisonDetailRequest,
  createComparisonDetailState,
  failComparisonDetailRequest,
  getComparisonDetailsInSelectionOrder,
  removeComparisonDetail,
  startComparisonDetailRequest,
} from "./comparisonDetails.js";

const cpu = (id) => ({ id, name: `CPU ${id}` });
const detail = (id) => ({ id, name: `CPU ${id}`, specifications: {} });

test("comparison details follow selection order when requests resolve in order", () => {
  const compareList = [cpu(1), cpu(2)];
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 1, 1);
  state = startComparisonDetailRequest(state, 2, 2);
  state = completeComparisonDetailRequest(state, 1, 1, detail(1));
  state = completeComparisonDetailRequest(state, 2, 2, detail(2));

  assert.deepEqual(
    getComparisonDetailsInSelectionOrder(compareList, state.detailsById),
    [detail(1), detail(2)],
  );
});

test("out-of-order requests still render in compareList order", () => {
  const compareList = [cpu(1), cpu(2)];
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 1, 1);
  state = startComparisonDetailRequest(state, 2, 2);
  state = completeComparisonDetailRequest(state, 2, 2, detail(2));
  state = completeComparisonDetailRequest(state, 1, 1, detail(1));

  assert.deepEqual(
    getComparisonDetailsInSelectionOrder(compareList, state.detailsById),
    [detail(1), detail(2)],
  );
});

test("a removed CPU cannot re-enter state from a late response", () => {
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 1, 1);
  state = removeComparisonDetail(state, 1);
  const nextState = completeComparisonDetailRequest(state, 1, 1, detail(1));

  assert.deepEqual(nextState, state);
  assert.equal(nextState.detailsById[1], undefined);
  assert.equal(nextState.requestStatesById[1], undefined);
});

test("a stale request cannot overwrite a newer request for the same CPU", () => {
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 1, 1);
  state = startComparisonDetailRequest(state, 1, 2);
  state = completeComparisonDetailRequest(state, 1, 1, detail(1));

  assert.equal(state.detailsById[1], undefined);
  assert.equal(state.requestStatesById[1].status, "loading");

  state = completeComparisonDetailRequest(state, 1, 2, detail(1));
  assert.deepEqual(state.detailsById[1], detail(1));
  assert.equal(state.requestStatesById[1].status, "success");
});

test("failed comparison requests become explicit error states", () => {
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 2, 1);
  state = failComparisonDetailRequest(state, 2, 1);

  assert.equal(state.requestStatesById[2].status, "error");
  assert.equal(state.requestStatesById[2].message, "Unable to load CPU details.");
});

test("retry only changes the failed CPU and preserves the successful CPU", () => {
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 1, 1);
  state = completeComparisonDetailRequest(state, 1, 1, detail(1));
  state = startComparisonDetailRequest(state, 2, 2);
  state = failComparisonDetailRequest(state, 2, 2);
  state = startComparisonDetailRequest(state, 2, 3);

  assert.deepEqual(state.detailsById[1], detail(1));
  assert.equal(state.requestStatesById[1].status, "success");
  assert.equal(state.detailsById[2], undefined);
  assert.equal(state.requestStatesById[2].status, "loading");
});

test("removing a failed CPU leaves the other CPU intact", () => {
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 1, 1);
  state = completeComparisonDetailRequest(state, 1, 1, detail(1));
  state = startComparisonDetailRequest(state, 2, 2);
  state = failComparisonDetailRequest(state, 2, 2);
  state = removeComparisonDetail(state, 2);

  assert.deepEqual(state.detailsById[1], detail(1));
  assert.equal(state.requestStatesById[1].status, "success");
  assert.equal(state.detailsById[2], undefined);
  assert.equal(state.requestStatesById[2], undefined);
});

test("a successful CPU remains selectable when the second CPU fails", () => {
  const compareList = [cpu(1), cpu(2)];
  let state = createComparisonDetailState();
  state = startComparisonDetailRequest(state, 1, 1);
  state = completeComparisonDetailRequest(state, 1, 1, detail(1));
  state = startComparisonDetailRequest(state, 2, 2);
  state = failComparisonDetailRequest(state, 2, 2);

  assert.deepEqual(
    getComparisonDetailsInSelectionOrder(compareList, state.detailsById),
    [detail(1)],
  );
  assert.equal(state.requestStatesById[2].status, "error");
});
