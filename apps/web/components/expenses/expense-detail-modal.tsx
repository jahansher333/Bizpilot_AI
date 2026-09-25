"use client";

import React from "react";
import { formatMoney, Expense, ExpenseCategory } from "@/lib/schemas/expenses";

interface ExpenseDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  expense: Expense | null;
  categories?: ExpenseCategory[];
  onOpenVoid?: (expense: Expense) => void;
  onOpenCorrect?: (expense: Expense) => void;
  canVoid?: boolean;
  canCorrect?: boolean;
}

export function ExpenseDetailModal({
  isOpen,
  onClose,
  expense,
  categories = [],
  onOpenVoid,
  onOpenCorrect,
  canVoid = false,
  canCorrect = false,
}: ExpenseDetailModalProps) {
  if (!isOpen || !expense) return null;

  const categoryMap = new Map(categories.map((c) => [c.id, c.name]));
  const categoryName = expense.expense_category_id
    ? categoryMap.get(expense.expense_category_id) || "Uncategorized"
    : "Uncategorized";

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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="expense-detail-modal-title"
    >
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <div>
            <h2 id="expense-detail-modal-title" className="text-lg font-semibold text-gray-900">
              Expense Details
            </h2>
            <p className="text-xs text-gray-500 font-mono">{expense.id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 space-y-4 text-sm">
          {/* Status & Amount */}
          <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3 border border-gray-100">
            <div>
              <span className="text-xs text-gray-500">Recorded Amount</span>
              <p className="text-xl font-bold text-gray-900">
                {formatMoney(expense.amount_minor, expense.currency_code)}
              </p>
            </div>
            <span
              className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${getStatusBadge(
                expense.status
              )}`}
            >
              {expense.status}
            </span>
          </div>

          {/* Info Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs font-medium text-gray-500">Category</span>
              <p className="font-medium text-gray-900">{categoryName}</p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">Payment Method</span>
              <p className="font-medium text-gray-900 capitalize">
                {formatMethod(expense.payment_method)}
              </p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">Payee</span>
              <p className="text-gray-900">{expense.payee || "—"}</p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">Date</span>
              <p className="text-gray-900 text-xs">
                {new Date(expense.occurred_at).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Description */}
          {expense.description && (
            <div>
              <span className="text-xs font-medium text-gray-500">Description / Memo</span>
              <p className="mt-1 rounded bg-gray-50 p-2 text-xs text-gray-700 whitespace-pre-wrap">
                {expense.description}
              </p>
            </div>
          )}

          {/* Replacement / Void Status Details */}
          {expense.status === "voided" && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-800">
              <span className="font-semibold">Voided Record:</span> This expense was voided
              {expense.voided_at && ` on ${new Date(expense.voided_at).toLocaleString()}`} and is
              excluded from active operating totals.
            </div>
          )}

          {expense.status === "corrected" && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 space-y-1">
              <p className="font-semibold">Corrected Record:</p>
              <p>This expense was replaced by a corrective expense record.</p>
              {expense.replaced_by_expense_id && (
                <p className="font-mono text-xs">
                  Replacement ID: {expense.replaced_by_expense_id}
                </p>
              )}
            </div>
          )}

          {expense.corrects_expense_id && (
            <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800 space-y-1">
              <p className="font-semibold">Corrective Adjustment:</p>
              <p>This expense replaces a previously corrected expense record.</p>
              <p className="font-mono text-xs">Previous ID: {expense.corrects_expense_id}</p>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="mt-6 flex justify-between border-t pt-4">
          <div className="flex gap-2">
            {expense.status === "active" && canVoid && onOpenVoid && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenVoid(expense);
                }}
                className="rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50 focus:outline-none"
              >
                Void Expense
              </button>
            )}
            {expense.status === "active" && canCorrect && onOpenCorrect && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenCorrect(expense);
                }}
                className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-50 focus:outline-none"
              >
                Correct Expense
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
