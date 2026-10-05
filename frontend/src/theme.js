/* Theme preference resolution.

   Kept free of React and of direct DOM reads so the resolution rules are
   testable on their own. The one impure step - writing the attribute onto
   the document element - is isolated at the bottom and called only by the
   component and by the boot script's mirrored logic in index.html. */

export const THEME_PREFERENCES = ["system", "dark", "light"];

export const THEME_STORAGE_KEY = "spectra-theme";

export const DEFAULT_THEME_PREFERENCE = "system";

/* Dark is the product identity, so it is the fallback for every unresolved
   case: an unrecognised stored value, an unavailable storage API, or a
   browser with no prefers-color-scheme support. */
export const FALLBACK_THEME = "dark";

export const normalizeThemePreference = (value) =>
  THEME_PREFERENCES.includes(value) ? value : DEFAULT_THEME_PREFERENCE;

/* An absent or non-boolean preference means "unknown", not "light", so it
   falls through to the dark identity rather than flipping the product on a
   missing value. Only an explicit false selects light. */
export const resolveTheme = (preference, prefersColorSchemeDark) => {
  const normalized = normalizeThemePreference(preference);

  if (normalized !== "system") {
    return normalized;
  }

  return prefersColorSchemeDark === false ? "light" : FALLBACK_THEME;
};

/* Round-trips the resolved theme back to a preference so "System" stays
   distinguishable from an explicit choice after a reload. */
export const getThemePreferenceForTheme = (theme) =>
  theme === "dark" || theme === "light" ? theme : DEFAULT_THEME_PREFERENCE;

export const readStoredThemePreference = (storage) => {
  try {
    return normalizeThemePreference(storage?.getItem(THEME_STORAGE_KEY));
  } catch {
    // Private mode, disabled storage, or a non-DOM storage stand-in.
    return DEFAULT_THEME_PREFERENCE;
  }
};

export const writeStoredThemePreference = (storage, preference) => {
  const normalized = normalizeThemePreference(preference);

  try {
    storage?.setItem(THEME_STORAGE_KEY, normalized);
  } catch {
    // A preference that cannot be persisted still applies for this session.
  }

  return normalized;
};

export const getPrefersColorSchemeDark = (mediaQueryListLike) =>
  Boolean(mediaQueryListLike?.matches);

export const createThemePreferenceState = (preference, prefersColorSchemeDark) => ({
  preference: normalizeThemePreference(preference),
  theme: resolveTheme(preference, prefersColorSchemeDark),
});

export const selectThemePreference = (state, preference) =>
  createThemePreferenceState(preference, state?.theme === "dark");

/* The single DOM write. Everything else in this module is pure.
   Both attributes are kept truthful so nothing inspecting the DOM can see a
   preference that disagrees with the theme actually in force. */
export const applyThemeToDocument = (theme, documentLike, preference) => {
  const resolved = theme === "light" ? "light" : FALLBACK_THEME;
  const root = documentLike?.documentElement;

  root?.setAttribute("data-theme", resolved);

  if (preference !== undefined) {
    root?.setAttribute("data-theme-preference", normalizeThemePreference(preference));
  }

  return resolved;
};