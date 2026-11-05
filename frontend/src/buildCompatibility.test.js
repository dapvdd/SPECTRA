import test from "node:test";
import assert from "node:assert/strict";

import {
  buildCompatibilityReport,
  buildPowerSuggestion,
  SOCKET_CHIPSET_LINEAGE,
  normalizeSocket,
  getCpuSocket,
} from "./buildCompatibility.js";

const cpuDetail = (overrides = {}) => ({
  id: 1,
  name: "AMD Ryzen 7 7800X3D",
  manufacturer: "AMD",
  type: "CPU",
  segment: null,
  specifications: {
    cores: 8,
    threads: 16,
    base_clock_ghz: 3.5,
    boost_clock_ghz: 5.0,
    tdp_w: 120,
    process_node_nm: 5,
    socket: "AM5",
  },
  ...overrides,
});

const gpuDetail = (overrides = {}) => ({
  id: 2,
  name: "NVIDIA GeForce RTX 5070 Ti",
  manufacturer: "NVIDIA",
  type: "GPU",
  segment: null,
  specifications: {
    memory_gb: 16,
    memory_type: "GDDR7",
    core_clock_mhz: 2450,
    boost_clock_mhz: 2750,
    vram_bandwidth_gbps: 896,
    memory_bus_width_bits: 256,
    tdp_w: 300,
    interface: "PCIe 5.0 x16",
    length_mm: 304,
  },
  ...overrides,
});

/* ---- buildCompatibilityReport ---- */

test("incomplete when cpu missing", () => {
  const report = buildCompatibilityReport(null, gpuDetail());
  assert.strictEqual(report.status, "incomplete");
  assert.deepStrictEqual(report.checks, []);
  assert.ok(report.assumptions.length > 0);
});

test("incomplete when gpu missing", () => {
  const report = buildCompatibilityReport(cpuDetail(), null);
  assert.strictEqual(report.status, "incomplete");
});

test("incomplete when both missing", () => {
  const report = buildCompatibilityReport(null, null);
  assert.strictEqual(report.status, "incomplete");
});

test("ready when cpu and gpu present", () => {
  const report = buildCompatibilityReport(cpuDetail(), gpuDetail());
  assert.strictEqual(report.status, "ready");
  assert.ok(report.checks.length >= 4);
});

test("cpu-socket check passes for AM5", () => {
  const report = buildCompatibilityReport(cpuDetail(), gpuDetail());
  const check = report.checks.find((c) => c.id === "cpu-socket");
  assert.ok(check);
  assert.strictEqual(check.state, "pass");
  assert.ok(check.message.includes("AM5"));
});

test("cpu-socket check warns for unrecognised socket", () => {
  const report = buildCompatibilityReport(
    cpuDetail({ specifications: { socket: "AM99" } }),
    gpuDetail()
  );
  const check = report.checks.find((c) => c.id === "cpu-socket");
  assert.strictEqual(check.state, "warn");
});

test("cpu-socket check unknown when no socket", () => {
  const report = buildCompatibilityReport(
    cpuDetail({ specifications: { socket: null } }),
    gpuDetail()
  );
  const check = report.checks.find((c) => c.id === "cpu-socket");
  assert.strictEqual(check.state, "unknown");
});

test("cpu-socket handles whitespace-padded values", () => {
  const normal = normalizeSocket("AM5");
  const padded = normalizeSocket("  AM5  ");
  assert.strictEqual(normal, "AM5");
  assert.strictEqual(padded, "AM5");
});

test("gpu-interface check passes when interface present", () => {
  const report = buildCompatibilityReport(cpuDetail(), gpuDetail());
  const check = report.checks.find((c) => c.id === "gpu-interface");
  assert.strictEqual(check.state, "pass");
  assert.ok(check.message.includes("PCIe 5.0 x16"));
});

test("gpu-interface check unknown when no interface", () => {
  const report = buildCompatibilityReport(
    cpuDetail(),
    gpuDetail({ specifications: { interface: null } })
  );
  const check = report.checks.find((c) => c.id === "gpu-interface");
  assert.strictEqual(check.state, "unknown");
});

test("gpu-clearance check passes with length", () => {
  const report = buildCompatibilityReport(cpuDetail(), gpuDetail());
  const check = report.checks.find((c) => c.id === "gpu-clearance");
  assert.strictEqual(check.state, "info");
  assert.ok(check.message.includes("304 mm"));
});

