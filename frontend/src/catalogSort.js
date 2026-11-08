/* Client-side catalog ordering.

   The backend owns filtering and pagination; ordering of the already-fetched
   catalog page is a pure view concern. Release dates in the catalog are
   ISO strings (or null), so string comparison is correct where present and
   nulls always sort last regardless of direction. Name is the stable
   tiebreaker so equal-key records keep a deterministic order. */

const DIRECTIONS = ["default", "name-asc", "name-desc", "newest", "oldest"];

export const CATALOG_SORTS = [
  { key: "default", label: "Default" },
  { key: "name-asc", label: "Name A–Z" },
  { key: "name-desc", label: "Name Z–A" },
  { key: "newest", label: "Newest" },
  { key: "oldest", label: "Oldest" },
];

const isIsoDate = (value) =>
  typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value);

const byNameAsc = (a, b) =>
  String(a?.name ?? "").localeCompare(String(b?.name ?? ""));

const byDateAsc = (a, b) => {
  const aDate = isIsoDate(a?.release_date) ? a.release_date : null;
  const bDate = isIsoDate(b?.release_date) ? b.release_date : null;

  if (aDate && bDate) {
    return aDate < bDate ? -1 : aDate > bDate ? 1 : 0;
  }
  if (aDate) {
    return -1;
  }
  if (bDate) {
    return 1;
  }
  return 0;
};

/* Date-descending without flipping the nulls-last rule: only the relative
   order of two dated records inverts. */
const byDateDesc = (a, b) => {
  const bothDated =
    isIsoDate(a?.release_date) && isIsoDate(b?.release_date);

  if (bothDated) {
    return byDateAsc(b, a);
  }
  return byDateAsc(a, b);
};

export const isCatalogSortKey = (value) => DIRECTIONS.includes(value);

export const sortCatalogItems = (items, sortKey = "default") => {
  if (!Array.isArray(items) || sortKey === "default") {
    return Array.isArray(items) ? items : [];
  }

  const sorted = [...items];

  switch (sortKey) {
    case "name-asc":
      sorted.sort(byNameAsc);
      break;
    case "name-desc":
      sorted.sort((a, b) => byNameAsc(b, a));
      break;
    case "newest":
      sorted.sort((a, b) => byDateDesc(a, b) || byNameAsc(a, b));
      break;
    case "oldest":
      sorted.sort((a, b) => byDateAsc(a, b) || byNameAsc(a, b));
      break;
    default:
      break;
  }

  return sorted;
};
