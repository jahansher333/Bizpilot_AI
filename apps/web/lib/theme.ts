/**
 * Light/dark theme (R10c). The preference is a per-device display setting, so it lives in
 * localStorage; "system" follows the operating system. The resolved theme is set as
 * `data-theme` on <html>, which `html[data-theme="dark"] .bp` in bizpilot.css picks up.
 */
export type ThemePreference = "system" | "light" | "dark";
export type Theme = "light" | "dark";

export const THEME_KEY = "bizpilot_theme";
export const THEME_EVENT = "bizpilot:theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function readThemePreference(): ThemePreference {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function resolveTheme(pref: ThemePreference): Theme {
  if (pref !== "system") return pref;
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

export function applyTheme(pref: ThemePreference = readThemePreference()): Theme {
  const theme = resolveTheme(pref);
  document.documentElement.setAttribute("data-theme", theme);
  return theme;
}

export function setThemePreference(pref: ThemePreference): void {
  try {
    if (pref === "system") window.localStorage.removeItem(THEME_KEY);
    else window.localStorage.setItem(THEME_KEY, pref);
  } catch {
    // Storage blocked (private mode): the choice still applies for this page view.
  }
  applyTheme(pref);
  window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: pref }));
}

/** Runs in <head> before first paint, so dark-mode users never see a white flash. Keep in sync with the functions above. */
export const THEME_SCRIPT = `(function(){try{var p=localStorage.getItem("${THEME_KEY}");var d=p==="dark"||(p!=="light"&&window.matchMedia&&window.matchMedia("${DARK_QUERY}").matches);document.documentElement.setAttribute("data-theme",d?"dark":"light")}catch(e){}})()`;

/** Re-applies the theme when the OS setting changes (while following the system) or another tab changes it. */
export function watchSystemTheme(): () => void {
  const mql = typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY) : null;
  const onSystem = () => {
    if (readThemePreference() === "system") applyTheme("system");
  };
  const onStorage = (e: StorageEvent) => {
    if (e.key === THEME_KEY || e.key === null) applyTheme();
  };
  mql?.addEventListener("change", onSystem);
  window.addEventListener("storage", onStorage);
  return () => {
    mql?.removeEventListener("change", onSystem);
    window.removeEventListener("storage", onStorage);
  };
}
