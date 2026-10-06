"use client";

import React, { useMemo } from "react";
import { useCustomers } from "@/hooks/use-customers";
import { Icon, IconName } from "@/components/ui/icon";

/** Backend status → design label. "active" orders are shown as Completed (they count toward sales). */
export const ORDER_STATUS: Record<string, { label: string; cls: string; icon: IconName }> = {
  active: { label: "Completed", cls: "b-success", icon: "check" },
  corrected: { label: "Corrected", cls: "b-warning", icon: "edit" },
  voided: { label: "Voided", cls: "b-danger", icon: "ban" },
};

export function OrderStatusBadge({ status }: { status: string }) {
  const meta = ORDER_STATUS[status];
  return (
    <span className={`badge ${meta?.cls ?? "b-neutral"}`}>
      {meta && <Icon name={meta.icon} />}
      {meta?.label ?? status}
    </span>
  );
}

const TZ = "Asia/Karachi";

/** "Today, 11:58" / "Yesterday, 09:02" / "24 Sep 2026, 10:00" in Pakistan time. */
export function orderWhen(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const day = (x: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(x);
  const time = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }).format(d);
  if (day(d) === day(now)) return `Today, ${time}`;
  if (day(d) === day(new Date(now.getTime() - 86_400_000))) return `Yesterday, ${time}`;
  return new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(d);
}

/** Customer id → name for order rows (orders only carry the id). Includes archived customers. */
export function useCustomerNames(orgId: string, token?: string): Map<string, string> {
  const { data } = useCustomers(orgId, { limit: 100 }, token);
  return useMemo(() => new Map((data?.items ?? []).map((c) => [c.id, c.name])), [data]);
}

export const WALK_IN = "Walk-in customer";
