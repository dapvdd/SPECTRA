const isRecord = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const isUsableHardwareId = (value) =>
  typeof value === "number" && Number.isInteger(value) && value > 0;

const isNonEmptyString = (value) =>
  typeof value === "string" && value.trim().length > 0;

const isOptionalText = (value) =>
  value === null || value === undefined || typeof value === "string";

const GPU_SPEC_FIELDS = [
  "memory_gb",
  "memory_type",
  "core_clock_mhz",
  "boost_clock_mhz",
  "vram_bandwidth_gbps",
  "tdp_w",
  "interface",
  "length_mm",
];

const isScalarSpecValue = (value) =>
  value === null ||
  value === undefined ||
  typeof value === "number" ||
  typeof value === "string" ||
  typeof value === "boolean";

const assertGpuSpecificationValues = (specifications) => {
  for (const field of GPU_SPEC_FIELDS) {
    if (
      Object.hasOwn(specifications, field) &&
      !isScalarSpecValue(specifications[field])
    ) {
      throw new Error(
        "GPU hardware response has an invalid specification value."
      );
    }
  }
};

export const assertSuccessfulResponse = (response) => {
  if (!response?.ok) {
    throw new Error(`HTTP error: ${response?.status ?? "unknown"}`);
  }

  return response;
};

const assertHardwareIdentity = (payload, expectedId) => {
  if (!isRecord(payload)) {
    throw new Error("Hardware response must be an object.");
  }

  if (isNonEmptyString(payload.error)) {
    throw new Error(payload.error);
  }

  if (!isUsableHardwareId(payload.id)) {
    throw new Error("Hardware response has an invalid id.");
  }

  if (expectedId !== undefined && payload.id !== expectedId) {
    throw new Error("Hardware response id does not match the requested CPU.");
  }

  if (!isNonEmptyString(payload.name)) {
    throw new Error("Hardware response has an invalid name.");
  }

  if (
    !isOptionalText(payload.manufacturer) ||
    !isOptionalText(payload.type) ||
    !isOptionalText(payload.release_date) ||
    !isOptionalText(payload.architecture)
  ) {
    throw new Error("Hardware response has an invalid text field.");
  }
};

export const validateCatalogPayload = (payload) => {
  if (!Array.isArray(payload)) {
    throw new Error("Hardware catalog response must be an array.");
  }

  payload.forEach((item) => {
    assertHardwareIdentity(item);
  });

  return payload;
};

export const validateHardwareDetailPayload = (payload, expectedId) => {
  assertHardwareIdentity(payload, expectedId);

  if (
    payload.specifications !== undefined &&
    payload.specifications !== null &&
    !isRecord(payload.specifications)
  ) {
    throw new Error("Hardware response has invalid specifications.");
  }

  if (payload.type === "GPU" && isRecord(payload.specifications)) {
    assertGpuSpecificationValues(payload.specifications);
  }

  return payload;
};

export const validateComparisonDetailPayload = (payload, expectedId) => {
  validateHardwareDetailPayload(payload, expectedId);

  if (!isRecord(payload.specifications)) {
    throw new Error("Comparison hardware response is missing specifications.");
  }

  return payload;
};

const getBenchmarkRecords = (payload) => {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (!isRecord(payload)) {
    return null;
  }

  if (Array.isArray(payload.benchmark_results)) {
    return payload.benchmark_results;
  }

  if (Array.isArray(payload.benchmarks)) {
    return payload.benchmarks;
  }

  if (Array.isArray(payload.results)) {
    return payload.results;
  }

  if (isRecord(payload.performance) && Array.isArray(payload.performance.results)) {
    return payload.performance.results;
  }

  return null;
};

export const validateBenchmarkPayload = (payload) => {
  const records = getBenchmarkRecords(payload);

  if (!records) {
    throw new Error("Benchmark response has an invalid structure.");
  }

  if (records.some((record) => !isRecord(record))) {
    throw new Error("Benchmark response contains an invalid record.");
  }

  return payload;
};
