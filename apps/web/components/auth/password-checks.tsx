import React from "react";
import { Icon } from "@/components/ui/icon";

/** Must match the backend policy (AuthenticationSettings.password_min_length = 12). */
export const PASSWORD_MIN_LENGTH = 12;

export function passwordChecks(password: string, avoid: string[] = []) {
  const lowered = password.toLowerCase();
  const personal = avoid
    .flatMap((value) => value.toLowerCase().split(/[\s@.]+/))
    .filter((part) => part.length >= 3);
  return [
    { label: `At least ${PASSWORD_MIN_LENGTH} characters`, ok: password.length >= PASSWORD_MIN_LENGTH },
    { label: "Contains a letter", ok: /[a-z]/i.test(password) },
    { label: "Contains a number", ok: /[0-9]/.test(password) },
    { label: "Not your email or name", ok: password.length > 0 && !personal.some((part) => lowered.includes(part)) },
  ];
}

/** Strength bars + live checklist from the design (03 · Register, 05 · Reset). */
export function PasswordChecklist({ password, avoid = [], id }: { password: string; avoid?: string[]; id: string }) {
  const checks = passwordChecks(password, avoid);
  const score = checks.filter((c) => c.ok).length;
  const color = score <= 1 ? "var(--danger)" : score < 4 ? "var(--warning)" : "var(--success)";
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 4, marginTop: 2 }} aria-hidden="true">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} style={{ height: 4, borderRadius: 2, background: i <= score ? color : "var(--border)" }} />
        ))}
      </div>
      <ul id={id} aria-live="polite" style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "4px 12px", marginTop: 4 }}>
        {checks.map((c) => (
          <li key={c.label} style={{ display: "flex", gap: 6, alignItems: "center", font: "400 12.5px/18px var(--font)", color: c.ok ? "var(--success)" : "var(--text-muted)" }}>
            {c.ok ? (
              <Icon name="check" size="sm" style={{ strokeWidth: 2.4 }} />
            ) : (
              <svg className="i i-sm" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="7" />
              </svg>
            )}
            <span>{c.label}</span>
            <span className="sr-only">{c.ok ? "(met)" : "(not met)"}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function FieldError({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <span className="err" id={id}>
      <Icon name="alert" size="sm" />
      {children}
    </span>
  );
}
