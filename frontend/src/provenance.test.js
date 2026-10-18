import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSpecSourceItems,
  getBenchmarkSources,
  getLicenseStatusLabel,
  getProvenanceFieldMap,
  getProvenanceStatusLabel,
  normalizeSource,
  summarizeHardwareSources,
} from "./provenance.js";

const record = (overrides = {}) => ({
  id: 1,
  source_id: 5,
  source_name: "Wikipedia (English)",
  publisher: "Wikipedia contributors",
  source_url: "https://en.wikipedia.org/wiki/Example",
  field_name: "cores",
  evidenced_value: "8",
  evidence_status: "verified",
  license_name: "CC BY-SA 4.0",
  license_status: "clear",
  attribution: "Wikipedia, The Free Encyclopedia (CC BY-SA 4.0).",
  access_date: "2026-10-10",
  ...overrides,
});

const provenance = {
  hardware_id: 1,
  hardware_name: "Test CPU",
  hardware_type: "CPU",
  fields: [
    {
      table_name: "cpu_specifications",
      field_name: "cores",
      has_value: true,
      status: "verified",
      records: [record()],
    },
    {
      table_name: "cpu_specifications",
      field_name: "threads",
      has_value: true,
      status: "unattributed",
      records: [],
    },
    {
      table_name: "cpu_specifications",
      field_name: "socket",
      has_value: false,
      status: "unavailable",
      records: [],
    },
  ],
  benchmarks: [
    {
      benchmark_result_id: 7,
      benchmark_name: "Geekbench 7",
      unit: "points",
      test_type: "single-core",
      score: 1234.5,
      records: [
        record({
          id: 2,
          source_id: 2,
          source_name: "Geekbench Browser",
          field_name: "score",
          evidenced_value: "1234.5",
          license_status: "unknown",
        }),
      ],
    },
  ],
  summary: {},
};

test("status labels have honest fallbacks", () => {
  assert.equal(getProvenanceStatusLabel("verified"), "Verified source");
  assert.equal(getProvenanceStatusLabel("unattributed"), "No source recorded");
  assert.equal(getProvenanceStatusLabel("mystery"), "Source status unavailable");
  assert.equal(getLicenseStatusLabel("clear"), "Licence documented");
  assert.equal(getLicenseStatusLabel("restricted"), "Redistribution restricted");
  assert.equal(getLicenseStatusLabel(undefined), "Licence status unavailable");
});

test("normalizeSource maps snake_case and rejects invalid input", () => {
  assert.equal(normalizeSource(null), null);
  assert.equal(normalizeSource("nope"), null);
  assert.deepEqual(normalizeSource({ id: 5, name: "Wikipedia", url: "https://x" }), {
    id: 5,
    name: "Wikipedia",
    url: "https://x",
    publisher: null,
    licenseName: null,
    licenseStatus: null,
    attribution: null,
    retrievedOn: null,
  });
});

test("getProvenanceFieldMap keys by table and field and ignores junk", () => {
  const map = getProvenanceFieldMap({
    fields: [
      { table_name: "cpu_specifications", field_name: "cores", status: "verified", has_value: true, records: [record()] },
      { nope: true },
      null,
    ],
  });

  assert.deepEqual(Object.keys(map), ["cpu_specifications.cores"]);
  assert.equal(map["cpu_specifications.cores"].status, "verified");
  assert.equal(map["cpu_specifications.cores"].records.length, 1);
});

test("buildSpecSourceItems attaches disclosures only where meaningful", () => {
  const items = [
    { label: "Cores", value: "8" },
    { label: "Threads", value: "16" },
    { label: "Socket", value: "N/A" },
    { label: "Manufacturer", value: "Test" },
  ];

  const result = buildSpecSourceItems(items, "CPU", provenance);

  assert.equal(result[0].source.status, "verified");
  assert.equal(result[0].source.records[0].sourceName, "Wikipedia (English)");
  assert.deepEqual(result[1].source, { status: "unattributed", records: [] });
  assert.equal(result[2].source, undefined);
  assert.equal(result[3].source, undefined);
});

test("buildSpecSourceItems tolerates missing provenance and bad input", () => {
  const items = [{ label: "Cores", value: "8" }];
  assert.deepEqual(buildSpecSourceItems(items, "CPU", null), items);
  assert.deepEqual(buildSpecSourceItems(null, "CPU", provenance), []);
});

test("GPU memory bus width resolves to its recorded provenance field", () => {
  const items = [
    { label: "Memory Bus Width", value: "192 bits" },
    { label: "VRAM", value: "12 GB" },
  ];

  const result = buildSpecSourceItems(items, "GPU", {
    fields: [
      {
        table_name: "gpu_specifications",
        field_name: "memory_bus_width_bits",
        has_value: true,
        status: "verified",
        records: [
          record({
            field_name: "memory_bus_width_bits",
            evidenced_value: "192",
          }),
        ],
      },
    ],
  });

  assert.equal(result[0].source.status, "verified");
  assert.equal(result[0].source.records[0].sourceName, "Wikipedia (English)");
  assert.equal(result[1].source, undefined);
});

test("getBenchmarkSources dedupes and exposes attribution", () => {
  const sources = getBenchmarkSources({
    results: [
      {
        benchmark_name: "Geekbench 7",
        unit: "points",
        test_type: "single-core",
        recorded_at: "2026-01-02T03:04:05",
        source: { id: 2, name: "Geekbench Browser", url: "https://geekbench.test" },
      },
      {
        benchmark_name: "Geekbench 7",
        unit: "points",
        test_type: "single-core",
        source: { id: 2, name: "Geekbench Browser", url: "https://geekbench.test" },
      },
    ],
  });

  assert.equal(sources.length, 1);
  assert.equal(sources[0].benchmarkName, "Geekbench 7");
  assert.equal(sources[0].source.name, "Geekbench Browser");
});

test("summarizeHardwareSources collects distinct spec and benchmark sources", () => {
  const summary = summarizeHardwareSources(provenance);

  assert.equal(summary.hasProvenance, true);
  assert.equal(summary.specSources.length, 1);
  assert.equal(summary.specSources[0].name, "Wikipedia (English)");
  assert.equal(summary.specSources[0].licenseStatus, "clear");
  assert.equal(summary.benchmarkSources.length, 1);
  assert.equal(summary.benchmarkSources[0].benchmarkName, "Geekbench 7");
  assert.equal(summary.unattributedFields, 1);

  const empty = summarizeHardwareSources(null);
  assert.equal(empty.hasProvenance, false);
  assert.deepEqual(empty.specSources, []);
});
