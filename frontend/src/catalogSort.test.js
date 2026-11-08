import test from "node:test";
import assert from "node:assert/strict";

import {
  CATALOG_SORTS,
  isCatalogSortKey,
  sortCatalogItems,
} from "./catalogSort.js";

const ITEMS = [
  { id: 1, name: "Ryzen 9", release_date: "2022-09-27" },
  { id: 2, name: "Core i9", release_date: "2023-10-17" },
  { id: 3, name: "Radeon HD", release_date: null },
  { id: 4, name: "GeForce 256", release_date: "1999-08-31" },
  { id: 5, name: "Arc B580", release_date: "2024-12-12" },
];

test("CATALOG_SORTS exposes the five supported orders", () => {
  assert.deepEqual(
    CATALOG_SORTS.map((s) => s.key),
    ["default", "name-asc", "name-desc", "newest", "oldest"],
  );
});

test("default returns the items in catalog order without copying", () => {
  const items = [ITEMS[0], ITEMS[1]];
  assert.equal(sortCatalogItems(items, "default"), items);
});

test("non-array input returns an empty array", () => {
  assert.deepEqual(sortCatalogItems(null, "name-asc"), []);
  assert.deepEqual(sortCatalogItems(undefined, "newest"), []);
});

test("name-asc sorts case-sensitively by name", () => {
  const sorted = sortCatalogItems(ITEMS, "name-asc");
  assert.deepEqual(
    sorted.map((i) => i.name),
    ["Arc B580", "Core i9", "GeForce 256", "Radeon HD", "Ryzen 9"],
  );
});

test("name-desc reverses the name order", () => {
  const sorted = sortCatalogItems(ITEMS, "name-desc");
  assert.deepEqual(
    sorted.map((i) => i.name),
    ["Ryzen 9", "Radeon HD", "GeForce 256", "Core i9", "Arc B580"],
  );
});

test("newest puts records with dates first, newest date first, nulls last", () => {
  const sorted = sortCatalogItems(ITEMS, "newest");
  assert.deepEqual(
    sorted.map((i) => i.name),
    ["Arc B580", "Core i9", "Ryzen 9", "GeForce 256", "Radeon HD"],
  );
});

test("oldest puts oldest dated records first, nulls still last", () => {
  const sorted = sortCatalogItems(ITEMS, "oldest");
  assert.deepEqual(
    sorted.map((i) => i.name),
    ["GeForce 256", "Ryzen 9", "Core i9", "Arc B580", "Radeon HD"],
  );
});

test("dated records with equal dates tiebreak by name", () => {
  const tied = [
    { id: 1, name: "Zeta", release_date: "2020-01-01" },
    { id: 2, name: "Alpha", release_date: "2020-01-01" },
  ];
  const sorted = sortCatalogItems(tied, "newest");
  assert.deepEqual(sorted.map((i) => i.name), ["Alpha", "Zeta"]);
});

test("non-ISO date strings are treated as missing, never compared", () => {
  const odd = [
    { id: 1, name: "A", release_date: "recently" },
    { id: 2, name: "B", release_date: "2020-01-01" },
  ];
  const sorted = sortCatalogItems(odd, "oldest");
  assert.deepEqual(sorted.map((i) => i.name), ["B", "A"]);
});

test("isCatalogSortKey accepts only known keys", () => {
  assert.equal(isCatalogSortKey("newest"), true);
  assert.equal(isCatalogSortKey("default"), true);
  assert.equal(isCatalogSortKey("price"), false);
  assert.equal(isCatalogSortKey(undefined), false);
});
