"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { DashboardPeriod, DashboardSummary, RecentActivityItem } from "@/lib/schemas/dashboard";
import { useDashboard } from "@/hooks/use-dashboard";
import { useOptionalAuth } from "@/hooks/use-auth";
import { fetchBalances } from "@/lib/api/inventory";
import { Icon, IconName } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { ErrorState, Skeleton } from "@/components/ui/states";

interface DashboardViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
}

const PERIODS: { key: DashboardPeriod; label: string; phrase: string }[] = [
  { key: "today", label: "Today", phrase: "today" },
  { key: "yesterday", label: "Yesterday", phrase: "yesterday" },
  { key: "this_week", label: "This week", phrase: "this week" },
  { key: "this_month", label: "This month", phrase: "this month" },
  { key: "custom", label: "Custom", phrase: "for the selected dates" },
];

function karachiHour(): number {
  return Number(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", hour: "numeric", hour12: false }).format(new Date()));
}

function greeting(): string {
  const h = karachiHour();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function minutesAgo(iso: string, now: number): string {
  const diff = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (diff < 1) return "just now";
  if (diff < 60) return `${diff} min ago`;
  return `${Math.round(diff / 60)} h ago`;
}

function formatTime(iso: string, timezone: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: timezone, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

const ACTIVITY: Record<RecentActivityItem["activity_type"], { label: string; icon: IconName; dot: string; section: string }> = {
  order: { label: "Order recorded", icon: "orders", dot: "", section: "orders" },
  payment: { label: "Payment recorded", icon: "payments", dot: "in", section: "payments" },
  expense: { label: "Expense recorded", icon: "expenses", dot: "out", section: "expenses" },
};

function MetricCard({
  label,
  icon,
  amountMinor,
  currency,
  caption,
  source,
  highlight,
}: {
  label: string;
  icon?: IconName;
  amountMinor: number;
  currency: string;
  caption: string;
  source: string;
  highlight?: boolean;
}) {
  return (
    <div className="card metric" style={highlight ? { background: "var(--brand-tint)", borderColor: "var(--brand-border)" } : undefined}>
      <span className="metric-l">
        {icon && <Icon name={icon} size="sm" />}
        {label}
      </span>
      <Money amountMinor={amountMinor} currency={currency} className="metric-v" style={highlight ? { color: "var(--brand-text)" } : undefined} />
      <span className="metric-c">{caption}</span>
      <span className="fresh" style={{ marginTop: 6 }}>
        {!highlight && <span className="live" />}
        {source}
      </span>
    </div>
  );
}

/** Design canvas "08 · Dashboard". */
export function DashboardView({ orgId, userRole = "owner", token }: DashboardViewProps) {
  const user = useOptionalAuth()?.user ?? null;
  const [period, setPeriod] = useState<DashboardPeriod>("today");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [applied, setApplied] = useState<{ start?: string; end?: string }>({});
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(timer);
  }, []);

  const customReady = period !== "custom" || (!!applied.start && !!applied.end);
  const { data, isLoading, error, refetch } = useDashboard(
    customReady ? orgId : "",
    { period, startDate: period === "custom" ? applied.start : undefined, endDate: period === "custom" ? applied.end : undefined },
    token
  );
  const { data: balances } = useQuery({
    queryKey: ["inventory", "balances", orgId, "total"],
    queryFn: () => fetchBalances(orgId, 1, 0, token),
    enabled: !!orgId,
  });

  const base = `/workspace/${orgId}`;
  const isStaff = userRole.toLowerCase() === "staff";
  const phrase = PERIODS.find((p) => p.key === period)?.phrase ?? "today";
  const firstName = (user?.display_name || "").trim().split(/\s+/)[0];

  const prompts = [
    "How are sales doing today?",
    "Which products are low on stock?",
    "How much did I collect today?",
    ...(isStaff ? [] : ["What are my expenses this month?"]),
    "Which products sell the most?",
  ];

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">
            {greeting()}
            {firstName ? `, ${firstName}` : ""}
          </h1>
          <p className="t-body secondary">Here’s what’s happening with your business {phrase}.</p>
        </div>
        <div className="ph-a">
          <div className="seg" role="group" aria-label="Reporting period">
            {PERIODS.map((p) => (
              <button key={p.key} type="button" aria-pressed={period === p.key} onClick={() => setPeriod(p.key)}>
                {p.label}
              </button>
            ))}
          </div>
          <Link className="btn btn-primary" href={`${base}/orders`}>
            <Icon name="plus" />
            New order
          </Link>
        </div>
      </div>

      {period === "custom" && (
        <form
          className="card card-b toolbar fade-in"
          onSubmit={(e) => {
            e.preventDefault();
            if (customStart && customEnd) setApplied({ start: customStart, end: customEnd });
          }}
          aria-label="Custom date range"
        >
          <div className="field">
            <label className="label" htmlFor="dash-start">
              From
            </label>
            <input className="input" id="dash-start" type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)} />
          </div>
          <div className="field">
            <label className="label" htmlFor="dash-end">
              To
            </label>
            <input className="input" id="dash-end" type="date" value={customEnd} min={customStart || undefined} onChange={(e) => setCustomEnd(e.target.value)} />
          </div>
          <button type="submit" className="btn btn-secondary" style={{ alignSelf: "flex-end" }} disabled={!customStart || !customEnd}>
            Apply dates
          </button>
        </form>
      )}

      {error && (
        <ErrorState title="Couldn’t load the dashboard" message={error instanceof Error ? error.message : undefined} onRetry={() => void refetch()} />
      )}

      {!customReady && !error && (
        <div className="alert a-neutral" role="status">
          <Icon name="info" />
          <div>Choose a start and end date, then apply them to see figures for that range.</div>
        </div>
      )}

      {isLoading && customReady && <DashboardSkeleton />}

      {data && (
        <DashboardContent
          data={data}
          base={base}
          isStaff={isStaff}
          now={now}
          healthyTotal={balances ? Math.max(0, balances.total - data.inventory.low_stock_count) : null}
          prompts={prompts}
        />
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading dashboard" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(230px, 100%), 1fr))", gap: 12 }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="card metric" style={{ gap: 10 }}>
            <Skeleton width={90} height={12} />
            <Skeleton width={150} height={26} />
            <Skeleton width={120} height={12} />
          </div>
        ))}
      </div>
      <div className="card card-b" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Skeleton height={12} />
        <Skeleton height={40} />
      </div>
    </div>
  );
}

