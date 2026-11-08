import { formatDetailValue } from "./detail.js";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/* Catalog-row spec fields, in usefulness order. A row shows the first three
   fields that actually carry a value: boost_clock_mhz is null on 40% of GPUs
   and memory_gb on 18%, so fixed slots repeat N/A; availability-driven
   selection fills rows with real data instead. */
const CATALOG_ROW_SPEC_FIELDS = [
  { key: "memory_gb", label: "VRAM", unit: "GB" },
  { key: "memory_type", label: "Memory", unit: "" },
  { key: "core_clock_mhz", label: "Core Clock", unit: "MHz" },
  { key: "boost_clock_mhz", label: "Boost Clock", unit: "MHz" },
  { key: "tdp_w", label: "TDP", unit: "W" },
];

const GPU_CATALOG_ROW_LIMIT = 3;

export const getGpuCatalogRowSpecs = (specifications) => {
  if (!specifications || typeof specifications !== "object") {
    return [];
  }

  return CATALOG_ROW_SPEC_FIELDS.map((spec) => ({
    spec,
    value: formatDetailValue(specifications[spec.key], spec.unit),
  }))
    .filter((row) => row.value !== "N/A")
    .slice(0, GPU_CATALOG_ROW_LIMIT)
    .map((row) => ({ label: row.spec.label, value: row.value }));
};

/* A catalog row's secondary line. GPUs draw from their detail specifications;
   CPUs carry catalog-identity fields from the list payload — architecture and
   release date when the record has them, nothing fabricated when it doesn't. */
export const getCatalogRowSpecs = (type, specifications, catalogIdentity) => {
  if (type === "GPU") {
    return getGpuCatalogRowSpecs(specifications);
  }

  if (type !== "CPU" || !catalogIdentity) {
    return [];
  }

  const rows = [];
  if (catalogIdentity.architecture) {
    rows.push({ label: "Architecture", value: String(catalogIdentity.architecture) });
  }
  if (catalogIdentity.release_date) {
    rows.push({ label: "Released", value: formatReleaseDate(catalogIdentity.release_date) });
  }
  return rows;
};

export const formatReleaseDate = (value) => {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  if (typeof value !== "string") {
    return String(value);
  }

  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);

  if (!match) {
    return value;
  }

  const [, year, month, day] = match;
  const monthName = MONTH_NAMES[Number(month) - 1];

  if (!monthName) {
    return value;
  }

  return `${monthName} ${Number(day)}, ${year}`;
};

export const getGpuDetailViewModel = (hardware) => {
  const specifications = hardware?.specifications || {};
  const type = hardware?.type || "N/A";

  return {
    name: hardware?.name || "N/A",
    manufacturer: hardware?.manufacturer || "N/A",
    type,
    overview: [
      {
        label: "Architecture",
        value: formatDetailValue(hardware?.architecture),
      },
      {
        label: "Release Date",
        value: formatReleaseDate(hardware?.release_date),
      },
    ],
    memory: [
      {
        label: "VRAM",
        value: formatDetailValue(specifications.memory_gb, "GB"),
      },
      {
        label: "Memory Type",
        value: formatDetailValue(specifications.memory_type),
      },
      {
        label: "Bandwidth",
        value: formatDetailValue(
          specifications.vram_bandwidth_gbps,
          "GB/s"
        ),
      },
      {
        label: "Memory Bus Width",
        value: formatDetailValue(
          specifications.memory_bus_width_bits,
          "bits"
        ),
      },
    ],
    clocks: [
      {
        label: "Core Clock",
        value: formatDetailValue(specifications.core_clock_mhz, "MHz"),
      },
      {
        label: "Boost Clock",
        value: formatDetailValue(specifications.boost_clock_mhz, "MHz"),
      },
    ],
    powerPhysical: [
      {
        label: "TDP",
        value: formatDetailValue(specifications.tdp_w, "W"),
      },
      {
        label: "Length",
        value: formatDetailValue(specifications.length_mm, "mm"),
      },
    ],
    interface: [
      {
        label: "Bus Interface",
        value: formatDetailValue(specifications.interface),
      },
    ],
  };
};