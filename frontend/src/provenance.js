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
  MOTHERBOARD: {
    Socket: ["motherboard_specifications", "socket"],
    Chipset: ["motherboard_specifications", "chipset"],
    "Form Factor": ["motherboard_specifications", "form_factor"],
    "Memory Type": ["motherboard_specifications", "ram_type"],
    "Memory Slots": ["motherboard_specifications", "ram_slots"],
    "Max Memory": ["motherboard_specifications", "max_ram_gb"],
    "M.2 Slots": ["motherboard_specifications", "m2_slots"],
    "SATA Ports": ["motherboard_specifications", "sata_ports"],
    "PCIe Slots": ["motherboard_specifications", "pcie_slots"],
  },
  RAM: {
    "Release Date": ["hardware", "release_date"],
    Architecture: ["hardware", "architecture"],
    Capacity: ["ram_specifications", "capacity_gb"],
    "DDR Generation": ["ram_specifications", "ddr_generation"],
    Speed: ["ram_specifications", "speed_mhz"],
    Modules: ["ram_specifications", "modules"],
    ECC: ["ram_specifications", "ecc"],
    Voltage: ["ram_specifications", "voltage_v"],
    "Form Factor": ["ram_specifications", "form_factor"],
  },
  STORAGE: {
    "Release Date": ["hardware", "release_date"],
    Architecture: ["hardware", "architecture"],
    Capacity: ["storage_specifications", "capacity_gb"],
    "Storage Type": ["storage_specifications", "storage_type"],
    Interface: ["storage_specifications", "interface"],
    "Form Factor": ["storage_specifications", "form_factor"],
    "Sequential Read": ["storage_specifications", "read_mb_s"],
    "Sequential Write": ["storage_specifications", "write_mb_s"],
    "DRAM Cache": ["storage_specifications", "dram_cache"],
  },
  PSU: {
    "Release Date": ["hardware", "release_date"],
    Architecture: ["hardware", "architecture"],
    "Rated Wattage": ["psu_specifications", "wattage"],
    Wattage: ["psu_specifications", "wattage"],
    "Efficiency Rating": ["psu_specifications", "efficiency_rating"],
    Modular: ["psu_specifications", "modular"],
    "PCIe 8-pin Connectors": ["psu_specifications", "pcie_8pin_count"],
    "12VHPWR Connectors": ["psu_specifications", "pcie_12vhpwr"],
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

/**
 * Transparency meta for a category detail view (M3): how much of the shown
 * specification carries recorded provenance, the most recent human access
 * date across verified records, and the standing attribution notice. Missing
 * or malformed input degrades honestly to nulls — nothing is invented.
 */
export const getHardwareSourceMeta = (provenance) => {
  if (!isRecord(provenance) || !Array.isArray(provenance.fields)) {
    return {
      hasProvenance: false,
      totalFields: 0,
      verifiedFields: 0,
      unattributedFields: 0,
      lastVerifiedOn: null,
      attribution: null,
    };
  }

  let totalFields = 0;
  let verifiedFields = 0;
  let unattributedFields = 0;
  let lastVerifiedOn = null;

  for (const field of provenance.fields) {
    if (!isRecord(field) || typeof field.table_name !== "string") {
      continue;
    }
    totalFields += 1;
    if (field.status === "verified") {
      verifiedFields += 1;
    } else if (field.status === "unattributed") {
      unattributedFields += 1;
    }

    const records = Array.isArray(field.records) ? field.records : [];
    for (const rawRecord of records) {
      const record = normalizeRecord(rawRecord);
      const accessDate = record?.accessDate;
      if (
        typeof accessDate === "string" &&
        /^\d{4}-\d{2}-\d{2}$/.test(accessDate)
      ) {
        if (lastVerifiedOn === null || accessDate > lastVerifiedOn) {
          lastVerifiedOn = accessDate;
        }
      }
    }
  }

  return {
    hasProvenance: true,
    totalFields,
    verifiedFields,
    unattributedFields,
    lastVerifiedOn,
    attribution:
      "Specs verified against sources including Wikipedia (CC BY-SA 4.0).",
  };
};
