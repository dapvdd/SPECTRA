export const formatDetailValue = (value, unit = "") => {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  return unit ? `${value} ${unit}` : String(value);
};

export const getCpuDetailViewModel = (hardware) => {
  const specifications = hardware?.specifications || {};

  return {
    name: hardware?.name || "N/A",
    manufacturer: hardware?.manufacturer || "N/A",
    type: hardware?.type || "N/A",
    overview: [
      { label: "Manufacturer", value: formatDetailValue(hardware?.manufacturer) },
      { label: "Type", value: formatDetailValue(hardware?.type) },
      { label: "Release Date", value: formatDetailValue(hardware?.release_date) },
      { label: "Architecture", value: formatDetailValue(hardware?.architecture) },
    ],
    keySpecifications: [
      { label: "Cores", value: formatDetailValue(specifications.cores) },
      { label: "Threads", value: formatDetailValue(specifications.threads) },
      {
        label: "Base Clock",
        value: formatDetailValue(specifications.base_clock_ghz, "GHz"),
      },
      {
        label: "Boost Clock",
        value: formatDetailValue(specifications.boost_clock_ghz, "GHz"),
      },
      { label: "TDP", value: formatDetailValue(specifications.tdp_w, "W") },
    ],
    technicalSpecifications: [
      {
        label: "Process Node",
        value: formatDetailValue(specifications.process_node_nm, "nm"),
      },
      { label: "Socket", value: formatDetailValue(specifications.socket) },
    ],
  };
};

export const getDetailBackLabel = (type) => {
  const noun = type === "CPU" ? "CPUs" : type === "GPU" ? "GPUs" : "hardware";

  return `Back to ${noun}`;
};

// ---- Category-aware detail view models (M2 Task 4) ----------------------
// Each Build Planner category renders only the specifications its schema
// records. Missing values fall through to "N/A"; nothing is invented.

export const getRamDetailViewModel = (hardware) => {
  const specifications = hardware?.specifications || {};

  return {
    name: hardware?.name || "N/A",
    manufacturer: hardware?.manufacturer || "N/A",
    type: hardware?.type || "N/A",
    overview: [
      { label: "Manufacturer", value: formatDetailValue(hardware?.manufacturer) },
      { label: "Type", value: formatDetailValue(hardware?.type) },
      { label: "Release Date", value: formatDetailValue(hardware?.release_date) },
    ],
    keySpecifications: [
      { label: "Capacity", value: formatDetailValue(specifications.capacity_gb, "GB") },
      { label: "DDR Generation", value: formatDetailValue(specifications.ddr_generation) },
      { label: "Speed", value: formatDetailValue(specifications.speed_mhz, "MHz") },
      { label: "Modules", value: formatDetailValue(specifications.modules) },
    ],
    technicalSpecifications: [
      { label: "ECC", value: formatDetailValue(specifications.ecc) },
      { label: "Voltage", value: formatDetailValue(specifications.voltage_v, "V") },
      { label: "Form Factor", value: formatDetailValue(specifications.form_factor) },
    ],
  };
};

export const getStorageDetailViewModel = (hardware) => {
  const specifications = hardware?.specifications || {};

  return {
    name: hardware?.name || "N/A",
    manufacturer: hardware?.manufacturer || "N/A",
    type: hardware?.type || "N/A",
    overview: [
      { label: "Manufacturer", value: formatDetailValue(hardware?.manufacturer) },
      { label: "Type", value: formatDetailValue(hardware?.type) },
      { label: "Release Date", value: formatDetailValue(hardware?.release_date) },
    ],
    keySpecifications: [
      { label: "Capacity", value: formatDetailValue(specifications.capacity_gb, "GB") },
      { label: "Storage Type", value: formatDetailValue(specifications.storage_type) },
      { label: "Interface", value: formatDetailValue(specifications.interface) },
      { label: "Form Factor", value: formatDetailValue(specifications.form_factor) },
    ],
    technicalSpecifications: [
      { label: "Sequential Read", value: formatDetailValue(specifications.read_mb_s, "MB/s") },
      { label: "Sequential Write", value: formatDetailValue(specifications.write_mb_s, "MB/s") },
      { label: "DRAM Cache", value: formatDetailValue(specifications.dram_cache) },
    ],
  };
};

