import test from "node:test";
import assert from "node:assert/strict";

import {
  addComparisonSelection,
  clearComparisonSelection,
  completeCatalogLoad,
  completeDetailNavigation,
  createCatalogState,
  createDetailNavigationState,
  failCatalogLoad,
  failDetailNavigation,
  removeComparisonSelection,
  returnToCatalogState,
  setBenchmarkError,
  setBenchmarkLoading,
  setBenchmarkSuccess,
  startDetailNavigation,
} from "./appState.js";
import {
  completeComparisonDetailRequest,
  createComparisonDetailState,
  failComparisonDetailRequest,
  startComparisonDetailRequest,
} from "./comparisonDetails.js";

const cpu = (id) => ({ id, name: `CPU ${id}` });

test("catalog load transitions from loading to the normal catalog state", () => {
  const state = completeCatalogLoad(createCatalogState(), [cpu(1)]);

  assert.deepEqual(state, { items: [cpu(1)], loading: false, error: "" });
});

test("catalog failures become an explicit catalog error state", () => {
  const state = failCatalogLoad(createCatalogState(), "Catalog unavailable");

  assert.equal(state.loading, false);
  assert.equal(state.error, "Catalog unavailable");
  assert.deepEqual(state.items, []);
});

test("detail navigation exposes loading, success, error, and catalog return states", () => {
  const loading = startDetailNavigation(createDetailNavigationState());
  assert.equal(loading.view, true);
  assert.equal(loading.loading, true);

  const success = completeDetailNavigation(loading, { ...cpu(1), specifications: {} });
  assert.equal(success.loading, false);
  assert.equal(success.selected.id, 1);

  const error = failDetailNavigation(loading, "Detail unavailable");
  assert.equal(error.loading, false);
  assert.equal(error.error, "Detail unavailable");

  assert.deepEqual(returnToCatalogState(success), {
    selected: null,
    view: false,
    loading: false,
    error: "",
  });
});

test("comparison selection enforces uniqueness and two-CPU capacity", () => {
  const first = [cpu(1)];
  const second = addComparisonSelection(first, cpu(2));

  assert.deepEqual(second, [cpu(1), cpu(2)]);
  assert.strictEqual(addComparisonSelection(second, cpu(2)), second);
  assert.strictEqual(addComparisonSelection(second, cpu(3)), second);
  assert.deepEqual(removeComparisonSelection(second, 1), [cpu(2)]);
  assert.deepEqual(removeComparisonSelection(second, 2), [cpu(1)]);
  assert.deepEqual(clearComparisonSelection(), []);
});

test("benchmark loading, success, and error remain isolated by CPU", () => {
  let states = setBenchmarkLoading({}, 1);
  states = setBenchmarkSuccess(states, 1, [{ score: 100 }]);
  states = setBenchmarkLoading(states, 2);
  states = setBenchmarkError(states, 2, "Benchmark unavailable");

  assert.deepEqual(states[1], { status: "success", results: [{ score: 100 }] });
  assert.deepEqual(states[2], {
    status: "error",
    message: "Benchmark unavailable",
    results: null,
  });
});

test("comparison selection composes with loading, error, and retry states", () => {
  const selection = addComparisonSelection(addComparisonSelection([], cpu(1)), cpu(2));
  let state = createComparisonDetailState();

  state = startComparisonDetailRequest(state, selection[0].id, 1);
  state = completeComparisonDetailRequest(state, selection[0].id, 1, {
    ...cpu(1),
    specifications: {},
  });
  state = startComparisonDetailRequest(state, selection[1].id, 2);
  assert.equal(state.requestStatesById[2].status, "loading");

  state = failComparisonDetailRequest(state, selection[1].id, 2);
  assert.equal(state.requestStatesById[2].status, "error");
  assert.equal(state.detailsById[1].id, 1);

  state = startComparisonDetailRequest(state, selection[1].id, 3);
  assert.equal(state.requestStatesById[1].status, "success");
  assert.equal(state.requestStatesById[2].status, "loading");
});

test("comparison details preserve selection order when the second response wins the race", () => {
  const selection = [cpu(1), cpu(2)];
  const detailsById = { 2: { ...cpu(2), specifications: {} }, 1: { ...cpu(1), specifications: {} } };

  assert.deepEqual(
    selection.map((item) => detailsById[item.id]),
    [detailsById[1], detailsById[2]],
  );
});
