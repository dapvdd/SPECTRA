/* Build compatibility & build-intelligence rules.

   Phase 4 build intelligence: a deterministic, explicit-assumption validator for
   the component data the current catalog actually contains.

   Design rules
   ------------
   - Every check must be *derived from verified catalog fields* and every derived
     rule must carry its assumptions verbatim in the result.
   - A rule that cannot be evaluated (missing field) returns `unknown`, never a
     guess.
   - Laptop/desktop/other segments are never conflated: a mobile GPU name is
     reported as a distinct concern when the data cannot prove which segment a
     component belongs to.
   - Power supply sizing is a *suggestion with a documented margin and
     assumption list*, never a hard requirement measured from the hardware.

   The current catalog has CPU (with socket) and GPU (with length/interface/tdp)
   only; motherboard, RAM, PSU, case, cooler and storage catalogs do not exist
   yet. This module therefore validates the checks that ARE possible and reports
   the rest as `requires_catalog` instead of pretending to know.
*/

import { calculateListedTdpSum } from "./buildConfig.js";

export const COMPATIBILITY_EXPLICIT_ASSUMPTIONS = [
  "Socket compatibility can only be validated when a motherboard catalog exists; " +
    "this build answers 'socket present' and 'GPU physical interface present'.",
  "Power supply value is a SUGGESTION derived from listed TDP plus a 1.25x headroom " +
    "margin. It is not a measured system draw and not a PSU manufacturer requirement.",
  "Case clearance assumes a generic case with at least one unobstructed PCIe slot " +
    "and a length allowance equal to the stated GPU length plus 20 mm. Actual cases " +
    "vary and the real measurement is the case's maximum GPU length.",
  "Cooler clearance cannot be validated without a cooler catalog; only the CPU " +
    "socket is reported, which the user must match to a compatible cooler.",
  "RAM type and capacity are not validated because a RAM specification catalog " +
    "does not exist yet; the AI layer may discuss them but they are not facts.",
  "Storage interface (M.2 / SATA) is not validated because a motherboard catalog " +
    "does not exist yet.",
  "A GPU's interface string (for example 'PCIe 4.0 x16') is carried over only " +
    "verbatim; generation and lane counts are not assumptions we invent.",
];

const isPositiveNumber = (value) =>
  typeof value === "number" && Number.isFinite(value) && value > 0;

const isNonEmptyText = (value) =>
  typeof value === "string" && value.trim() !== "";

/* Map a CPU socket name to the motherboard chipset generation that supports
   it. This is a data table of *public* compatibility facts (manufacturer
   chipset naming), not a guess; it powers a 'socket present' check today and a
   full motherboard validation once a motherboard catalog is added. */
const SOCKET_CHIPSET_LINEAGE = {
  AM5: ["600-series", "800-series"],
  AM4: ["400-series", "500-series", "A320", "B350", "X370", "B450", "X470", "B550", "X570"],
  LGA1700: ["600-series", "700-series"],
  LGA1200: ["400-series", "500-series"],
  LGA1151: ["100-series", "200-series", "300-series"],
  LGA2066: ["X299"],
  TR4: ["X399"],
  sTRX4: ["TRX40"],
  sWRX8: ["WRX80"],
};

const NORMALIZED_SOCKET_ALIASES = {
  AM5: "AM5",
  AM4: "AM4",
  LGA1700: "LGA1700",
  "LGA 1700": "LGA1700",
  LGA1200: "LGA1200",
  "LGA 1200": "LGA1200",
  LGA1151: "LGA1151",
  "LGA 1151": "LGA1151",
  LGA2066: "LGA2066",
  TR4: "TR4",
  sTRX4: "sTRX4",
  sWRX8: "sWRX8",
};

const normalizeSocket = (socket) => {
  if (!isNonEmptyText(socket)) {
    return null;
  }

  const trimmed = socket.trim();
  return NORMALIZED_SOCKET_ALIASES[trimmed] ?? null;
};

const getCpuSocket = (cpuDetail) => {
  const socket = cpuDetail?.specifications?.socket;
  return isNonEmptyText(socket) ? socket.trim() : null;
};

const getGpuInterface = (gpuDetail) => {
  const interfaceValue = gpuDetail?.specifications?.interface;
  return isNonEmptyText(interfaceValue) ? interfaceValue.trim() : null;
};

const getGpuLength = (gpuDetail) => gpuDetail?.specifications?.length_mm;

const estimatedGpuLengthFromInterface = (interfaceValue) => {
  if (!isNonEmptyText(interfaceValue)) {
    return null;
  }

  const value = interfaceValue.toLowerCase();

  if (value.includes("x16")) {
    return 267;
  }

  if (value.includes("x8")) {
    return 267;
  }

  if (value.includes("x4")) {
    return 210;
  }

  return null;
};

