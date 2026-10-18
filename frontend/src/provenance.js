/**
 * Source-transparency view helpers (Batch 015).
 *
 * Pure, defensive functions that turn the read-only provenance API payloads
 * into display models for the hardware detail, benchmark and comparison views.
 * Anything malformed or missing is treated as "no source recorded" rather than
 * being rendered as a claim.
 */

export const PROVENANCE_STATUS_LABELS = {
  verified: "Verified source",
  uncertain: "Uncertain source",
  excluded: "Excluded evidence",
  unmatched: "Unmatched evidence",
  unattributed: "No source recorded",
  unavailable: "Not recorded",
};

export const LICENSE_STATUS_LABELS = {
  clear: "Licence documented",
  unknown: "Licence unknown",
  restricted: "Redistribution restricted",
  unresolved: "Licence unresolved",
};

export const getProvenanceStatusLabel = (status) =>
  PROVENANCE_STATUS_LABELS[status] || "Source status unavailable";

export const getLicenseStatusLabel = (status) =>
  LICENSE_STATUS_LABELS[status] || "Licence status unavailable";

// Display label -> (provenance table, field) for each hardware type. The
// labels mirror the detail view models in `detail.js` and `hardwareCard.js`.
export const SPEC_SOURCE_KEYS = {
  CPU: {
    "Release Date": ["hardware", "release_date"],
    Architecture: ["hardware", "architecture"],
    Cores: ["cpu_specifications", "cores"],
    Threads: ["cpu_specifications", "threads"],
    "Base Clock": ["cpu_specifications", "base_clock_ghz"],
    "Boost Clock": ["cpu_specifications", "boost_clock_ghz"],
    TDP: ["cpu_specifications", "tdp_w"],
    "Process Node": ["cpu_specifications", "process_node_nm"],
    Socket: ["cpu_specifications", "socket"],
  },
  GPU: {
    Architecture: ["hardware", "architecture"],
    "Release Date": ["hardware", "release_date"],
    VRAM: ["gpu_specifications", "memory_gb"],
    "Memory Type": ["gpu_specifications", "memory_type"],
    Bandwidth: ["gpu_specifications", "vram_bandwidth_gbps"],
    "Memory Bus Width": ["gpu_specifications", "memory_bus_width_bits"],
    "Core Clock": ["gpu_specifications", "core_clock_mhz"],
    "Boost Clock": ["gpu_specifications", "boost_clock_mhz"],
    TDP: ["gpu_specifications", "tdp_w"],
    Length: ["gpu_specifications", "length_mm"],
    "Bus Interface": ["gpu_specifications", "interface"],
  },
};

const isRecord = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const asText = (value) => (typeof value === "string" ? value : null);

export const normalizeSource = (source) => {
  if (!isRecord(source)) {
    return null;
  }

  return {
    id: Number.isInteger(source.id) ? source.id : null,
    name: asText(source.name) || "",
    url: asText(source.url) || "",
    publisher: asText(source.publisher),
    licenseName: asText(source.license_name),
    licenseStatus: asText(source.license_status),
    attribution: asText(source.attribution),
    retrievedOn: asText(source.retrieved_on),
  };
};

const normalizeRecord = (record) => {
  if (!isRecord(record)) {
    return null;
  }

  return {
    id: Number.isInteger(record.id) ? record.id : null,
    sourceId: Number.isInteger(record.source_id) ? record.source_id : null,
    sourceName: asText(record.source_name),
    publisher: asText(record.publisher),
    sourceUrl: asText(record.source_url),
    fieldName: asText(record.field_name),
    evidencedValue: asText(record.evidenced_value),
    evidenceStatus: asText(record.evidence_status) || "unavailable",
    confidence: asText(record.confidence),
    accessDate: asText(record.access_date),
    licenseName: asText(record.license_name),
    licenseStatus: asText(record.license_status),
    licenseNotes: asText(record.license_notes),
    attribution: asText(record.attribution),
    batchNo: Number.isInteger(record.batch_no) ? record.batch_no : null,
  };
};