test("gpu-clearance uses estimated length when actual is missing", () => {
  const report = buildCompatibilityReport(
    cpuDetail(),
    gpuDetail({
      specifications: {
        interface: "PCIe 5.0 x16",
        length_mm: null,
      },
    })
  );
  const check = report.checks.find((c) => c.id === "gpu-clearance");
  assert.strictEqual(check.state, "info");
  assert.ok(check.message.includes("estimate"));
});

test("gpu-clearance unknown when no length or interface", () => {
  const report = buildCompatibilityReport(
    cpuDetail(),
    gpuDetail({
      specifications: {
        interface: null,
        length_mm: null,
      },
    })
  );
  const check = report.checks.find((c) => c.id === "gpu-clearance");
  assert.strictEqual(check.state, "unknown");
});

test("psu-suggestion check is included", () => {
  const report = buildCompatibilityReport(cpuDetail(), gpuDetail());
  const check = report.checks.find((c) => c.id === "psu-suggestion");
  assert.ok(check);
  assert.strictEqual(check.state, "info");
});

test("psu-suggestion check unknown when TDP missing", () => {
  const report = buildCompatibilityReport(
    cpuDetail({ specifications: { tdp_w: null } }),
    gpuDetail()
  );
  const check = report.checks.find((c) => c.id === "psu-suggestion");
  assert.strictEqual(check.state, "unknown");
});

test("assumptions are never empty when status is ready", () => {
  const report = buildCompatibilityReport(cpuDetail(), gpuDetail());
  assert.ok(report.assumptions.length > 0, "assumptions must be non-empty");
  assert.ok(
    report.assumptions.some((a) => a.includes("PSU")),
    "PSU assumption must be present"
  );
});

/* ---- buildPowerSuggestion ---- */

test("power suggestion derives from listed TDP sum with 1.25x margin", () => {
  const suggestion = buildPowerSuggestion(cpuDetail(), gpuDetail());
  assert.ok(suggestion);
  assert.strictEqual(suggestion.base_tdp_sum, 420);
  assert.strictEqual(suggestion.margin_multiplier, 1.25);
  // 420 * 1.25 = 525 → rounded to nearest 50 = 550 W
  assert.strictEqual(suggestion.watts, 550);
  assert.ok(suggestion.label.includes("550 W"));
  assert.strictEqual(suggestion.isSuggestion, true);
});

test("power suggestion is null when cpu tdp missing", () => {
  assert.strictEqual(
    buildPowerSuggestion(
      cpuDetail({ specifications: { tdp_w: null } }),
      gpuDetail()
    ),
    null
  );
});

test("power suggestion is null when gpu tdp missing", () => {
  assert.strictEqual(
    buildPowerSuggestion(
      cpuDetail(),
      gpuDetail({ specifications: { tdp_w: null } })
    ),
    null
  );
});

test("power suggestion rounds up to nearest 50 W", () => {
  const suggestion = buildPowerSuggestion(
    cpuDetail({ specifications: { tdp_w: 65 } }),
    gpuDetail({ specifications: { tdp_w: 50 } })
  );
  // 115 * 1.25 = 143.75 → ceil / 50 = 3 → 150 W
  assert.strictEqual(suggestion.watts, 150);
});

/* ---- socket normalisation helpers ---- */

test("SOCKET_CHIPSET_LINEAGE covers known modern sockets", () => {
  assert.ok(SOCKET_CHIPSET_LINEAGE["AM5"]);
  assert.ok(SOCKET_CHIPSET_LINEAGE["LGA1700"]);
  assert.ok(SOCKET_CHIPSET_LINEAGE["AM4"]);
});

test("normalizeSocket returns canonical form or null", () => {
  assert.strictEqual(normalizeSocket("AM5"), "AM5");
  assert.strictEqual(normalizeSocket("  AM5  "), "AM5");
  assert.strictEqual(normalizeSocket("LGA 1700"), "LGA1700");
  assert.strictEqual(normalizeSocket("LGA1700"), "LGA1700");
  assert.strictEqual(normalizeSocket("garbage"), null);
  assert.strictEqual(normalizeSocket(null), null);
  assert.strictEqual(normalizeSocket(""), null);
});

test("getCpuSocket extracts socket from spec", () => {
  assert.strictEqual(getCpuSocket(cpuDetail()), "AM5");
  assert.strictEqual(getCpuSocket(cpuDetail({ specifications: { socket: null } })), null);
  assert.strictEqual(getCpuSocket({}), null);
  assert.strictEqual(getCpuSocket(null), null);
});
