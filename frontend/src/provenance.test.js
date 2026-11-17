import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSpecSourceItems,
  getBenchmarkSources,
  getHardwareSourceMeta,
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

// ---- M3 Phase 7: Build Planner category transparency ---------------------

const m3Record = (overrides = {}) =>
  record({
    id: 9,
    source_id: 6,
    source_name: "Wikipedia (English) — curated",
    source_url: "https://en.wikipedia.org/wiki/DDR5_SDRAM",
    field_name: "speed_mhz",
    evidenced_value: "6000",
    license_name: "CC BY-SA 4.0",
    license_status: "clear",
    access_date: "2026-11-16",
    ...overrides,
  });

const psuProvenance = {
  hardware_id: 14,
  hardware_name: "RM750x",
  hardware_type: "PSU",
  fields: [
    {
      table_name: "hardware",
      field_name: "release_date",
      has_value: true,
      status: "unattributed",
      records: [],
    },
    {
      table_name: "psu_specifications",
      field_name: "wattage",
      has_value: true,
      status: "verified",
      records: [
        m3Record({
          field_name: "wattage",
          evidenced_value: "850",
          source_url: "https://seasonic.com/focus-gx/",
        }),
      ],
    },
    {
      table_name: "psu_specifications",
      field_name: "efficiency_rating",
      has_value: true,
      status: "unattributed",
      records: [],
    },
    {
      table_name: "psu_specifications",
      field_name: "modular",
      has_value: false,
      status: "unavailable",
      records: [],
    },
  ],
  benchmarks: [],
  summary: {},
};

test("RAM detail labels resolve to their ram_specifications provenance fields", () => {
  const items = [
    { label: "Capacity", value: "32 GB" },
    { label: "DDR Generation", value: "DDR5" },
    { label: "Speed", value: "6000 MHz" },
    { label: "Modules", value: "2" },
    { label: "ECC", value: "No" },
    { label: "Voltage", value: "1.35 V" },
    { label: "Form Factor", value: "UDIMM" },
    { label: "Release Date", value: "2024-05-01" },
    { label: "Manufacturer", value: "Test" },
  ];

  const result = buildSpecSourceItems(items, "RAM", {
    fields: [
      {
        table_name: "ram_specifications",
        field_name: "speed_mhz",
        has_value: true,
        status: "verified",
        records: [m3Record()],
      },
    ],
  });

  assert.equal(result[2].source.status, "verified");
  assert.equal(result[2].source.records[0].fieldName, "speed_mhz");
  // Labels without provenance rows stay untouched, mapped or not.
  assert.equal(result[0].source, undefined);
  assert.equal(result[8].source, undefined);
});

test("Storage detail labels resolve to their storage_specifications fields", () => {
  const items = [
    { label: "Capacity", value: "1024 GB" },
    { label: "Storage Type", value: "NVMe" },
    { label: "Interface", value: "PCIe 4.0 x4" },
    { label: "Form Factor", value: "M.2 2280" },
    { label: "Sequential Read", value: "7000 MB/s" },
    { label: "Sequential Write", value: "5000 MB/s" },
    { label: "DRAM Cache", value: "Yes" },
  ];

  const result = buildSpecSourceItems(items, "STORAGE", {
    fields: [
      {
        table_name: "storage_specifications",
        field_name: "read_mb_s",
        has_value: true,
        status: "verified",
        records: [
          m3Record({
            field_name: "read_mb_s",
            evidenced_value: "7000.0",
          }),
        ],
      },
    ],
  });

  assert.equal(result[4].source.status, "verified");
  assert.equal(result[4].source.records[0].fieldName, "read_mb_s");
  assert.equal(result[1].source, undefined);
});

