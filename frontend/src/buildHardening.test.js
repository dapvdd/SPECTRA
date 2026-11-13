/* M2.5 Task 6: state, accessibility & microcopy hardening.
 *
 * F6 — the build chat restore must read a live ref mirror of the build detail
 *      state, not the render-scope snapshot captured when the slot request
 *      started (stale-closure regression).
 * F7 — the compatibility check must not POST for an empty build.
 * F8 — build slot prose must humanize the raw uppercase slot constants.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  completeBuildDetailRequest,
  createBuildDetailState,
  getBuildChatSnapshot,
  hasSelectedBuildComponent,
  startBuildDetailRequest,
} from "./buildConfig.js";
import { getBuildChatToken, resolveBuildChatRestore } from "./buildChat.js";

const cpuDetail = {
  id: 1,
  name: "AMD Ryzen 7 7800X3D",
  manufacturer: "AMD",
  type: "CPU",
  specifications: { cores: 8, threads: 16, tdp_w: 120, socket: "AM5" },
};

const gpuDetail = {
  id: 3361,
  name: "NVIDIA GeForce RTX 5070 Ti",
  manufacturer: "NVIDIA",
  type: "GPU",
  specifications: { memory_gb: 16, tdp_w: 300, interface: "PCIe 5.0 x16" },
};

const userContext = { useCase: "Gaming", resolution: "1440p" };

const detailStateWith = (slots) => {
  let state = createBuildDetailState();
  let requestId = 1;

  for (const [slot, detail] of Object.entries(slots)) {
    state = startBuildDetailRequest(state, slot, requestId);
    state = completeBuildDetailRequest(state, slot, requestId, detail);
    requestId += 1;
  }

  return state;
};

/* ---------- F6: restore pairing reads the supplied snapshot ---------- */

test("restore ignores slots that are not part of the chat identity", () => {
  const state = detailStateWith({ CPU: cpuDetail, GPU: gpuDetail });

  for (const slot of ["RAM", "STORAGE", "MOTHERBOARD", "PSU"]) {
    assert.equal(resolveBuildChatRestore(state, slot, cpuDetail, userContext), null);
  }
});

test("restore resolves the CPU+GPU pair and the chat token from the snapshot", () => {
  const state = detailStateWith({ CPU: cpuDetail, GPU: gpuDetail });
  const restore = resolveBuildChatRestore(state, "GPU", gpuDetail, userContext);

  assert.equal(restore.cpuId, 1);
  assert.equal(restore.gpuId, 3361);
  assert.equal(
    restore.token,
    getBuildChatToken(getBuildChatSnapshot(cpuDetail, gpuDetail, userContext))
  );
});

test("restore waits until the other slot detail is present", () => {
  const empty = createBuildDetailState();
  assert.equal(resolveBuildChatRestore(empty, "GPU", gpuDetail, userContext), null);
  assert.equal(resolveBuildChatRestore(empty, "CPU", cpuDetail, userContext), null);
});

test("restore pairs a late CPU with the GPU already in the snapshot (stale-closure regression)", () => {
  /* The stale-closure bug: the GPU detail commits first, then the CPU request
     resolves. The restore must read the GPU from the current snapshot, not the
     render scope captured when the CPU request started (which had no GPU). */
  const staleSnapshot = createBuildDetailState();
  assert.equal(
    resolveBuildChatRestore(staleSnapshot, "CPU", cpuDetail, userContext),
    null
  );

  const currentSnapshot = detailStateWith({ GPU: gpuDetail });
  const restore = resolveBuildChatRestore(currentSnapshot, "CPU", cpuDetail, userContext);

  assert.equal(restore.cpuId, 1);
  assert.equal(restore.gpuId, 3361);
});

/* ---------- F7: empty-build compatibility short-circuit ---------- */

test("an empty build has no selected component", () => {
  assert.equal(
    hasSelectedBuildComponent({
      cpu: null,
      gpu: null,
      ram: null,
      storage: null,
      motherboard: null,
      psu: null,
    }),
    false
  );
  assert.equal(hasSelectedBuildComponent({}), false);
  assert.equal(hasSelectedBuildComponent(null), false);
});

test("any positive slot id counts as a selection", () => {
  assert.equal(hasSelectedBuildComponent({ cpu: 1, gpu: null }), true);
  assert.equal(hasSelectedBuildComponent({ cpu: 0, gpu: null }), false);
  assert.equal(hasSelectedBuildComponent({ cpu: null, psu: 5 }), true);
});

/* ---------- App wiring contracts ---------- */

const appSource = readFileSync(new URL("./App.jsx", import.meta.url), "utf8");

test("the build detail restore reads a live ref mirror, not the render-scope state", () => {
  assert.equal(appSource.includes("buildDetailStateRef"), true);
  assert.equal(appSource.includes("resolveBuildChatRestore("), true);
  assert.equal(appSource.includes("getBuildSlotDetail(buildDetailState, otherSlot)"), false);
});

test("the compatibility effect short-circuits an empty build", () => {
  assert.equal(appSource.includes("hasSelectedBuildComponent"), true);
});

test("build slot prose never leaks the raw uppercase slot constants", () => {
  assert.equal(appSource.includes("Select a {type}"), false);
  assert.equal(appSource.includes("Browse {type} catalog"), false);
  assert.equal(
    appSource.includes('<span className="build-summary-label">{type}</span>'),
    false
  );
  assert.equal(appSource.includes("getBuildSlotDisplayName"), true);
});
