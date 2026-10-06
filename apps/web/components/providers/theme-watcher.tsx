"use client";

import { useEffect } from "react";
import { applyTheme, watchSystemTheme } from "@/lib/theme";

/** Keeps the theme in step with the OS and other tabs after the inline head script has set it. */
export function ThemeWatcher() {
  useEffect(() => {
    applyTheme();
    return watchSystemTheme();
  }, []);
  return null;
}