test("Motherboard detail labels resolve to their motherboard_specifications fields", () => {
  const items = [
    { label: "Socket", value: "AM5" },
    { label: "Chipset", value: "B650" },
    { label: "Form Factor", value: "ATX" },
    { label: "Memory Type", value: "DDR5" },
    { label: "Memory Slots", value: "4" },
    { label: "Max Memory", value: "192 GB" },
    { label: "M.2 Slots", value: "3" },
    { label: "SATA Ports", value: "4" },
    { label: "PCIe Slots", value: "5" },
  ];

  const result = buildSpecSourceItems(items, "MOTHERBOARD", {
    fields: [
      {
        table_name: "motherboard_specifications",
        field_name: "ram_slots",
        has_value: true,
        status: "verified",
        records: [
          m3Record({
            field_name: "ram_slots",
            evidenced_value: "4",
            source_url: "https://www.msi.com/Motherboard/MAG-B650-TOMAHAWK-WIFI",
          }),
        ],
      },
    ],
  });

  assert.equal(result[4].source.status, "verified");
  assert.equal(result[4].source.records[0].fieldName, "ram_slots");
  assert.equal(result[6].source, undefined);
});

test("PSU detail labels resolve to their psu_specifications fields", () => {
  const items = [
    { label: "Release Date", value: "2024-03-01" },
    { label: "Rated Wattage", value: "850 W" },
    { label: "Efficiency Rating", value: "80 Plus Gold" },
    { label: "Modular", value: "Yes" },
    { label: "PCIe 8-pin Connectors", value: "4" },
    { label: "12VHPWR Connectors", value: "1" },
  ];

  const result = buildSpecSourceItems(items, "PSU", psuProvenance);

  assert.equal(result[1].source.status, "verified");
  assert.equal(result[1].source.records[0].fieldName, "wattage");
  // Unattributed populated values surface the honest empty disclosure.
  assert.deepEqual(result[0].source, { status: "unattributed", records: [] });
  assert.deepEqual(result[2].source, { status: "unattributed", records: [] });
  // Unavailable fields stay untouched.
  assert.equal(result[3].source, undefined);
});

test("getHardwareSourceMeta reports completeness, last-verified date and attribution", () => {
  const meta = getHardwareSourceMeta(psuProvenance);

  assert.equal(meta.hasProvenance, true);
  assert.equal(meta.totalFields, 4);
  assert.equal(meta.verifiedFields, 1);
  assert.equal(meta.unattributedFields, 2);
  assert.equal(meta.lastVerifiedOn, "2026-11-16");
  assert.equal(
    meta.attribution,
    "Specs verified against sources including Wikipedia (CC BY-SA 4.0).",
  );

  const unknown = getHardwareSourceMeta(null);
  assert.equal(unknown.hasProvenance, false);
  assert.equal(unknown.totalFields, 0);
  assert.equal(unknown.verifiedFields, 0);
  assert.equal(unknown.unattributedFields, 0);
  assert.equal(unknown.lastVerifiedOn, null);
  assert.equal(unknown.attribution, null);
});

test("getHardwareSourceMeta ignores malformed access dates and junk fields", () => {
  const meta = getHardwareSourceMeta({
    fields: [
      { nope: true },
      {
        table_name: "psu_specifications",
        field_name: "wattage",
        has_value: true,
        status: "verified",
        records: [
          m3Record({ id: 11, access_date: "not-a-date" }),
          m3Record({ id: 12, access_date: "2026-11-15" }),
        ],
      },
    ],
  });

  assert.equal(meta.totalFields, 1);
  assert.equal(meta.verifiedFields, 1);
  // The malformed date is skipped; the valid one is reported.
  assert.equal(meta.lastVerifiedOn, "2026-11-15");

  const allMalformed = getHardwareSourceMeta({
    fields: [
      {
        table_name: "psu_specifications",
        field_name: "wattage",
        has_value: true,
        status: "verified",
        records: [m3Record({ access_date: "not-a-date" })],
      },
    ],
  });
  assert.equal(allMalformed.lastVerifiedOn, null);
});
