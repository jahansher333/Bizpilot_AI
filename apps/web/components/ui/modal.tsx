"use client";

import React, { useEffect, useId, useRef } from "react";
import { Icon } from "@/components/ui/icon";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  wide?: boolean;
  /** Destructive confirmations use alertdialog and are not dismissed by clicking the scrim. */
  tone?: "default" | "danger" | "warning";
  /** Element to focus first; defaults to the first focusable element. */
  initialFocusRef?: React.RefObject<HTMLElement | null>;
}

/** Design `.modal`: focus is trapped, restored on close, Esc dismisses. */
export function Modal({ open, title, description, onClose, children, footer, wide, tone = "default", initialFocusRef }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const first = initialFocusRef?.current ?? dialog?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !dialog) return;
      const nodes = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const firstNode = nodes[0];
      const lastNode = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === firstNode) {
        e.preventDefault();
        lastNode.focus();
      } else if (!e.shiftKey && document.activeElement === lastNode) {
        e.preventDefault();
        firstNode.focus();
      }
    }

    dialog?.addEventListener("keydown", onKeyDown);
    return () => {
      dialog?.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose, initialFocusRef]);

  if (!open) return null;

  const isAlert = tone !== "default";

  return (
    <div
      className="scrim"
      onMouseDown={(e) => {
        if (!isAlert && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className={`modal${wide ? " wide" : ""}`}
        role={isAlert ? "alertdialog" : "dialog"}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
      >
        <div className="modal-h">
          {isAlert && (
            <span className={`dlg-icon ${tone === "danger" ? "danger" : "warn"}`}>
              <Icon name="alert" size="lg" />
            </span>
          )}
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
            <h2 className="t-h2" id={titleId}>
              {title}
            </h2>
            {description && (
              <p className="t-body secondary" id={descId}>
                {description}
              </p>
            )}
          </div>
          {!isAlert && (
            <button type="button" className="btn btn-ghost btn-sm icon-btn" aria-label="Close dialog" onClick={onClose}>
              <Icon name="close" />
            </button>
          )}
        </div>
        {children && <div className="modal-b">{children}</div>}
        {footer && <div className="modal-f">{footer}</div>}
      </div>
    </div>
  );
}
