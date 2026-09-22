const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export const getApiBaseUrl = (configuredBaseUrl = import.meta.env?.VITE_API_BASE_URL) =>
  (configuredBaseUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, "");

export const API_BASE_URL = getApiBaseUrl();

export const apiUrl = (path) => `${API_BASE_URL}/${path.replace(/^\/+/, "")}`;