function DashboardContent({
  data,
  base,
  isStaff,
  now,
  healthyTotal,
  prompts,
}: {
  data: DashboardSummary;
  base: string;
  isStaff: boolean;
  now: number;
  healthyTotal: number | null;
  prompts: string[];
}) {
  const tz = data.freshness.timezone;
  const updated = minutesAgo(data.freshness.generated_at, now);
  const items = data.inventory.items;
  const outCount = items.filter((i) => i.is_out_of_stock).length;
  const lowCount = data.inventory.low_stock_count - outCount;
  const tracked = healthyTotal !== null ? healthyTotal + data.inventory.low_stock_count : null;
  const pct = (n: number) => (tracked && tracked > 0 ? `${(n / tracked) * 100}%` : "0%");

  return (
    <>
      <section aria-label="Key figures" className="stagger" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(230px, 100%), 1fr))", gap: 12 }}>
        <MetricCard
          label="Sales"
          icon="orders"
          amountMinor={data.sales.total_sales_minor}
          currency={data.sales.currency_code}
          caption={`${data.sales.order_count} completed ${data.sales.order_count === 1 ? "order" : "orders"} · voided excluded`}
          source={`From Orders · updated ${updated}`}
        />
        <MetricCard
          label="Payments collected"
          icon="payments"
          amountMinor={data.payments.total_collected_minor}
          currency={data.payments.currency_code}
          caption={`${data.payments.payment_count} ${data.payments.payment_count === 1 ? "payment" : "payments"} recorded`}
          source={`From Payments · updated ${updated}`}
        />
        {isStaff ? (
          <div className="card metric" style={{ justifyContent: "center", background: "var(--surface-sunken)" }}>
            <span className="metric-l">
              <Icon name="lock" size="sm" />
              Expenses &amp; cash flow
            </span>
            <span className="metric-c">Visible to Owners and Managers.</span>
          </div>
        ) : (
          <>
            {data.expenses ? (
              <MetricCard
                label="Expenses"
                icon="expenses"
                amountMinor={data.expenses.total_expenses_minor}
                currency={data.expenses.currency_code}
                caption={`${data.expenses.expense_count} ${data.expenses.expense_count === 1 ? "expense" : "expenses"} recorded`}
                source={`From Expenses · updated ${updated}`}
              />
            ) : (
              <UnavailableMetric label="Expenses" />
            )}
            {data.net_cash ? (
              <MetricCard
                label="Net cash flow"
                amountMinor={data.net_cash.net_cash_minor}
                currency={data.net_cash.currency_code}
                caption="Payments collected − expenses"
                source="Calculated · not a profit figure"
                highlight
              />
            ) : (
              <UnavailableMetric label="Net cash flow" />
            )}
          </>
        )}
      </section>
      <p className="t-caption" style={{ marginTop: -12 }}>
        Period {data.freshness.local_start_date === data.freshness.local_end_date ? data.freshness.local_start_date : `${data.freshness.local_start_date} – ${data.freshness.local_end_date}`} · {tz}
      </p>

      <div className="split">
        <div className="l">
          <section className="card" aria-labelledby="inv-h">
            <div className="card-h">
              <h2 className="t-h3" id="inv-h">
                Inventory health
              </h2>
              <Link className="link t-body-sm" href={`${base}/inventory`}>
                View inventory
              </Link>
            </div>
            <div className="card-b" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {tracked !== null && tracked > 0 && (
                <div
                  className="dist"
                  role="img"
                  aria-label={`${tracked} tracked products: ${healthyTotal} healthy, ${lowCount} low stock, ${outCount} out of stock`}
                  style={{ height: 12 }}
                >
                  <span className="seg-healthy" style={{ width: pct(healthyTotal ?? 0) }} />
                  <span className="seg-low" style={{ width: pct(lowCount) }} />
                  <span className="seg-out" style={{ width: pct(outCount) }} />
                </div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(140px, 100%), 1fr))", gap: 12 }}>
                <HealthTile href={`${base}/inventory`} label="Healthy" value={healthyTotal} tone="healthy" />
                <HealthTile href={`${base}/inventory`} label="Low stock" value={lowCount} tone="low" />
                <HealthTile href={`${base}/inventory`} label="Out of stock" value={outCount} tone="out" />
              </div>
              <span className="t-caption">Low stock means {data.inventory.low_stock_threshold} or fewer on hand.</span>
            </div>
          </section>

          <section className="card" aria-labelledby="low-h" style={{ overflow: "hidden" }}>
            <div className="card-h">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <h2 className="t-h3" id="low-h">
                  Needs restocking
                </h2>
                <span className="badge b-neutral">{data.inventory.low_stock_count}</span>
              </div>
              <Link className="link t-body-sm" href={`${base}/inventory`}>
                See all
              </Link>
            </div>
            {items.length === 0 ? (
              <div className="card-b">
                <p className="t-body secondary">Nothing needs restocking right now.</p>
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Code</th>
                      <th className="r">Current stock</th>
                      <th>Status</th>
                      <th className="r">
                        <span className="sr-only">Action</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="stagger">
                    {items.map((item) => (
                      <tr key={item.product_id}>
                        <td>
                          <div className="cell-main">
                            <span className="thumb">{item.product_code.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase() || "—"}</span>
                            <span className="t">{item.product_name}</span>
                          </div>
                        </td>
                        <td className="mono muted">{item.product_code}</td>
                        <td className="r strong">
                          {item.on_hand_quantity} <span className="muted">{item.base_unit}</span>
                        </td>
                        <td>
                          {item.is_out_of_stock ? (
                            <span className="badge b-danger">
                              <Icon name="close" />
                              Out of stock
                            </span>
                          ) : (
                            <span className="badge b-warning">
                              <Icon name="alert" />
                              Low stock
                            </span>
                          )}
                        </td>
                        <td className="r">
                          {!isStaff && (
                            <Link className="btn btn-secondary btn-sm" href={`${base}/inventory`}>
                              Adjust stock
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <div className="r">
          <section className="card" aria-labelledby="ai-h" style={{ overflow: "hidden", position: "relative" }}>
            <div
              style={{ position: "absolute", right: -60, top: -60, width: 200, height: 200, borderRadius: "50%", background: "radial-gradient(circle, var(--brand-tint-strong) 0%, transparent 70%)", pointerEvents: "none" }}
            />
            <div className="card-b" style={{ display: "flex", flexDirection: "column", gap: 16, position: "relative" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="orb pulse" />
                <div>
                  <h2 className="t-h3" id="ai-h">
                    Ask BizPilot about your business
                  </h2>
                  <span className="t-caption">Read-only · answers from your own records</span>
                </div>
              </div>
              <Link href={`${base}/assistant`} className="ig" style={{ textDecoration: "none", height: 42 }} aria-label="Ask BizPilot AI a question">
                <span className="pre plain">
                  <Icon name="ai" />
                </span>
                <span style={{ flex: 1, display: "flex", alignItems: "center", padding: "0 12px", color: "var(--text-muted)", fontSize: 14 }}>Ask a question…</span>
              </Link>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span className="t-label muted">Suggested</span>
                {prompts.map((prompt) => (
                  <Link
                    key={prompt}
                    className="menu-item"
                    href={`${base}/assistant?prompt=${encodeURIComponent(prompt)}`}
                    style={{ border: "1px solid var(--border)", minHeight: 38 }}
                  >
                    {prompt}
                    <Icon name="chevronRight" className="trail" />
                  </Link>
                ))}
              </div>
              <Link className="btn btn-outline btn-block" href={`${base}/assistant`}>
                Open BizPilot AI
                <Icon name="arrowRight" />
              </Link>
            </div>
          </section>

          <section className="card" aria-labelledby="act-h">
            <div className="card-h">
              <h2 className="t-h3" id="act-h">
                Recent activity
              </h2>
              <span className="t-caption">Newest first</span>
            </div>
            {data.recent_activity.length === 0 ? (
              <div className="card-b">
                <p className="t-body secondary">No orders, payments or expenses recorded yet.</p>
              </div>
            ) : (
              <ul className="stagger" style={{ padding: "4px 18px 8px" }}>
                {data.recent_activity.map((a, i) => {
                  const meta = ACTIVITY[a.activity_type];
                  const voided = a.status === "voided";
                  return (
                    <li
                      key={a.id}
                      style={{ display: "flex", gap: 12, alignItems: "center", padding: "10px 0", borderBottom: i < data.recent_activity.length - 1 ? "1px solid var(--border)" : 0 }}
                    >
                      <span className={`tl-dot ${voided ? "bad" : meta.dot}`}>
                        <Icon name={meta.icon} />
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="t-body-sm">
                          <span className="strong">{voided ? meta.label.replace("recorded", "voided") : meta.label}</span> ·{" "}
                          <Link className="link" href={`${base}/${meta.section}`}>
                            {a.reference_code}
                          </Link>
                        </div>
                        <div className="t-caption" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {a.description ? `${a.description} · ` : ""}
                          {formatTime(a.timestamp, tz)}
                        </div>
                      </div>
                      <Money amountMinor={a.amount_minor} currency={a.currency_code} className={`t-body-sm ${voided ? "struck" : "strong"}`} />
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}

function UnavailableMetric({ label }: { label: string }) {
  return (
    <div className="card metric" style={{ justifyContent: "center", background: "var(--surface-sunken)" }}>
      <span className="metric-l">{label}</span>
      <span className="metric-v muted" style={{ fontSize: 18 }}>
        Unavailable
      </span>
      <span className="metric-c">This figure couldn’t be loaded for your role.</span>
    </div>
  );
}

function HealthTile({ href, label, value, tone }: { href: string; label: string; value: number | null; tone: "healthy" | "low" | "out" }) {
  const styles: Record<string, React.CSSProperties> = {
    healthy: { border: "1px solid var(--border)" },
    low: { border: "1px solid var(--warning-border)", background: "var(--warning-bg)" },
    out: { border: "1px solid var(--danger-border)", background: "var(--danger-bg)" },
  };
  const color = tone === "low" ? "var(--warning)" : tone === "out" ? "var(--danger)" : undefined;
  return (
    <Link href={href} style={{ textDecoration: "none", color: "inherit", display: "flex", flexDirection: "column", gap: 2, padding: "10px 12px", borderRadius: 6, ...styles[tone] }}>
      <span className={`t-body-sm ${tone === "healthy" ? "secondary" : ""}`} style={{ display: "flex", alignItems: "center", gap: 6, color }}>
        {tone === "healthy" && <span className="legend-sw seg-healthy" />}
        {tone === "low" && <Icon name="alert" size="sm" />}
        {tone === "out" && <Icon name="close" size="sm" />}
        {label}
      </span>
      <span className="num" style={{ font: "600 22px/30px var(--font)" }}>
        {value === null ? "—" : value}
      </span>
    </Link>
  );
}
