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
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "payment":
        return "bg-green-100 text-green-800 border-green-200";
      case "expense":
        return "bg-purple-100 text-purple-800 border-purple-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header and Controls */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Operational Dashboard
          </h1>
          <p className="text-sm text-gray-500">
            Deterministic business operations, daily collections, operating outflows, and stock levels.
          </p>
        </div>

        {/* Period Selector */}
        <div className="flex flex-wrap items-center gap-2">
          {(["today", "yesterday", "this_week", "this_month", "custom"] as const).map(
            (p) => (
              <button
                key={p}
                type="button"
                onClick={() => handlePeriodChange(p)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                  selectedPeriod === p
                    ? "bg-emerald-700 text-white shadow-sm"
                    : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
                }`}
              >
                {p.replace("_", " ")}
              </button>
            )
          )}
        </div>
      </div>

      {/* AI Business Copilot Spotlight */}
      <div className="rounded-xl border border-emerald-200 bg-gradient-to-r from-emerald-50 via-teal-50 to-white p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800 border border-emerald-300">
                AI Copilot
              </span>
              <h2 className="text-base font-semibold text-gray-950">
                Operational Business Copilot
              </h2>
            </div>
            <p className="text-xs text-gray-600 max-w-2xl">
              Ask questions about sales trends, low stock alerts, customer balances, or operating expenses. Every answer is grounded directly in verified database records.
            </p>
          </div>

          <Link
            href={`/workspace/${orgId}/assistant`}
            className="inline-flex items-center justify-center rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-800 transition shrink-0"
          >
            Consult AI Copilot →
          </Link>
        </div>

        {/* Quick Question Chips */}
        <div className="mt-3 flex flex-wrap gap-2 pt-2 border-t border-emerald-100/60">
          <span className="text-[11px] font-medium text-emerald-900 py-1">Quick insights:</span>
          {[
            "How are sales doing today?",
            "Which products are low on stock?",
            "What is our customer balance status?",
            ...(userRole !== "staff" ? ["Summarize operational expenses"] : []),
          ].map((prompt) => (
            <Link
              key={prompt}
              href={`/workspace/${orgId}/assistant?prompt=${encodeURIComponent(prompt)}`}
              className="rounded-md border border-emerald-200 bg-white px-2.5 py-1 text-xs text-emerald-900 hover:bg-emerald-50 hover:border-emerald-300 transition shadow-xs"
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
          className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs"
        >
          <div className="flex items-center gap-1.5">
            <label className="font-medium text-gray-700">From:</label>
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="rounded border border-gray-300 bg-white px-2 py-1 text-xs focus:border-indigo-500 focus:outline-none"
              required
            />
          </div>
          <div className="flex items-center gap-1.5">
            <label className="font-medium text-gray-700">To:</label>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="rounded border border-gray-300 bg-white px-2 py-1 text-xs focus:border-indigo-500 focus:outline-none"
              required
            />
          </div>
          <button
            type="submit"
            className="rounded bg-indigo-600 px-3 py-1 font-medium text-white hover:bg-indigo-700"
          >
            Apply Range
          </button>
        </form>
      )}

      {/* Freshness Banner */}
      {data?.freshness && (
        <div className="flex flex-wrap items-center justify-between rounded-md border border-gray-100 bg-white px-4 py-2 text-xs text-gray-500 shadow-sm">
          <div>
            Period: <span className="font-medium text-gray-900">{data.freshness.local_start_date}</span>{" "}
            to <span className="font-medium text-gray-900">{data.freshness.local_end_date}</span>{" "}
            ({data.freshness.timezone})
          </div>
          <div>
            Freshness:{" "}
            <span className="font-mono text-gray-700">
              {new Date(data.freshness.generated_at).toLocaleTimeString()}
            </span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      {isLoading ? (
        <div className="p-12 text-center text-sm text-gray-500">Loading dashboard metrics...</div>
      ) : error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-sm text-red-600">
          <p className="font-semibold">Failed to load dashboard metrics.</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-2 text-xs font-medium text-indigo-600 underline hover:text-indigo-800"
          >
            Retry
          </button>
        </div>
      ) : data ? (
        <>
          {/* Key Metric Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Sales Orders */}
            <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
                  Sales Orders
                </span>
                <span className="text-[10px] font-mono text-gray-400">PostgreSQL</span>
              </div>
              <div className="mt-2 text-2xl font-bold text-gray-900">
                {formatMoney(data.sales.total_sales_minor, data.sales.currency_code)}
              </div>
              <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
                <span>{data.sales.order_count} active order(s)</span>
                <Link
                  href={`/workspace/${orgId}/orders`}
                  className="font-medium text-emerald-700 hover:text-emerald-900"
                >
                  View Orders →
                </Link>
              </div>
            </div>

            {/* Collections */}
            <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
                  Payments Collected
                </span>
                <span className="text-[10px] font-mono text-gray-400">PostgreSQL</span>
              </div>
              <div className="mt-2 text-2xl font-bold text-gray-900">
                {formatMoney(data.payments.total_collected_minor, data.payments.currency_code)}
              </div>
              <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
                <span>{data.payments.payment_count} receipt(s)</span>
                <Link
                  href={`/workspace/${orgId}/payments`}
                  className="font-medium text-emerald-700 hover:text-emerald-900"
                >
                  View Receipts →
                </Link>
              </div>
            </div>

            {/* Operating Expenses */}
            <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
                  Operating Expenses
                </span>
                <span className="text-[10px] font-mono text-gray-400">PostgreSQL</span>
              </div>
              {data.expenses !== null && data.expenses !== undefined ? (
                <>
                  <div className="mt-2 text-2xl font-bold text-gray-900">
                    {formatMoney(data.expenses.total_expenses_minor, data.expenses.currency_code)}
                  </div>
                  <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
                    <span>{data.expenses.expense_count} expense record(s)</span>
                    <Link
                      href={`/workspace/${orgId}/expenses`}
                      className="font-medium text-emerald-700 hover:text-emerald-900"
                    >
                      View Expenses →
                    </Link>
                  </div>
                </>
              ) : (
                <>
                  <div className="mt-2 text-sm font-semibold text-gray-400">Restricted</div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    Staff role is not authorized to view operating expenses.
                  </p>
                </>
              )}
            </div>

            {/* Net Operational Cash */}
            <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
                Net Cash Flow
              </span>
              {data.net_cash !== null && data.net_cash !== undefined ? (
                <>
                  <div
                    className={`mt-2 text-2xl font-bold ${
                      data.net_cash.net_cash_minor >= 0 ? "text-gray-900" : "text-red-600"
                    }`}
                  >
                    {formatMoney(data.net_cash.net_cash_minor, data.net_cash.currency_code)}
                  </div>
                  <p className="mt-1 text-[10px] text-gray-400">
                    Collections minus expenses. (Not profit/tax).
                  </p>
                </>
              ) : (
                <>
                  <div className="mt-2 text-sm font-semibold text-gray-400">Unavailable</div>
                  <p className="mt-1 text-[11px] text-gray-400">
                    Requires expense access.
                  </p>
                </>
              )}
            </div>
          </div>

          {/* Low Stock Alert Section */}
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h2 className="text-sm font-semibold text-gray-900">
                  Stock Alerts ({data.inventory.low_stock_count})
                </h2>
                <p className="text-xs text-gray-500">
                  Products with stock on hand at or below threshold ({data.inventory.low_stock_threshold} units).
                </p>
              </div>
              <Link
                href={`/workspace/${orgId}/inventory`}
                className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
              >
                Go to Inventory →
              </Link>
            </div>

            {data.inventory.items.length === 0 ? (
              <div className="py-6 text-center text-xs text-gray-500">
                All inventory products are currently above the alert threshold.
              </div>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
                  <thead className="text-gray-500 font-medium">
                    <tr>
                      <th className="py-2 pr-4">Code</th>
                      <th className="py-2 pr-4">Product Name</th>
                      <th className="py-2 pr-4 text-center">Unit</th>
                      <th className="py-2 pr-4 text-right">On Hand</th>
                      <th className="py-2 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.inventory.items.map((item) => (
                      <tr key={item.product_id} className="hover:bg-gray-50">
                        <td className="py-2.5 pr-4 font-mono font-medium text-gray-800">
                          {item.product_code}
                        </td>
                        <td className="py-2.5 pr-4 text-gray-900">{item.product_name}</td>
                        <td className="py-2.5 pr-4 text-center text-gray-500 capitalize">
                          {item.base_unit}
                        </td>
                        <td className="py-2.5 pr-4 text-right font-semibold text-gray-900">
                          {item.on_hand_quantity}
                        </td>
                        <td className="py-2.5 text-center">
                          {item.is_out_of_stock ? (
                            <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800 border border-red-200">
                              Out of Stock
                            </span>
                          ) : (
                            <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800 border border-amber-200">
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

          {/* Recent Operational Activity Feed */}
          <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-900 border-b pb-3">
              Recent Operational Activity
            </h2>

            {data.recent_activity.length === 0 ? (
              <div className="py-6 text-center text-xs text-gray-500">
                No recent activity recorded for this organization yet.
              </div>
            ) : (
              <div className="mt-3 divide-y divide-gray-100">
                {data.recent_activity.map((act) => (
                  <div
                    key={`${act.activity_type}-${act.id}`}
                    className="flex flex-col sm:flex-row sm:items-center sm:justify-between py-2.5 gap-2"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize ${formatActivityBadge(
                          act.activity_type
                        )}`}
                      >
                        {act.activity_type}
                      </span>
                      <div>
                        <span className="font-medium text-gray-900 text-xs">
                          {act.reference_code}
                        </span>
                        {act.description && (
                          <span className="ml-2 text-xs text-gray-500">
                            — {act.description}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 text-xs">
                      <span className="font-semibold text-gray-900">
                        {formatMoney(act.amount_minor, act.currency_code)}
                      </span>
                      <span className="text-gray-400 text-[11px]">
                        {new Date(act.timestamp).toLocaleDateString()} {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
