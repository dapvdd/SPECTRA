import { apiUrl } from "./api.js";
import {
  assertSuccessfulResponse,
  validateHardwareDetailPayload,
} from "./apiValidation.js";

export const requestHardwareDetail = async (
  hardwareId,
  fetchImplementation = fetch
) => {
  const response = await fetchImplementation(
    apiUrl(`/hardware/${hardwareId}`)
  );
  const payload = await assertSuccessfulResponse(response).json();
  return validateHardwareDetailPayload(payload, hardwareId);
};

export const createDetailRequestGuard = () => {
  let currentRequestId = 0;

  return {
    begin: () => (currentRequestId += 1),
    isCurrent: (requestId) => requestId === currentRequestId,
    invalidate: () => (currentRequestId += 1),
  };
};