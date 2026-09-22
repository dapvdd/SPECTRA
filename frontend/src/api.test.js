import test from "node:test";
import assert from "node:assert/strict";

import { API_BASE_URL, apiUrl, getApiBaseUrl } from "./api.js";

test("API base URL defaults to the local backend", () => {
  assert.equal(getApiBaseUrl(undefined), "http://127.0.0.1:8000");
  assert.equal(API_BASE_URL, "http://127.0.0.1:8000");
});

test("configured Vite API base URL is used", () => {
  assert.equal(getApiBaseUrl("https://api.example.test"), "https://api.example.test");
});

test("configured API base URL trailing slashes are normalized", () => {
  assert.equal(apiUrl("/hardware/1"), "http://127.0.0.1:8000/hardware/1");
  assert.equal(getApiBaseUrl("https://api.example.test///"), "https://api.example.test");
});

test("API endpoint paths remain unchanged", () => {
  assert.equal(apiUrl("/"), "http://127.0.0.1:8000/");
  assert.equal(apiUrl("/hardware"), "http://127.0.0.1:8000/hardware");
  assert.equal(
    apiUrl("/hardware/7/benchmarks"),
    "http://127.0.0.1:8000/hardware/7/benchmarks"
  );
  assert.equal(
    apiUrl("/comparison/explanation"),
    "http://127.0.0.1:8000/comparison/explanation"
  );
});
