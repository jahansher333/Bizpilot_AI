"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useExpenseCategories, useExpenses } from "@/hooks/use-expenses";
import { useDashboard } from "@/hooks/use-dashboard";
import { EXPENSE_METHOD_LABEL, Expense } from "@/lib/schemas/expenses";
import { Icon } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { EmptyState, ErrorState, RestrictedState, Skeleton } from "@/components/ui/states";
import { RecordStatusBadge, thisMonthRange } from "@/components/finance/record-meta";
import { orderWhen } from "@/components/orders/order-meta";
import { ExpenseRecordModal } from "@/components/expenses/expense-record-modal";
import { ExpenseDetailModal } from "@/components/expenses/expense-detail-modal";
import { ExpenseCorrectModal } from "@/components/expenses/expense-correct-modal";
import { ExpenseVoidModal } from "@/components/expenses/expense-void-modal";
import { ExpenseCategoriesPanel } from "@/components/expenses/expense-categories-panel";

interface ExpensesViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
}

const PAGE_SIZE = 50;
const METRIC = { font: "600 24px/32px var(--font)" } as const;

/** Design canvas "23–25 · Expenses". Owner/Manager only; Staff get a restricted state. Void: Owner. */
export function ExpensesView({ orgId, userRole = "staff", token }: ExpensesViewProps) {
  const canSee = userRole === "owner" || userRole === "manager";
  const canVoid = userRole === "owner";
  const base = `/workspace/${orgId}`;

  const [categoryId, setCategoryId] = useState<string>("all");
  const [thisMonth, setThisMonth] = useState(true);
  const [page, setPage] = useState(0);
  const [recordOpen, setRecordOpen] = useState(false);
  const [detail, setDetail] = useState<Expense | null>(null);
  const [correcting, setCorrecting] = useState<Expense | null>(null);
  const [voiding, setVoiding] = useState<Expense | null>(null);

  const range = thisMonthRange();
  // Disabled for Staff: the backend would answer 403 and the page shows a restricted state instead.
  const queryOrg = canSee ? orgId : "";
  const { data, isLoading, error, refetch } = useExpenses(
    queryOrg,
    { categoryId: categoryId === "all" ? undefined : categoryId, startDate: thisMonth ? range.start : undefined, endDate: thisMonth ? range.end : undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
    token
  );
  const { data: categories } = useExpenseCategories(queryOrg, undefined, token);
  const today = useDashboard(queryOrg, { period: "today" }, token);
  const month = useDashboard(queryOrg, { period: "this_month" }, token);
  const categoryNames = useMemo(() => new Map((categories?.items ?? []).map((c) => [c.id, c.name])), [categories]);
  const categoryName = (id?: string | null) => (id ? (categoryNames.get(id) ?? "Category") : "Uncategorised");
  const activeCategories = (categories?.items ?? []).filter((c) => c.status === "active");

  if (!canSee) {
    return (
      <div className="main page-in">
        <RestrictedState
          title="Expenses are visible to Owners and Managers"
          description="Your role (Staff) doesn’t include business expenses. If you need to record one, ask an Owner or Manager of this business."
          action={
            <Link className="btn btn-primary" href={base}>
              Back to dashboard
            </Link>
          }
        />
      </div>
    );
  }

  const expenses = data?.items ?? [];
  const filtered = categoryId !== "all";

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <h1 className="t-h1">Expenses</h1>
            <span className="badge b-neutral square">
              <Icon name="lock" />
              Owners &amp; Managers
            </span>
          </div>
          <p className="t-body secondary">What it costs to run the business.</p>
        </div>
        <div className="ph-a">
          <button type="button" className="btn btn-primary" onClick={() => setRecordOpen(true)}>
            <Icon name="plus" />
            Record expense
          </button>
        </div>
      </div>

      <section className="sum-grid" aria-label="Expense summary">
        <div className="card metric">
          <span className="metric-l">Today</span>
          {today.data?.expenses ? <Money amountMinor={today.data.expenses.total_expenses_minor} currency={today.data.expenses.currency_code} style={METRIC} /> : <span className="num" style={METRIC}>—</span>}
          <span className="metric-c">{today.data?.expenses ? `${today.data.expenses.expense_count} ${today.data.expenses.expense_count === 1 ? "expense" : "expenses"}` : "Voided excluded"}</span>
        </div>
        <div className="card metric">
          <span className="metric-l">This month</span>
          {month.data?.expenses ? <Money amountMinor={month.data.expenses.total_expenses_minor} currency={month.data.expenses.currency_code} style={METRIC} /> : <span className="num" style={METRIC}>—</span>}
          <span className="metric-c">Voided and corrected excluded</span>
        </div>
        <div className="card metric">
          <span className="metric-l">Expense count</span>
          <span className="num" style={METRIC}>
            {month.data?.expenses?.expense_count ?? "—"}
          </span>
          <span className="metric-c">This month</span>
        </div>
      </section>

      <div className="split">
        <div className="l">
          <div className="toolbar">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} role="group" aria-label="Category">
              <button
                type="button"
                className="chip"
                aria-pressed={categoryId === "all"}
                onClick={() => {
                  setCategoryId("all");
                  setPage(0);
                }}
              >
                All categories
              </button>
              {activeCategories.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="chip"
                  aria-pressed={categoryId === c.id}
                  onClick={() => {
                    setCategoryId(c.id);
                    setPage(0);
                  }}
                >
                  {c.name}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="chip filter"
              aria-pressed={thisMonth}
              onClick={() => {
                setThisMonth((v) => !v);
                setPage(0);
              }}
            >
              <Icon name="calendar" size="sm" />
              This month
            </button>
          </div>

          {error && <ErrorState title="Couldn’t load expenses" message="Nothing was lost — check your connection, then try again." onRetry={() => void refetch()} />}

          {isLoading && (
            <div className="tbl-wrap" aria-busy="true" aria-label="Loading expenses" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
              {[1, 2, 3].map((i) => (
                <div key={i} style={{ display: "flex", gap: 12 }}>
                  <Skeleton width={200} height={12} />
                  <Skeleton width={90} height={12} />
                </div>
              ))}
            </div>
          )}

          {data && expenses.length === 0 && (
            <div className="card">
              {filtered || thisMonth ? (
                <EmptyState icon="expenses" title={thisMonth ? "No expenses this month" : "No expenses in this category"} description={thisMonth ? "Turn off “This month” to see older expenses." : undefined} />
              ) : (
                <EmptyState
                  icon="expenses"
                  title="No expenses yet"
                  description="Record rent, bills and other running costs to see your real net cash."
                  action={
                    <button type="button" className="btn btn-primary" onClick={() => setRecordOpen(true)}>
                      Record expense
                    </button>
                  }
                />
              )}
            </div>
          )}

          {expenses.length > 0 && (
            <div className="tbl-wrap fade-in">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Expense</th>
                    <th>Category</th>
                    <th className="r">Amount</th>
                    <th>Paid by</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th className="r">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {expenses.map((e) => {
                    const active = e.status === "active";
                    const label = e.description || e.payee || "Expense";
                    return (
                      <tr key={e.id} className={active ? "" : "is-void"}>
                        <td>
                          <button type="button" className={`link${active ? " strong" : " struck"}`} style={{ background: "none", border: 0, padding: 0, cursor: "pointer", textAlign: "left", font: "inherit" }} onClick={() => setDetail(e)}>
                            {label}
                          </button>
                          {e.payee && e.description && <div className="cell-sub">{e.payee}</div>}
                        </td>
                        <td>{categoryName(e.expense_category_id)}</td>
                        <td className="r">
                          <Money amountMinor={e.amount_minor} currency={e.currency_code} className={active ? "strong" : "struck"} />
                        </td>
                        <td>{EXPENSE_METHOD_LABEL[e.payment_method] ?? e.payment_method}</td>
                        <td className="muted">{orderWhen(e.occurred_at)}</td>
                        <td>
                          <RecordStatusBadge status={e.status} />
                        </td>
                        <td className="r">
                          {active && (
                            <span className="row-actions">
                              <button type="button" className="btn btn-ghost btn-sm" aria-label={`Correct ${label}`} onClick={() => setCorrecting(e)}>
                                Correct
                              </button>
                              {canVoid && (
                                <button type="button" className="btn btn-ghost btn-sm" aria-label={`Void ${label}`} onClick={() => setVoiding(e)}>
                                  Void
                                </button>
                              )}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {data && data.total > PAGE_SIZE && (
                <div className="pager">
                  <span>
                    Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, data.total)} of {data.total}
                  </span>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button type="button" className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage((x) => x - 1)}>
                      Previous
                    </button>
                    <button type="button" className="btn btn-secondary btn-sm" disabled={(page + 1) * PAGE_SIZE >= data.total} onClick={() => setPage((x) => x + 1)}>
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          <p className="t-caption">Simple expense records only — not an accounting ledger, tax filing or bank reconciliation.</p>
        </div>
        <div className="r">
          <ExpenseCategoriesPanel orgId={orgId} token={token} />
        </div>
      </div>

      <ExpenseRecordModal isOpen={recordOpen} onClose={() => setRecordOpen(false)} orgId={orgId} token={token} />
      <ExpenseDetailModal
        expense={correcting || voiding ? null : detail}
        onClose={() => setDetail(null)}
        orgId={orgId}
        token={token}
        categoryName={categoryName}
        canCorrect
        canVoid={canVoid}
        onCorrect={(e) => setCorrecting(e)}
        onVoid={(e) => setVoiding(e)}
        onOpenExpense={(e) => setDetail(e)}
      />
      <ExpenseCorrectModal isOpen={!!correcting} onClose={() => setCorrecting(null)} expense={correcting} orgId={orgId} token={token} onCorrected={() => setDetail(null)} />
      <ExpenseVoidModal
        isOpen={!!voiding}
        onClose={() => {
          setVoiding(null);
          setDetail(null);
        }}
        expense={voiding}
        orgId={orgId}
        token={token}
      />
    </div>
  );
}