export const getProvenanceFieldMap = (provenance) => {
  const map = {};
  const fields = isRecord(provenance) && Array.isArray(provenance.fields)
    ? provenance.fields
    : [];

  for (const field of fields) {
    if (!isRecord(field) || typeof field.table_name !== "string") {
      continue;
    }

    const records = Array.isArray(field.records)
      ? field.records.map(normalizeRecord).filter(Boolean)
      : [];

    map[`${field.table_name}.${field.field_name}`] = {
      status: asText(field.status) || "unavailable",
      hasValue: Boolean(field.has_value),
      records,
    };
  }

  return map;
};

/**
 * Attach a `source` disclosure model to detail spec rows. Only rows with
 * recorded provenance, or a recorded value but no source, get a disclosure;
 * rows with no value and no provenance are left untouched.
 */
export const buildSpecSourceItems = (items, hardwareType, provenance) => {
  if (!Array.isArray(items)) {
    return [];
  }

  const keyMap = SPEC_SOURCE_KEYS[hardwareType] || {};
  const fieldMap = getProvenanceFieldMap(provenance);

  return items.map((item) => {
    const reference = keyMap[item?.label];
    if (!reference) {
      return item;
    }

    const field = fieldMap[`${reference[0]}.${reference[1]}`];
    if (!field) {
      return item;
    }

    if (field.records.length > 0) {
      return {
        ...item,
        source: { status: field.status, records: field.records },
      };
    }

    if (field.status === "unattributed") {
      return {
        ...item,
        source: { status: "unattributed", records: [] },
      };
    }

    return item;
  });
};

export const getBenchmarkSources = (benchmarkState) => {
  const results = Array.isArray(benchmarkState?.results)
    ? benchmarkState.results
    : [];
  const byKey = new Map();

  for (const result of results) {
    if (!isRecord(result)) {
      continue;
    }

    const source = normalizeSource(result.source);
    const key = `${result.benchmark_name ?? ""}|${result.unit ?? ""}|${
      result.test_type ?? ""
    }|${source?.id ?? "none"}`;

    if (byKey.has(key)) {
      continue;
    }

    byKey.set(key, {
      key,
      benchmarkName: asText(result.benchmark_name) || "Benchmark",
      unit: asText(result.unit) || "",
      testType: asText(result.test_type) || "",
      source,
      recordedAt: asText(result.recorded_at),
    });
  }

  return [...byKey.values()];
};

/**
 * Compact per-hardware source summary for comparison evidence: the distinct
 * spec sources backing recorded fields, and the distinct benchmark sources.
 */
export const summarizeHardwareSources = (provenance) => {
  const fieldMap = getProvenanceFieldMap(provenance);
  const specByKey = new Map();
  let unattributedFields = 0;

  for (const field of Object.values(fieldMap)) {
    if (field.status === "unattributed") {
      unattributedFields += 1;
      continue;
    }

    for (const record of field.records) {
      const key = record.sourceId ?? record.sourceName ?? "unknown";
      if (specByKey.has(key)) {
        continue;
      }
      specByKey.set(key, {
        sourceId: record.sourceId,
        name: record.sourceName,
        publisher: record.publisher,
        sourceUrl: record.sourceUrl,
        licenseStatus: record.licenseStatus,
      });
    }
  }

  const benchmarkByKey = new Map();
  const groups = Array.isArray(provenance?.benchmarks)
    ? provenance.benchmarks
    : [];

  for (const group of groups) {
    if (!isRecord(group)) {
      continue;
    }
    const records = Array.isArray(group.records) ? group.records : [];
    for (const rawRecord of records) {
      const record = normalizeRecord(rawRecord);
      if (!record) {
        continue;
      }
      const key = `${group.benchmark_name ?? ""}|${
        group.test_type ?? ""
      }|${record.sourceId ?? "unknown"}`;
      if (benchmarkByKey.has(key)) {
        continue;
      }
      benchmarkByKey.set(key, {
        benchmarkName: asText(group.benchmark_name) || "Benchmark",
        testType: asText(group.test_type) || "",
        name: record.sourceName,
        publisher: record.publisher,
        sourceUrl: record.sourceUrl,
        licenseStatus: record.licenseStatus,
      });
    }
  }

  return {
    hasProvenance: isRecord(provenance) && Array.isArray(provenance.fields),
    specSources: [...specByKey.values()],
    benchmarkSources: [...benchmarkByKey.values()],
    unattributedFields,
  };
};