export const getMotherboardDetailViewModel = (hardware) => {
  const specifications = hardware?.specifications || {};

  return {
    name: hardware?.name || "N/A",
    manufacturer: hardware?.manufacturer || "N/A",
    type: hardware?.type || "N/A",
    overview: [
      { label: "Manufacturer", value: formatDetailValue(hardware?.manufacturer) },
      { label: "Type", value: formatDetailValue(hardware?.type) },
      { label: "Release Date", value: formatDetailValue(hardware?.release_date) },
    ],
    keySpecifications: [
      { label: "Socket", value: formatDetailValue(specifications.socket) },
      { label: "Chipset", value: formatDetailValue(specifications.chipset) },
      { label: "Form Factor", value: formatDetailValue(specifications.form_factor) },
      { label: "Memory Type", value: formatDetailValue(specifications.ram_type) },
    ],
    technicalSpecifications: [
      { label: "Memory Slots", value: formatDetailValue(specifications.ram_slots) },
      { label: "Max Memory", value: formatDetailValue(specifications.max_ram_gb, "GB") },
      { label: "M.2 Slots", value: formatDetailValue(specifications.m2_slots) },
      { label: "SATA Ports", value: formatDetailValue(specifications.sata_ports) },
      { label: "PCIe Slots", value: formatDetailValue(specifications.pcie_slots) },
    ],
  };
};

export const getPsuDetailViewModel = (hardware) => {
  const specifications = hardware?.specifications || {};
  const modularLabel =
    specifications.modular === null || specifications.modular === undefined
      ? "N/A"
      : specifications.modular
        ? "Yes"
        : "No";

  return {
    name: hardware?.name || "N/A",
    manufacturer: hardware?.manufacturer || "N/A",
    type: hardware?.type || "N/A",
    overview: [
      { label: "Manufacturer", value: formatDetailValue(hardware?.manufacturer) },
      { label: "Type", value: formatDetailValue(hardware?.type) },
      { label: "Release Date", value: formatDetailValue(hardware?.release_date) },
    ],
    keySpecifications: [
      { label: "Rated Wattage", value: formatDetailValue(specifications.wattage, "W") },
      { label: "Efficiency Rating", value: formatDetailValue(specifications.efficiency_rating) },
      { label: "Modular", value: modularLabel },
    ],
    technicalSpecifications: [
      { label: "PCIe 8-pin Connectors", value: formatDetailValue(specifications.pcie_8pin_count) },
      { label: "12VHPWR Connectors", value: formatDetailValue(specifications.pcie_12vhpwr) },
    ],
  };
};

const CATEGORY_VIEW_MODELS = {
  RAM: getRamDetailViewModel,
  STORAGE: getStorageDetailViewModel,
  MOTHERBOARD: getMotherboardDetailViewModel,
  PSU: getPsuDetailViewModel,
};

export const getCategoryDetailViewModel = (hardware) => {
  const factory = CATEGORY_VIEW_MODELS[hardware?.type];
  return factory ? factory(hardware) : getCpuDetailViewModel(hardware);
};

export const getDetailComparisonAction = (compareList, hardwareId) => {
  const selectedIndex = compareList.findIndex((item) => item.id === hardwareId);
  const alreadySelected = selectedIndex !== -1;
  const comparisonFull = compareList.length >= 2 && !alreadySelected;

  return {
    alreadySelected,
    comparisonFull,
    comparisonSlot: alreadySelected ? selectedIndex + 1 : compareList.length + 1,
    shouldNavigateToComparison:
      !alreadySelected && compareList.length === 1 && !comparisonFull,
  };
};
