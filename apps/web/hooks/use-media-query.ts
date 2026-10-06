"use client";

import { useSyncExternalStore } from "react";

/** Matches the stylesheet's phone breakpoint (`@media (max-width: 760px)` in bizpilot.css). */
export const PHONE_QUERY = "(max-width: 760px)";

/** True while the media query matches. False on the server and where matchMedia is unavailable. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => undefined;
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(query).matches,
    () => false
  );
}
