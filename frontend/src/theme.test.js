import test from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_THEME_PREFERENCE,
  FALLBACK_THEME,
  THEME_PREFERENCES,
  THEME_STORAGE_KEY,
  applyThemeToDocument,
  createThemePreferenceState,
  getPrefersColorSchemeDark,
  getThemePreferenceForTheme,
  normalizeThemePreference,
  readStoredThemePreference,
  resolveTheme,
  selectThemePreference,
  writeStoredThemePreference,
} from "./theme.js";

const createStorage = (initial = {}) => {
  const store = new Map(Object.entries(initial));

  return {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    dump: () => Object.fromEntries(store),
  };
};

const throwingStorage = () => ({
  getItem() {
    throw new Error("storage unavailable");
  },
  setItem() {
    throw new Error("storage unavailable");
  },
});

const createDocument = () => {
  const attributes = {};

  return {
    attributes,
    documentElement: {
      setAttribute: (name, value) => {
        attributes[name] = value;
      },
    },
  };
};

test("theme preferences are exactly system, dark and light", () => {
  assert.deepEqual(THEME_PREFERENCES, ["system", "dark", "light"]);
  assert.equal(DEFAULT_THEME_PREFERENCE, "system");
});

test("unrecognised preferences fall back to system", () => {
  assert.equal(normalizeThemePreference("dark"), "dark");
  assert.equal(normalizeThemePreference("light"), "light");
  assert.equal(normalizeThemePreference("system"), "system");
  assert.equal(normalizeThemePreference("solarized"), "system");
  assert.equal(normalizeThemePreference(undefined), "system");
  assert.equal(normalizeThemePreference(null), "system");
  assert.equal(normalizeThemePreference(42), "system");
});

test("system resolves from the OS preference", () => {
  assert.equal(resolveTheme("system", true), "dark");
  assert.equal(resolveTheme("system", false), "light");
});

test("explicit preferences always win over the OS preference", () => {
  assert.equal(resolveTheme("dark", false), "dark");
  assert.equal(resolveTheme("light", true), "light");
});

test("a missing media query resolves to dark, the product identity", () => {
  assert.equal(resolveTheme("system", undefined), FALLBACK_THEME);
  assert.equal(resolveTheme("system", null), "dark");
  assert.equal(getPrefersColorSchemeDark(undefined), false);
  assert.equal(getPrefersColorSchemeDark({ matches: true }), true);
});

test("preference and resolved theme stay distinguishable after a reload", () => {
  assert.equal(getThemePreferenceForTheme("dark"), "dark");
  assert.equal(getThemePreferenceForTheme("light"), "light");
  assert.equal(getThemePreferenceForTheme("system"), "system");
  assert.equal(getThemePreferenceForTheme("sepia"), "system");
});

test("preference state carries both the choice and its resolution", () => {
  assert.deepEqual(createThemePreferenceState("dark", false), {
    preference: "dark",
    theme: "dark",
  });

  assert.deepEqual(createThemePreferenceState("system", true), {
    preference: "system",
    theme: "dark",
  });

  assert.deepEqual(createThemePreferenceState("nonsense", false), {
    preference: "system",
    theme: "light",
  });
});

test("selecting a preference re-resolves the theme from it", () => {
  const dark = createThemePreferenceState("system", true);
  assert.deepEqual(selectThemePreference(dark, "light"), {
    preference: "light",
    theme: "light",
  });

  const light = createThemePreferenceState("light", false);
  assert.deepEqual(selectThemePreference(light, "dark"), {
    preference: "dark",
    theme: "dark",
  });
});

test("stored preferences round-trip through storage", () => {
  const storage = createStorage();

  assert.equal(readStoredThemePreference(storage), "system");

  assert.equal(writeStoredThemePreference(storage, "light"), "light");
  assert.equal(storage.getItem(THEME_STORAGE_KEY), "light");
  assert.equal(readStoredThemePreference(storage), "light");

  writeStoredThemePreference(storage, "nonsense");
  assert.equal(storage.getItem(THEME_STORAGE_KEY), "system");
});

test("unavailable storage degrades to system without throwing", () => {
  const storage = throwingStorage();

  assert.equal(readStoredThemePreference(storage), "system");
  assert.equal(writeStoredThemePreference(storage, "dark"), "dark");
  assert.equal(readStoredThemePreference(undefined), "system");
  assert.equal(writeStoredThemePreference(undefined, "dark"), "dark");
});

test("only light is written to the document; everything else is dark", () => {
  const documentLike = createDocument();

  assert.equal(applyThemeToDocument("light", documentLike), "light");
  assert.equal(documentLike.attributes["data-theme"], "light");

  assert.equal(applyThemeToDocument("dark", documentLike), "dark");
  assert.equal(applyThemeToDocument("sepia", documentLike), "dark");
  assert.equal(applyThemeToDocument(undefined, documentLike), "dark");
  assert.equal(documentLike.attributes["data-theme"], "dark");
});

test("the preference attribute stays in step with the resolved theme", () => {
  const documentLike = createDocument();

  applyThemeToDocument("dark", documentLike, "system");
  assert.equal(documentLike.attributes["data-theme-preference"], "system");

  applyThemeToDocument("light", documentLike, "light");
  assert.equal(documentLike.attributes["data-theme"], "light");
  assert.equal(documentLike.attributes["data-theme-preference"], "light");

  applyThemeToDocument("dark", documentLike, "nonsense");
  assert.equal(documentLike.attributes["data-theme-preference"], "system");
});

test("an omitted preference leaves the attribute untouched", () => {
  const documentLike = createDocument();

  applyThemeToDocument("light", documentLike, "light");
  applyThemeToDocument("dark", documentLike);

  assert.equal(documentLike.attributes["data-theme"], "dark");
  assert.equal(documentLike.attributes["data-theme-preference"], "light");
});

test("applying a theme to a missing document is a no-op", () => {
  assert.equal(applyThemeToDocument("light", undefined), "light");
  assert.equal(applyThemeToDocument("light", {}), "light");
  assert.equal(applyThemeToDocument("light", {}, "light"), "light");
});