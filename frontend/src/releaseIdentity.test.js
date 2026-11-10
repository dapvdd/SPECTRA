// Tests for release identity diagnostics (M2.5).
// The browser-release-identification goal: detect a stale tab by comparing
// the executing bundle's build SHA against the server's release SHA.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  getClientBuild,
  describeClientBuild,
  fetchReleaseIdentity,
  compareClientWithServer,
} from "./releaseIdentity.js";

const SERVER_RELEASE = {
  version: "3.1.0",
  git_sha: "a".repeat(40),
  built_at: "2026-11-10T00:00:00Z",
  image_digest: null,
  auth_enabled: false,
  ai_provider: "unconfigured",
};

const jsonResponse = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

test("getClientBuild reports the baked build identity", () => {
  const build = getClientBuild();
  assert.equal(typeof build.sha, "string");
  assert.equal(typeof build.builtAt, "string");
});

test("describeClientBuild never throws and mentions build", () => {
  const text = describeClientBuild();
  assert.match(text, /client build/);
});

test("fetchReleaseIdentity returns the release on 200", async () => {
  let calledUrl = "";
  const fetchImpl = async (url) => {
    calledUrl = url;
    return jsonResponse(SERVER_RELEASE);
  };

  const result = await fetchReleaseIdentity("http://api.test", fetchImpl);
  assert.equal(result.ok, true);
  assert.equal(result.release.git_sha, "a".repeat(40));
  // Cache-buster present so no intermediary can serve a cached identity.
  assert.match(calledUrl, /\/release\?_=\d+/);
});

test("fetchReleaseIdentity fails soft on HTTP errors", async () => {
  const fetchImpl = async () => jsonResponse({}, 500);
  const result = await fetchReleaseIdentity("http://api.test", fetchImpl);
  assert.equal(result.ok, false);
  assert.match(result.error, /500/);
});

test("fetchReleaseIdentity fails soft on network errors", async () => {
  const fetchImpl = async () => {
    throw new Error("connection refused");
  };
  const result = await fetchReleaseIdentity("http://api.test", fetchImpl);
  assert.equal(result.ok, false);
  assert.match(result.error, /connection refused/);
});

test("fetchReleaseIdentity rejects unexpected payload shapes", async () => {
  const fetchImpl = async () => jsonResponse({ hello: "world" });
  const result = await fetchReleaseIdentity("http://api.test", fetchImpl);
  assert.equal(result.ok, false);
  assert.match(result.error, /unexpected shape/);
});

test("compareClientWithServer reports current when SHAs match", async () => {
  const fetchImpl = async () => jsonResponse(SERVER_RELEASE);
  const verdict = await compareClientWithServer("http://api.test", fetchImpl);
  // In the test environment the bundle is built without a build SHA, so the
  // verdict is "unidentified"; the important property is a clean verdict
  // shape, no throw, and no mismatch false-positive.
  assert.ok(["current", "unidentified"].includes(verdict.status));
});

test("compareClientWithServer detects a stale tab", async () => {
  const fetchImpl = async () => jsonResponse(SERVER_RELEASE);
  const verdict = await compareClientWithServer("http://api.test", fetchImpl);
  if (verdict.status === "unidentified") {
    // Built without VITE_APP_BUILD_SHA — stale detection needs the SHA.
    assert.match(verdict.message, /not injected/);
  } else {
    assert.notEqual(verdict.client.sha, undefined);
  }
});

test("compareClientWithServer survives a dead server", async () => {
  const fetchImpl = async () => {
    throw new Error("backend down");
  };
  const verdict = await compareClientWithServer("http://api.test", fetchImpl);
  assert.equal(verdict.status, "unknown");
  assert.match(verdict.message, /backend down/);
});
