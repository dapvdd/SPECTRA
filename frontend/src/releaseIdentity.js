// Release identity diagnostics (M2.5 / browser release identification).
//
// A stale browser tab can keep executing an old JS bundle long after the
// server has moved to a newer release (the V3 cache incident). This module
// gives the operator — and optionally the UI — a way to see WHICH release
// the page is talking to:
//
// - `fetchReleaseIdentity()` asks the backend's read-only /api/release
//   endpoint. The fetch always bypasses HTTP caches (cache: "no-store" plus
//   a cache-busting query param) so the answer reflects the SERVER's current
//   release, never a cached one.
// - `describeClientBuild()` reports the build-time identity of the bundle
//   actually executing in the tab (Vite bakes VITE_APP_BUILD_SHA at build
//   time). Comparing the two exposes a stale tab immediately: client build
//   SHA differs from server release SHA.
//
// Safety: the release endpoint carries no secrets (verified by
// backend/app/test_release.py). The module never logs, never retries in a
// loop, and fails soft — a diagnostics failure must never break the app.

import { apiUrl, API_BASE_URL } from "./api.js";

const CLIENT_BUILD_SHA = import.meta.env?.VITE_APP_BUILD_SHA ?? "unknown";
const CLIENT_BUILD_TIME = import.meta.env?.VITE_APP_BUILD_TIME ?? "unknown";

export const getClientBuild = () => ({
  sha: CLIENT_BUILD_SHA,
  builtAt: CLIENT_BUILD_TIME,
});

export const describeClientBuild = () => {
  const build = getClientBuild();
  if (build.sha === "unknown") {
    return "client build: unknown (built without VITE_APP_BUILD_SHA)";
  }
  return `client build: ${build.sha.slice(0, 12)} (built ${build.builtAt})`;
};

/**
 * Fetch the server's release identity with caches defeated.
 * Returns { ok: true, release } or { ok: false, error } — never throws.
 */
export const fetchReleaseIdentity = async (
  configuredBaseUrl = API_BASE_URL,
  fetchImpl = globalThis.fetch,
) => {
  if (typeof fetchImpl !== "function") {
    return { ok: false, error: "fetch unavailable" };
  }

  const url = `${apiUrl("/release", configuredBaseUrl)}?_=${Date.now()}`;

  try {
    const response = await fetchImpl(url, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return { ok: false, error: `release endpoint returned ${response.status}` };
    }
    const release = await response.json();
    if (!release || typeof release !== "object" || !("git_sha" in release)) {
      return { ok: false, error: "release endpoint returned an unexpected shape" };
    }
    return { ok: true, release };
  } catch (error) {
    return { ok: false, error: error?.message ?? "release fetch failed" };
  }
};

/**
 * Compare the executing bundle against the server release.
 * Returns a plain-language verdict for diagnostics display.
 */
export const compareClientWithServer = async (configuredBaseUrl, fetchImpl) => {
  const [clientBuild, serverResult] = await Promise.resolve().then(() =>
    fetchReleaseIdentity(configuredBaseUrl, fetchImpl),
  ).then((server) => [getClientBuild(), server]);

  if (!serverResult.ok) {
    return {
      status: "unknown",
      message: `server release unavailable: ${serverResult.error}`,
      client: clientBuild,
    };
  }

  const serverSha = serverResult.release.git_sha;
  if (clientBuild.sha === "unknown" || serverSha === "unknown") {
    return {
      status: "unidentified",
      message: "release identity not injected into this build",
      client: clientBuild,
      server: serverResult.release,
    };
  }

  if (clientBuild.sha === serverSha) {
    return {
      status: "current",
      message: `client matches server release ${serverSha.slice(0, 12)}`,
      client: clientBuild,
      server: serverResult.release,
    };
  }

  return {
    status: "stale",
    message: `client bundle ${clientBuild.sha.slice(0, 12)} differs from server release ${serverSha.slice(0, 12)} — reload to pick up the new release`,
    client: clientBuild,
    server: serverResult.release,
  };
};
