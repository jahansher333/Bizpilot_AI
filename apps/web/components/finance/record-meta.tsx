import React from "react";
import { Icon, IconName } from "@/components/ui/icon";

/** Payments and expenses: "active" records count; corrected and voided ones stay visible but don't. */
export const RECORD_STATUS: Record<string, { label: string; cls: string; icon: IconName }> = {
  active: { label: "Recorded", cls: "b-info", icon: "check" },
  corrected: { label: "Corrected", cls: "b-warning", icon: "edit" },
  voided: { label: "Voided", cls: "b-danger", icon: "ban" },
};

export function RecordStatusBadge({ status }: { status: string }) {
  const meta = RECORD_STATUS[status];
  return (
    <span className={`badge ${meta?.cls ?? "b-neutral"}`}>
      {meta && <Icon name={meta.icon} />}
      {meta?.label ?? status}
    </span>
  );
}

/** "9,120" or "9120.50" → minor units; null when empty or not a positive amount with ≤ 2 decimals. */
export function parseAmountMinor(text: string): number | null {
  const clean = text.replace(/,/g, "").trim();
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const minor = Math.round(parseFloat(clean) * 100);
  return minor > 0 ? minor : null;
}

/** Today's date in the browser's timezone, as YYYY-MM-DD for <input type="date">. */
export function todayInput(now: Date = new Date()): string {
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

/**
 * Timestamp for a picked date. Today → undefined so the server records the actual time;
 * another day → midday local time, so it can't slip into a neighbouring day.
 */
export function pickedDateToIso(date: string, now: Date = new Date()): string | undefined {
  if (!date || date === todayInput(now)) return undefined;
  return new Date(`${date}T12:00:00`).toISOString();
}

/** First and last day of the current month as YYYY-MM-DD (browser timezone). */
export function thisMonthRange(now: Date = new Date()): { start: string; end: string } {
  const today = todayInput(now);
  const [y, m] = today.split("-").map(Number);
  const last = new Date(y, m, 0).getDate();
  return { start: `${today.slice(0, 7)}-01`, end: `${today.slice(0, 7)}-${String(last).padStart(2, "0")}` };
}
