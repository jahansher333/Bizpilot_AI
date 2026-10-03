"use client";

import React, { useState } from "react";
import Link from "next/link";
import { formatMoney, DashboardPeriod } from "@/lib/schemas/dashboard";
import { useDashboard } from "@/hooks/use-dashboard";

interface DashboardViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
}

export function DashboardView({ orgId, userRole = "owner", token }: DashboardViewProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<DashboardPeriod>("today");
  const [customStart, setCustomStart] = useState<string>("");
  const [customEnd, setCustomEnd] = useState<string>("");
  const [appliedCustomStart, setAppliedCustomStart] = useState<string | undefined>();
  const [appliedCustomEnd, setAppliedCustomEnd] = useState<string | undefined>();

  const queryParams = {
    period: selectedPeriod,
    startDate: selectedPeriod === "custom" ? appliedCustomStart : undefined,
    endDate: selectedPeriod === "custom" ? appliedCustomEnd : undefined,
  };

  const { data, isLoading, error, refetch } = useDashboard(orgId, queryParams, token);

  const handlePeriodChange = (period: DashboardPeriod) => {
    setSelectedPeriod(period);
  };

  const handleApplyCustom = (e: React.FormEvent) => {
    e.preventDefault();
    if (customStart && customEnd) {
      setAppliedCustomStart(customStart);
      setAppliedCustomEnd(customEnd);
    }
  };

  const formatActivityBadge = (type: string) => {
    switch (type) {
      case "order":
        return "bg-primary-fixed text-primary border-primary-fixed-dim";
      case "payment":
        return "bg-tertiary-fixed text-on-tertiary-fixed border-tertiary-fixed-dim";
      case "expense":
        return "bg-secondary-fixed text-on-secondary-fixed border-secondary-fixed-dim";
      default:
        return "bg-surface-container-high text-on-surface-variant border-outline-variant";
    }
  };

  return (
    <div className="space-y-6 p-4 sm:p-6 lg:p-8 bg-surface min-h-screen">
      {/* Top Salutation & Controls Band (Stitch Executive Precision Header) */}
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-outline font-data-badge text-data-badge uppercase tracking-wider text-[11px]">
            <span>Enterprise Realtime Telemetry</span>
            <span>•</span>
            <span className="text-tertiary font-semibold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-tertiary animate-pulse inline-block" />
              Sync Stable
            </span>
          </div>
          <h1 className="font-display-lg text-2xl sm:text-3xl font-bold tracking-tight text-on-surface">
            Operational Dashboard
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
            Deterministic business operations, daily collections, operating outflows, and stock levels.
          </p>
        </div>

        {/* Period Selector (Stitch Segmented Control) */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center p-1 bg-surface-container-high rounded-xl shadow-xs">
            {(["today", "yesterday", "this_week", "this_month", "custom"] as const).map(
              (p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => handlePeriodChange(p)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${
                    selectedPeriod === p
                      ? "bg-surface-container-lowest text-primary shadow-xs"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  {p.replace("_", " ")}
                </button>
              )
            )}
          </div>

          <Link
            href={`/workspace/${orgId}/orders`}
            className="flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-primary-container text-on-primary text-xs font-semibold hover:bg-primary transition-all shadow-xs active:scale-[0.99]"
          >
            <span>+ Record Sale / POS</span>
          </Link>
        </div>
      </div>

      {/* AI Business Copilot Spotlight (Stitch Gradient Ribbon Widget) */}
      <div className="rounded-2xl border border-outline-variant/60 bg-surface-container-lowest p-5 shadow-xs relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary-container via-primary to-secondary-container" />
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-md bg-primary-fixed px-2 py-0.5 font-data-badge text-data-badge font-semibold text-primary">
                AI Copilot
              </span>
              <h2 className="text-base font-semibold text-on-surface">
                Operational Business Copilot
              </h2>
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
              Ask about sales, low stock, customer balances, payments received or expenses. Answers come only from records saved in this workspace, and the assistant never changes them.
            </p>
          </div>

          <Link
            href={`/workspace/${orgId}/assistant`}
            className="inline-flex items-center justify-center rounded-xl bg-primary px-4 py-2 font-body-sm text-body-sm font-semibold text-on-primary shadow-xs hover:bg-primary-container transition-all shrink-0 active:scale-[0.99]"
          >
            Consult AI Copilot →
          </Link>
        </div>

        {/* Quick Question Chips */}
        <div className="mt-3 flex flex-wrap gap-2 pt-3 border-t border-surface-container-high/60">
          <span className="text-[11px] font-medium text-on-surface-variant py-1">Quick insights:</span>
          {[
            "How are sales doing today?",
            "Which products are low on stock?",
            "What is our customer balance status?",
            ...(userRole !== "staff" ? ["Summarize operational expenses"] : []),
          ].map((prompt) => (
            <Link
              key={prompt}
              href={`/workspace/${orgId}/assistant?prompt=${encodeURIComponent(prompt)}`}
              className="rounded-lg border border-outline-variant/60 bg-surface-container-low px-2.5 py-1 text-xs text-on-surface hover:bg-surface-container hover:border-primary/40 transition-colors shadow-xs"
            >
              {prompt}
            </Link>
          ))}
        </div>
      </div>

      {/* Custom Date Picker (when custom is active) */}
      {selectedPeriod === "custom" && (
        <form
          onSubmit={handleApplyCustom}
          className="flex flex-wrap items-center gap-3 rounded-xl border border-outline-variant/60 bg-surface-container-lowest p-3 text-xs shadow-xs"
        >
          <div className="flex items-center gap-1.5">
            <label className="font-medium text-on-surface">From:</label>
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="rounded-lg border border-outline-variant/60 bg-surface-container-low px-2 py-1 text-xs focus:border-primary focus:outline-none"
              required
            />
          </div>
          <div className="flex items-center gap-1.5">
            <label className="font-medium text-on-surface">To:</label>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="rounded-lg border border-outline-variant/60 bg-surface-container-low px-2 py-1 text-xs focus:border-primary focus:outline-none"
              required
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-primary px-3 py-1 font-semibold text-on-primary hover:bg-primary-container shadow-xs"
          >
            Apply Range
          </button>
        </form>
      )}

      {/* Freshness Banner */}
      {data?.freshness && (
        <div className="flex flex-wrap items-center justify-between rounded-xl border border-surface-container-high bg-surface-container-lowest px-4 py-2 text-xs text-on-surface-variant shadow-xs">
          <div>
            Period: <span className="font-semibold text-on-surface font-mono">{data.freshness.local_start_date}</span>{" "}
            to <span className="font-semibold text-on-surface font-mono">{data.freshness.local_end_date}</span>{" "}
            ({data.freshness.timezone})
          </div>
          <div>
            Freshness:{" "}
            <span className="font-mono text-on-surface font-semibold">
              {new Date(data.freshness.generated_at).toLocaleTimeString()}
            </span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      {isLoading ? (
        <div className="p-12 text-center text-sm text-outline">Loading dashboard metrics...</div>
      ) : error ? (
        <div className="rounded-2xl border border-error/30 bg-error-container/20 p-6 text-center text-sm text-error">
          <p className="font-semibold">Failed to load dashboard metrics.</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-2 text-xs font-semibold text-primary underline hover:text-primary-container"
          >
            Retry
          </button>
        </div>
      ) : data ? (
        <>
          {/* Key Metric Cards (4 Stitch High-Precision Metric Cards) */}
          <div className="grid grid-cols-1 gap-space-md sm:grid-cols-2 lg:grid-cols-4">
            {/* Card 1: Sales Orders */}
            <div className="p-space-lg rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high/80 flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary to-primary-container opacity-90" />
              <div>
                <div className="flex items-center justify-between mb-space-xs">
                  <span className="font-label-caps text-label-caps uppercase text-outline text-[11px]">
                    Sales Orders
                  </span>
                  <span className="font-data-badge text-data-badge px-2 py-0.5 rounded bg-surface-container-high text-primary font-medium">
                    PostgreSQL
                  </span>
                </div>
                <div className="mt-2 font-data-metric text-2xl font-bold text-on-surface tracking-tight">
                  {formatMoney(data.sales.total_sales_minor, data.sales.currency_code)}
                </div>
                <div className="mt-1 flex items-center justify-between text-xs text-on-surface-variant font-body-sm">
                  <span>{data.sales.order_count} active order(s)</span>
                  <Link
                    href={`/workspace/${orgId}/orders`}
                    className="font-medium text-primary hover:text-primary-container"
                  >
                    View Orders →
                  </Link>
                </div>
              </div>
            </div>

            {/* Card 2: Collections */}
            <div className="p-space-lg rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high/80 flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-secondary-container to-secondary opacity-90" />
              <div>
                <div className="flex items-center justify-between mb-space-xs">
                  <span className="font-label-caps text-label-caps uppercase text-outline text-[11px]">
                    Payments Collected
                  </span>
                  <span className="font-data-badge text-data-badge px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed font-medium">
                    PostgreSQL
                  </span>
                </div>
                <div className="mt-2 font-data-metric text-2xl font-bold text-on-surface tracking-tight">
                  {formatMoney(data.payments.total_collected_minor, data.payments.currency_code)}
                </div>
                <div className="mt-1 flex items-center justify-between text-xs text-on-surface-variant font-body-sm">
                  <span>{data.payments.payment_count} receipt(s)</span>
                  <Link
                    href={`/workspace/${orgId}/payments`}
                    className="font-medium text-secondary hover:text-on-secondary-fixed-variant"
                  >
                    View Receipts →
                  </Link>
                </div>
              </div>
            </div>

            {/* Card 3: Operating Expenses */}
            <div className="p-space-lg rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high/80 flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-outline to-surface-dim opacity-90" />
              <div>
                <div className="flex items-center justify-between mb-space-xs">
                  <span className="font-label-caps text-label-caps uppercase text-outline text-[11px]">
                    Operating Expenses
                  </span>
                  <span className="font-data-badge text-data-badge px-2 py-0.5 rounded bg-surface-container-high text-outline font-medium">
                    PostgreSQL
                  </span>
                </div>
                {data.expenses !== null && data.expenses !== undefined ? (
                  <>
                    <div className="mt-2 font-data-metric text-2xl font-bold text-on-surface tracking-tight">
                      {formatMoney(data.expenses.total_expenses_minor, data.expenses.currency_code)}
                    </div>
                    <div className="mt-1 flex items-center justify-between text-xs text-on-surface-variant font-body-sm">
                      <span>{data.expenses.expense_count} expense record(s)</span>
                      <Link
                        href={`/workspace/${orgId}/expenses`}
                        className="font-medium text-primary hover:text-primary-container"
                      >
                        View Expenses →
                      </Link>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="mt-2 text-sm font-semibold text-outline">Restricted</div>
                    <p className="mt-1 text-[11px] text-outline">
                      Staff role is not authorized to view operating expenses.
                    </p>
                  </>
                )}
              </div>
            </div>

            {/* Card 4: Net Operational Cash */}
            <div className="p-space-lg rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high/80 flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-tertiary to-tertiary-fixed-dim opacity-90" />
              <div>
                <div className="flex items-center justify-between mb-space-xs">
                  <span className="font-label-caps text-label-caps uppercase text-outline text-[11px]">
                    Net Cash Flow
                  </span>
                  <span className="font-data-badge text-data-badge px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-medium">
                    Recorded
                  </span>
                </div>
                {data.net_cash !== null && data.net_cash !== undefined ? (
                  <>
                    <div
                      className={`mt-2 font-data-metric text-2xl font-bold tracking-tight ${
                        data.net_cash.net_cash_minor >= 0 ? "text-on-surface" : "text-error"
                      }`}
                    >
                      {formatMoney(data.net_cash.net_cash_minor, data.net_cash.currency_code)}
                    </div>
                    <p className="mt-1 text-[10px] text-outline">
                      Collections minus expenses. (Not profit/tax).
                    </p>
                  </>
                ) : (
                  <>
                    <div className="mt-2 text-sm font-semibold text-outline">Unavailable</div>
                    <p className="mt-1 text-[11px] text-outline">
                      Requires expense access.
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Low Stock Alert Section (Stitch Critical Inventory Tile) */}
          <div className="rounded-2xl border border-surface-container-high/80 bg-surface-container-lowest p-space-lg shadow-xs">
            <div className="flex items-center justify-between border-b border-surface-container-high pb-3">
              <div>
                <h2 className="font-headline-sm text-headline-sm font-semibold text-on-surface">
                  Stock Alerts ({data.inventory.low_stock_count})
                </h2>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Products with stock on hand at or below threshold ({data.inventory.low_stock_threshold} units).
                </p>
              </div>
              <Link
                href={`/workspace/${orgId}/inventory`}
                className="text-xs font-semibold text-primary hover:text-primary-container transition-colors"
              >
                Go to Inventory →
              </Link>
            </div>

            {data.inventory.items.length === 0 ? (
              <div className="py-6 text-center text-xs text-outline">
                All inventory products are currently above the alert threshold.
              </div>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full divide-y divide-surface-container-high text-left text-xs">
                  <thead className="text-outline font-label-caps uppercase text-[11px]">
                    <tr>
                      <th className="py-2.5 pr-4">Code</th>
                      <th className="py-2.5 pr-4">Product Name</th>
                      <th className="py-2.5 pr-4 text-center">Unit</th>
                      <th className="py-2.5 pr-4 text-right">On Hand</th>
                      <th className="py-2.5 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-container-low font-body-sm">
                    {data.inventory.items.map((item) => (
                      <tr key={item.product_id} className="hover:bg-surface-container-low/60 transition-colors">
                        <td className="py-3 pr-4 font-mono font-medium text-primary font-data-cell">
                          {item.product_code}
                        </td>
                        <td className="py-3 pr-4 text-on-surface font-medium">{item.product_name}</td>
                        <td className="py-3 pr-4 text-center text-on-surface-variant capitalize">
                          {item.base_unit}
                        </td>
                        <td className="py-3 pr-4 text-right font-semibold text-on-surface font-mono">
                          {item.on_hand_quantity}
                        </td>
                        <td className="py-3 text-center">
                          {item.is_out_of_stock ? (
                            <span className="inline-flex rounded-full bg-error-container px-2 py-0.5 font-data-badge text-[10px] font-semibold text-on-error-container border border-error/20">
                              Out of Stock
                            </span>
                          ) : (
                            <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 font-data-badge text-[10px] font-semibold text-amber-800 border border-amber-200">
                              Low Stock
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent Operational Activity Feed (Stitch Ledger Stream) */}
          <div className="rounded-2xl border border-surface-container-high/80 bg-surface-container-lowest p-space-lg shadow-xs">
            <h2 className="font-headline-sm text-headline-sm font-semibold text-on-surface border-b border-surface-container-high pb-3">
              Recent Operational Activity
            </h2>

            {data.recent_activity.length === 0 ? (
              <div className="py-6 text-center text-xs text-outline">
                No recent activity recorded for this organization yet.
              </div>
            ) : (
              <div className="mt-3 divide-y divide-surface-container-high/50">
                {data.recent_activity.map((act) => (
                  <div
                    key={`${act.activity_type}-${act.id}`}
                    className="flex flex-col sm:flex-row sm:items-center sm:justify-between py-3 gap-2 hover:bg-surface-container-low/40 px-2 rounded-xl transition-colors"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 font-data-badge text-[10px] font-semibold capitalize ${formatActivityBadge(
                          act.activity_type
                        )}`}
                      >
                        {act.activity_type}
                      </span>
                      <div>
                        <span className="font-semibold text-on-surface text-xs font-mono">
                          {act.reference_code}
                        </span>
                        {act.description && (
                          <span className="ml-2 text-xs text-on-surface-variant">
                            — {act.description}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 text-xs">
                      <span className="font-semibold text-on-surface font-mono text-sm">
                        {formatMoney(act.amount_minor, act.currency_code)}
                      </span>
                      <span className="text-outline font-data-cell text-[11px]">
                        {new Date(act.timestamp).toLocaleDateString()} {new Date(act.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
