const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export const getApiBaseUrl = (configuredBaseUrl = import.meta.env?.VITE_API_BASE_URL) => {
  if (configuredBaseUrl === undefined || configuredBaseUrl === null || configuredBaseUrl === "") {
    return DEFAULT_API_BASE_URL.replace(/\/+$/, "");
  }
  return String(configuredBaseUrl).replace(/\/+$/, "");
};

export const API_BASE_URL = getApiBaseUrl();

export const apiUrl = (path, configuredBaseUrl) => {
  const base = getApiBaseUrl(configuredBaseUrl);
  const normalizedPath = String(path).replace(/^\/+/, "");
  if (normalizedPath === "") {
    return `${base}/`;
  }
  return `${base}/${normalizedPath}`;
};
