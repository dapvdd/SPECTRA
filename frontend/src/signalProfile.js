/* Derives the real composition of the loaded hardware catalog.

   Every figure the SPECTRA SIGNAL shows comes from the catalog payload the
   app has already fetched. Nothing here estimates, extrapolates or invents a
   value, and no field is derived from a benchmark it has not been given. */

const isRecord = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

export const SIGNAL_CHANNEL_ORDER = ["CPU", "GPU"];

/* Anything the catalog reports that is not a CPU or a GPU is grouped under
   "Other" rather than dropped, so the channels always sum to the total. */
export const SIGNAL_OTHER_CHANNEL = "Other";

const MAX_MANUFACTURER_CHANNELS = 4;

export const formatSignalCount = (value) =>
  Number.isFinite(value) && value > 0 ? value.toLocaleString("en-US") : "0";

const emptyProfile = () => ({
  isEmpty: true,
  total: 0,
  channels: [],
  manufacturers: [],
});

const countBy = (items, keyFor) =>
  items.reduce((counts, item) => {
    const key = keyFor(item);

    if (key) {
      counts.set(key, (counts.get(key) || 0) + 1);
    }

    return counts;
  }, new Map());

export const buildSignalProfile = (hardware) => {
  if (!Array.isArray(hardware) || hardware.length === 0) {
    return emptyProfile();
  }

  const typeCounts = countBy(hardware, (item) =>
    isRecord(item) && typeof item.type === "string" && item.type.trim()
      ? item.type.trim()
      : null
  );

  const typeTotal = [...typeCounts.values()].reduce((sum, value) => sum + value, 0);

  // Order CPU then GPU, then any remaining types by volume, then "Other".
  const orderedTypes = [...typeCounts.entries()].sort(([a], [b]) => {
    const aIndex = SIGNAL_CHANNEL_ORDER.indexOf(a);
    const bIndex = SIGNAL_CHANNEL_ORDER.indexOf(b);

    if (aIndex !== bIndex) {
      return (aIndex === -1 ? Number.MAX_SAFE_INTEGER : aIndex) -
        (bIndex === -1 ? Number.MAX_SAFE_INTEGER : bIndex);
    }

    return typeCounts.get(b) - typeCounts.get(a);
  });

  const channels = orderedTypes.map(([label, value]) => ({
    label,
    value,
    // Share of the real total, expressed as a percentage. Never a progress
    // value: it cannot reach 100 for a single channel unless it is the only one.
    share: typeTotal > 0 ? (value / typeTotal) * 100 : 0,
  }));

  const manufacturerCounts = countBy(
    hardware,
    (item) =>
      isRecord(item) && typeof item.manufacturer === "string" && item.manufacturer.trim()
        ? item.manufacturer.trim()
        : null
  );

  const manufacturers = [...manufacturerCounts.entries()]
    .sort(([, a], [, b]) => b - a || 0)
    .slice(0, MAX_MANUFACTURER_CHANNELS)
    .map(([label, value]) => ({ label, value }));

  return {
    isEmpty: false,
    total: typeTotal,
    channels,
    manufacturers,
  };
};

export const getSignalPrimaryLabel = (profile) =>
  profile?.isEmpty ? "Catalog profile" : "Catalog composition";

export const getSignalStatusLabel = (profile, { loading = false, error = "" } = {}) => {
  if (loading) {
    return "Loading";
  }

  if (error) {
    return "Unavailable";
  }

  return profile?.isEmpty ? "No records" : "Verified records";
};