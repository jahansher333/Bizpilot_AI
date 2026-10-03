"use client";

import React, { useEffect, useId, useRef } from "react";
import { Icon } from "@/components/ui/icon";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface SheetProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

/** Design `.sheet`: a right-hand panel for forms. Focus is trapped and restored; Esc closes. */
export function Sheet({ open, title, onClose, children, footer }: SheetProps) {
  const panelRef = useRef<HTMLElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const firstField = panel?.querySelector<HTMLElement>("input, select, textarea") ?? panel?.querySelector<HTMLElement>(FOCUSABLE);
    firstField?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    panel?.addEventListener("keydown", onKeyDown);
    return () => {
      panel?.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sheet-wrap">
      <div style={{ flex: 1 }} onClick={onClose} aria-hidden="true" />
      <aside ref={panelRef} className="sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="sheet-h">
          <h2 className="t-h2" id={titleId}>
            {title}
          </h2>
          <button type="button" className="btn btn-ghost icon-btn" aria-label="Close" onClick={onClose}>
            <Icon name="close" size="lg" />
          </button>
        </div>
        <div className="sheet-b">{children}</div>
        {footer && <div className="sheet-f">{footer}</div>}
      </aside>
    </div>
  );
}
