"use client";

import { RefObject, useEffect } from "react";

/** Closes a popover on outside click or Escape, returning focus to its trigger. */
export function useDismiss(
  open: boolean,
  containerRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  triggerRef?: RefObject<HTMLElement | null>
) {
  useEffect(() => {
    if (!open) return;
    function onPointer(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        triggerRef?.current?.focus();
      }
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, containerRef, onClose, triggerRef]);
}
