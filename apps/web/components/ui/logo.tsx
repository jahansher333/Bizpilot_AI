import React from "react";

/** BizPilot AI wordmark (design canvas `.logo`). */
export function Logo({ showText = true }: { showText?: boolean }) {
  return (
    <span className="logo">
      <span className="logo-mark">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 17L17 7" />
          <path d="M9 7h8v8" />
        </svg>
      </span>
      {showText && (
        <span className="lbl">
          BizPilot <span className="ai">AI</span>
        </span>
      )}
    </span>
  );
}

export function initials(name: string | null | undefined): string {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
