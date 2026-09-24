import { formatDetailValue } from "./detail.js";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export const GPU_PRIMARY_SPECS = [
  { key: "memory_gb", label: "VRAM", unit: "GB" },
  { key: "memory_type", label: "Memory Type", unit: "" },
  { key: "boost_clock_mhz", label: "Boost Clock", unit: "MHz" },
  { key: "tdp_w", label: "TDP", unit: "W" },
];

export const getGpuPrimarySpecRows = (specifications) =>
  GPU_PRIMARY_SPECS.map((spec) => ({
    label: spec.label,
    value: formatDetailValue(
      specifications?.[spec.key],
      spec.unit
    ),
  }));

export const getHardwareCardPrimarySpecs = (type, specifications) => {
  if (
    type !== "GPU" ||
    !specifications ||
    typeof specifications !== "object"
  ) {
    return [];
  }

  return getGpuPrimarySpecRows(specifications);
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