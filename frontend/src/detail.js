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
