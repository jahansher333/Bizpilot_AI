"use client";

import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/ui/icon";

type ToastTone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastContextValue {
  notify: (toast: { title: string; description?: string; tone?: ToastTone }) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TONE_ICON = { success: "check", error: "alert", info: "info" } as const;
const TONE_CLASS = { success: "ok", error: "danger", info: "neutral" } as const;

/** Toasts from the design (`.toast`), announced politely via role="status". */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback<ToastContextValue["notify"]>(
    ({ title, description, tone = "success" }) => {
      const id = nextId.current++;
      setItems((current) => [...current.slice(-2), { id, title, description, tone }]);
      setTimeout(() => dismiss(id), 4000);
    },
    [dismiss]
  );

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        style={{ position: "fixed", right: 24, bottom: 24, zIndex: 60, display: "flex", flexDirection: "column", gap: 8, maxWidth: "calc(100vw - 32px)" }}
      >
        {items.map((t) => (
          <div key={t.id} className="toast" role={t.tone === "error" ? "alert" : "status"}>
            <span className={`dlg-icon ${TONE_CLASS[t.tone]}`} style={{ width: 24, height: 24 }}>
              <Icon name={TONE_ICON[t.tone]} size="sm" className={t.tone === "success" ? "check-anim" : ""} />
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="t-t">{t.title}</div>
              {t.description && <div className="t-body-sm secondary">{t.description}</div>}
            </div>
            <button type="button" className="btn btn-ghost btn-sm icon-btn" aria-label="Dismiss notification" onClick={() => dismiss(t.id)}>
              <Icon name="close" size="sm" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  // Outside the provider (isolated component tests) toasts become a no-op.
  return ctx ?? { notify: () => undefined };
}
