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
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Operating Expenses
          </h1>
          <p className="text-sm text-gray-500">
            Record direct business expenditures, categorize overheads, and maintain trace records.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href={`/workspace/${orgId}`}
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none"
          >
            Dashboard
          </Link>
          {canManageCategories && (
            <button
              onClick={() => setIsCategoryManageOpen(true)}
              className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none"
            >
              Categories
            </button>
          )}
          {canCreate && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="inline-flex items-center rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800 focus:outline-none"
            >
              Record Expense
            </button>
          )}
        </div>
      </div>

      {/* Operational Scope Notice */}
      <div className="rounded-md border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-900 flex items-center justify-between">
        <div>
          <span className="font-semibold">Operational Outflow Tracking:</span> Direct recording of operational overheads and expenditures. Distinguishable from double-entry formal accounting ledgers.
        </div>
      </div>

      {/* Daily Summary Card */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Today's Expenses ({todayStr})
            </span>
            <div className="text-2xl font-bold text-gray-900 mt-0.5">
              {dailyTotalData
                ? formatMoney(dailyTotalData.total_minor, dailyTotalData.currency_code)
                : "Rs. 0.00"}
            </div>
          </div>
          <div className="text-xs text-gray-500">
            {dailyTotalData ? dailyTotalData.expense_count : 0} active expense(s) recorded today
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-gray-600">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-indigo-500 focus:outline-none"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="voided">Voided</option>
            <option value="corrected">Corrected</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-gray-600">Category:</label>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-indigo-500 focus:outline-none"
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

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">Loading expenses...</div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-red-500">
            Failed to load expenses.{" "}
            <button
              onClick={() => refetch()}
              className="text-indigo-600 underline hover:text-indigo-800"
            >
              Retry
            </button>
          </div>
        ) : expenses.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">
            No expenses found matching the current filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
              <thead className="bg-gray-50 text-gray-500 font-medium">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Payee / Memo</th>
                  <th className="px-4 py-3">Method</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {expenses.map((expense) => {
                  const catName = expense.expense_category_id
                    ? categoryMap.get(expense.expense_category_id) || "—"
                    : "—";

                  return (
                    <tr key={expense.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-600">
                        {new Date(expense.occurred_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900">{catName}</td>
                      <td className="px-4 py-3 text-gray-700">
                        <div className="font-medium text-gray-900">
                          {expense.payee || "General Expense"}
                        </div>
                        {expense.description && (
                          <div className="text-gray-500 text-[11px] truncate max-w-xs">
                            {expense.description}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600 capitalize">
                        {formatMethod(expense.payment_method)}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-gray-900">
                        {formatMoney(expense.amount_minor, expense.currency_code)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize ${getStatusBadge(
                            expense.status
                          )}`}
                        >
                          {expense.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          onClick={() => handleOpenDetail(expense)}
                          className="text-indigo-600 hover:text-indigo-800 font-medium"
                        >
                          View
                        </button>
                        {expense.status === "active" && canCorrect && (
                          <button
                            onClick={() => handleOpenCorrect(expense)}
                            className="text-amber-600 hover:text-amber-800 font-medium"
                          >
                            Correct
                          </button>
                        )}
                        {expense.status === "active" && canVoid && (
                          <button
                            onClick={() => handleOpenVoid(expense)}
                            className="text-red-600 hover:text-red-800 font-medium"
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