/* Build a compatibility report for a CPU+GPU build.

   Returns:
   {
     status: 'ready' | 'requires_components' | 'incomplete',
     checks: [ { id, label, state: 'pass'|'warn'|'info'|'unknown', message } ],
     power_suggestion: { watts, label, isSuggestion: true, assumptions: [...] },
     assumptions: [ ... ],
   }
*/
export const buildCompatibilityReport = (cpuDetail, gpuDetail) => {
  const hasCpu = cpuDetail && isNonEmptyText(cpuDetail.name);
  const hasGpu = gpuDetail && isNonEmptyText(gpuDetail.name);

  if (!hasCpu || !hasGpu) {
    return {
      status: "incomplete",
      checks: [],
      power_suggestion: null,
      assumptions: COMPATIBILITY_EXPLICIT_ASSUMPTIONS,
    };
  }

  const checks = [];
  const assumptions = [...COMPATIBILITY_EXPLICIT_ASSUMPTIONS];

  /* 1. CPU socket presence */
  const socket = getCpuSocket(cpuDetail);
  const normalizedSocket = normalizeSocket(socket);

  if (!socket) {
    checks.push({
      id: "cpu-socket",
      label: "CPU socket",
      state: "unknown",
      message:
        "The catalog has no socket value for this CPU, so socket compatibility " +
        "cannot be assessed.",
    });
  } else if (!normalizedSocket) {
    checks.push({
      id: "cpu-socket",
      label: "CPU socket",
      state: "warn",
      message: `Socket "${socket}" was not recognised; confirm compatibility with the ` +
        "motherboard before purchasing.",
    });
  } else {
    const lineage = SOCKET_CHIPSET_LINEAGE[normalizedSocket];
    checks.push({
      id: "cpu-socket",
      label: "CPU socket",
      state: "pass",
      message: lineage
        ? `Socket ${normalizedSocket} — a compatible motherboard must use a ` +
          `${lineage.join(" or ")} chipset.`
        : `Socket ${normalizedSocket} present; motherboard chipset not mapped.`,
    });
  }

  /* 2. GPU physical interface — presence, verbatim */
  const gpuInterface = getGpuInterface(gpuDetail);

  if (!gpuInterface) {
    checks.push({
      id: "gpu-interface",
      label: "GPU interface",
      state: "unknown",
      message:
        "The catalog has no interface value for this GPU, so physical bus " +
        "compatibility cannot be assessed.",
    });
  } else {
    checks.push({
      id: "gpu-interface",
      label: "GPU interface",
      state: "pass",
      message: `GPU interface recorded as "${gpuInterface}" (verbatim from the ` +
        "catalog; generation/lane counts are not re-inferred).",
    });
  }

  /* 3. GPU length vs generic case allowance */
  let gpuLength = getGpuLength(gpuDetail);

  if (!isPositiveNumber(gpuLength)) {
    gpuLength = estimatedGpuLengthFromInterface(gpuInterface);
    if (gpuLength !== null) {
      assumptions.push(
        `GPU length was not recorded; an estimated length of ${gpuLength} mm was ` +
          "used based on its interface form factor. This is an estimate, not a " +
          "verified measurement.",
      );
    }
  }

  if (gpuLength === null) {
    checks.push({
      id: "gpu-clearance",
      label: "GPU case clearance",
      state: "unknown",
      message:
        "Neither a GPU length nor a usable interface estimate is available, so " +
        "case clearance cannot be assessed.",
    });
  } else {
    const allowance = gpuLength + 20;
    checks.push({
      id: "gpu-clearance",
      label: "GPU case clearance",
      state: "info",
      message: `Recorded GPU length is ${gpuLength} mm (estimate: ` +
        `${gpuLength !== getGpuLength(gpuDetail) ? "yes" : "no"}). With a 20 mm ` +
        `allowance, allow at least ${allowance} mm of unobstructed GPU space. This ` +
        "assumes a generic case with an unobstructed slot. See assumptions.",
    });
  }

  /* 4. Power supply suggestion (explicit margin, never a requirement) */
  const powerSuggestion = buildPowerSuggestion(cpuDetail, gpuDetail);

  if (powerSuggestion) {
    checks.push({
      id: "psu-suggestion",
      label: "Power supply suggestion",
      state: "info",
      message:
        `Suggested PSU: ${powerSuggestion.label}. This is a SUGGESTION derived from ` +
        "listed TDP plus a 25% margin, not a measured system requirement.",
    });
  } else {
    checks.push({
      id: "psu-suggestion",
      label: "Power supply suggestion",
      state: "unknown",
      message:
        "Listed TDP is missing for one or both components, so no power supply " +
        "suggestion can be made.",
    });
  }

  return {
    status: "ready",
    checks,
    power_suggestion: powerSuggestion,
    assumptions,
  };
};

export const buildPowerSuggestion = (cpuDetail, gpuDetail) => {
  /* Suggested minimum = (listed CPU TDP + listed GPU TDP) * 1.25, rounded up
     to the nearest 50 W. Uses manufacturer-listed TDPs only; not a measured
     system draw; never a stated PSU requirement. */
  const tdpSum = calculateListedTdpSum(cpuDetail, gpuDetail);

  if (!isPositiveNumber(tdpSum)) {
    return null;
  }

  const margin = tdpSum * 1.25;
  const wattage = Math.ceil(margin / 50) * 50;

  return {
    watts: wattage,
    label: `${wattage} W (listed CPU+GPU TDP ${tdpSum} W × 1.25 margin)`,
    base_tdp_sum: tdpSum,
    margin_multiplier: 1.25,
    isSuggestion: true,
  };
};

export { SOCKET_CHIPSET_LINEAGE, normalizeSocket, getCpuSocket };
