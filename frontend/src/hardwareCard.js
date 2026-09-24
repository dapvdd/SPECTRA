import { formatDetailValue } from "./detail.js";

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

export const getGpuDetailViewModel = (hardware) => {
  const specifications = hardware?.specifications || {};
  const type = hardware?.type || "N/A";

  return {
    name: hardware?.name || "N/A",
    manufacturer: hardware?.manufacturer || "N/A",
    type,
    overview: [
      {
        label: "Manufacturer",
        value: formatDetailValue(hardware?.manufacturer),
      },
      { label: "Type", value: formatDetailValue(type) },
      {
        label: "Release Date",
        value: formatDetailValue(hardware?.release_date),
      },
      {
        label: "Architecture",
        value: formatDetailValue(hardware?.architecture),
      },
    ],
    keySpecifications: getGpuPrimarySpecRows(specifications),
  };
};