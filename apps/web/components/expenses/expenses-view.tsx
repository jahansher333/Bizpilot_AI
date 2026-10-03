"use client";

import React, { useState } from "react";
import Link from "next/link";
import { formatMoney, Expense } from "@/lib/schemas/expenses";
import { useDailyExpenseTotal, useExpenseCategories, useExpenses } from "@/hooks/use-expenses";
import { ExpenseCreateModal } from "@/components/expenses/expense-create-modal";
import { CategoryManageModal } from "@/components/expenses/category-manage-modal";
import { ExpenseDetailModal } from "@/components/expenses/expense-detail-modal";
import { ExpenseVoidModal } from "@/components/expenses/expense-void-modal";
import { ExpenseCorrectModal } from "@/components/expenses/expense-correct-modal";

interface ExpensesViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
}

export function ExpensesView({ orgId, userRole = "owner", token }: ExpensesViewProps) {
  const [statusFilter, setStatusFilter] = useState<string | undefined>("all");
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>("all");
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isCategoryManageOpen, setIsCategoryManageOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isVoidOpen, setIsVoidOpen] = useState(false);
  const [isCorrectOpen, setIsCorrectOpen] = useState(false);

  const normalizedRole = userRole.toLowerCase();
  const isOwner = normalizedRole === "owner";
  const isManager = normalizedRole === "manager";
  const isStaff = normalizedRole === "staff";

  // Permission checks:
  // Staff denied read & write on expenses.
  // Owner and Manager can view, record, correct, and manage categories.
  // Owner only can void expenses.
  const canAccess = isOwner || isManager;
  const canCreate = canAccess;
  const canManageCategories = canAccess;
  const canCorrect = canAccess;
  const canVoid = isOwner;

  const effectiveStatus = statusFilter === "all" ? undefined : statusFilter;
  const effectiveCategory = categoryFilter === "all" ? undefined : categoryFilter;

  const { data: categoriesData } = useExpenseCategories(orgId, undefined, token);
  const categories = categoriesData?.items || [];
  const categoryMap = new Map(categories.map((c) => [c.id, c.name]));

  const { data, isLoading, error, refetch } = useExpenses(
    orgId,
    {
      status: effectiveStatus,
      categoryId: effectiveCategory,
      limit: 100,
      offset: 0,
    },
    token
  );

  const todayStr = new Date().toISOString().split("T")[0];
  const { data: dailyTotalData } = useDailyExpenseTotal(orgId, todayStr, token);

  const expenses = data?.items || [];

  const handleOpenDetail = (expense: Expense) => {
    setSelectedExpense(expense);
    setIsDetailOpen(true);
  };

  const handleOpenVoid = (expense: Expense) => {
    setSelectedExpense(expense);
    setIsVoidOpen(true);
  };

  const handleOpenCorrect = (expense: Expense) => {
    setSelectedExpense(expense);
    setIsCorrectOpen(true);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800 border-green-200";
      case "voided":
        return "bg-red-100 text-red-800 border-red-200";
      case "corrected":
        return "bg-amber-100 text-amber-800 border-amber-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const formatMethod = (m: string) => {
    switch (m) {
      case "cash":
        return "Cash";
      case "bank_transfer":
        return "Bank Transfer";
      case "cheque":
        return "Cheque";
      case "mobile_wallet":
        return "Mobile Wallet";
      case "digital":
        return "Digital";
      default:
        return m;
    }
  };

  if (isStaff) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <h2 className="text-lg font-semibold text-red-800">Access Restricted</h2>
          <p className="mt-2 text-sm text-red-600">
            Staff roles do not have permission to view or manage operating expenses.
            Contact an organization Owner or Manager if you require financial access.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 max-w-[1600px] mx-auto">
      {/* Top Action & Context Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-1 min-w-0">
          <h1 className="font-headline-lg text-2xl lg:text-3xl font-semibold tracking-tight text-on-surface">
            Operating Expenses
          </h1>
          <p className="font-body-md text-sm text-on-surface-variant max-w-3xl">
            Record business expenses with amount, date, category and notes. Totals appear on the dashboard.
          </p>
        </div>

        {/* Action Suite */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            href={`/workspace/${orgId}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3.5 py-2 font-body-sm text-sm font-medium text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[18px] text-outline">dashboard</span>
            <span>Dashboard</span>
          </Link>
          {canManageCategories && (
            <button
              onClick={() => setIsCategoryManageOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3.5 py-2 font-body-sm text-sm font-medium text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
            >
              <span className="material-symbols-outlined text-[18px] text-outline">category</span>
              <span>Categories</span>
            </button>
          )}
          {canCreate && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-body-sm text-sm font-medium text-on-primary shadow-sm hover:bg-primary-container active:scale-[0.99] transition-all"
            >
              <span className="material-symbols-outlined text-[18px]">add_circle</span>
              <span>Record Expense</span>
            </button>
          )}
        </div>
      </div>

      {/* Operational Scope Notice */}
      <div className="rounded-xl border border-secondary/20 bg-surface-container-low p-4 text-xs text-on-surface flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-[16px]">info</span>
          </div>
          <div>
            <span className="font-semibold text-on-surface">Operational Outflow Tracking:</span>{" "}
            <span className="text-on-surface-variant">
              Simple expense records only. This is not an accounting ledger, tax filing or bank reconciliation.
            </span>
          </div>
        </div>
      </div>

      {/* Executive KPI Grid (4 Metrics) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* Metric 1: Today's Expenses */}
        <div className="p-5 rounded-xl bg-surface-container-lowest shadow-xs border border-surface-container-high/60 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
              Today's Expenses ({todayStr})
            </span>
            <div className="w-8 h-8 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[18px]">account_balance_wallet</span>
            </div>
          </div>
          <div className="mt-3 mb-1">
            <div className="font-data-metric text-2xl font-bold text-on-surface tracking-tight">
              {dailyTotalData
                ? formatMoney(dailyTotalData.total_minor, dailyTotalData.currency_code)
                : "Rs. 0.00"}
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-on-surface-variant pt-2 border-t border-surface-container-low">
            <span className="flex items-center gap-1 text-tertiary font-data-badge font-semibold">
              <span className="material-symbols-outlined text-[14px]">trending_up</span>{" "}
              {dailyTotalData ? dailyTotalData.expense_count : 0} active recorded
            </span>
          </div>
        </div>

        {/* Metric 3: Active Cost Centers */}
        <div className="p-5 rounded-xl bg-surface-container-lowest shadow-xs border border-surface-container-high/60 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
              Active Categories
            </span>
            <div className="w-8 h-8 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[18px]">category</span>
            </div>
          </div>
          <div className="mt-3 mb-1">
            <div className="font-data-metric text-2xl font-bold text-on-surface tracking-tight">
              {categories.length}
            </div>
          </div>
        </div>

      </div>

      {/* Filters Console */}
      <div className="bg-surface-container-lowest p-4 rounded-xl shadow-xs border border-surface-container-high/60 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold uppercase font-label-caps text-on-surface-variant tracking-wider">
              Status:
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-1.5 font-body-sm text-xs text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="voided">Voided</option>
              <option value="corrected">Corrected</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold uppercase font-label-caps text-on-surface-variant tracking-wider">
              Category:
            </label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-1.5 font-body-sm text-xs text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
            >
              <option value="all">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="text-xs text-outline font-data-badge">
          Showing {expenses.length} record(s)
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-surface-container-high/60 bg-surface-container-lowest shadow-xs">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">Loading expenses...</div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-error">
            Failed to load expenses.{" "}
            <button
              onClick={() => refetch()}
              className="text-primary underline hover:text-primary-container font-medium ml-1"
            >
              Retry
            </button>
          </div>
        ) : expenses.length === 0 ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">
            No expenses found matching the current filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-surface-container-low text-on-surface-variant font-label-caps text-xs uppercase h-10 select-none border-b border-surface-container-high/60">
                  <th className="px-4 py-3 font-semibold">Date</th>
                  <th className="px-4 py-3 font-semibold">Category</th>
                  <th className="px-4 py-3 font-semibold">Payee / Memo</th>
                  <th className="px-4 py-3 font-semibold">Method</th>
                  <th className="px-4 py-3 text-right font-semibold">Amount</th>
                  <th className="px-4 py-3 text-center font-semibold">Status</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low font-body-md text-sm text-on-surface">
                {expenses.map((expense) => {
                  const catName = expense.expense_category_id
                    ? categoryMap.get(expense.expense_category_id) || "—"
                    : "—";

                  return (
                    <tr key={expense.id} className="hover:bg-surface-container-low/60 transition-colors group">
                      <td className="px-4 py-3.5 text-on-surface-variant font-data-cell">
                        {new Date(expense.occurred_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3.5 font-medium text-on-surface">
                        <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface text-xs font-medium">
                          {catName}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-on-surface">
                        <div className="font-semibold text-on-surface">
                          {expense.payee || "General Expense"}
                        </div>
                        {expense.description && (
                          <div className="text-on-surface-variant text-[11px] truncate max-w-xs">
                            {expense.description}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-on-surface-variant capitalize">
                        {formatMethod(expense.payment_method)}
                      </td>
                      <td className="px-4 py-3.5 text-right font-semibold text-on-surface font-data-cell">
                        {formatMoney(expense.amount_minor, expense.currency_code)}
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-data-badge text-xs font-semibold capitalize ${
                            expense.status === "active"
                              ? "bg-tertiary-container/15 text-tertiary"
                              : expense.status === "voided"
                              ? "bg-error-container text-on-error-container"
                              : "bg-secondary-fixed text-on-secondary-fixed"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              expense.status === "active"
                                ? "bg-tertiary"
                                : expense.status === "voided"
                                ? "bg-error"
                                : "bg-secondary"
                            }`}
                          ></span>
                          {expense.status}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right space-x-2">
                        <button
                          onClick={() => handleOpenDetail(expense)}
                          className="font-medium text-primary hover:text-primary-container transition-colors"
                        >
                          View
                        </button>
                        {expense.status === "active" && canCorrect && (
                          <button
                            onClick={() => handleOpenCorrect(expense)}
                            className="font-medium text-secondary hover:text-secondary-container transition-colors"
                          >
                            Correct
                          </button>
                        )}
                        {expense.status === "active" && canVoid && (
                          <button
                            onClick={() => handleOpenVoid(expense)}
                            className="font-medium text-error hover:text-on-error-container transition-colors"
                          >
                            Void
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <ExpenseCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        orgId={orgId}
        token={token}
      />

      <CategoryManageModal
        isOpen={isCategoryManageOpen}
        onClose={() => setIsCategoryManageOpen(false)}
        orgId={orgId}
        token={token}
      />

      <ExpenseDetailModal
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        expense={selectedExpense}
        categories={categories}
        canVoid={canVoid}
        canCorrect={canCorrect}
        onOpenVoid={handleOpenVoid}
        onOpenCorrect={handleOpenCorrect}
      />

      <ExpenseVoidModal
        isOpen={isVoidOpen}
        onClose={() => setIsVoidOpen(false)}
        expense={selectedExpense}
        orgId={orgId}
        token={token}
      />

      <ExpenseCorrectModal
        isOpen={isCorrectOpen}
        onClose={() => setIsCorrectOpen(false)}
        expense={selectedExpense}
        categories={categories}
        orgId={orgId}
        token={token}
      />
    </div>
  );
}
