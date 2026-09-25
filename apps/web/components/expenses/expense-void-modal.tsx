"use client";

import React, { useState } from "react";
import { formatMoney, Expense, expenseVoidSchema } from "@/lib/schemas/expenses";
import { useVoidExpense } from "@/hooks/use-expenses";

interface ExpenseVoidModalProps {
  isOpen: boolean;
  onClose: () => void;
  expense: Expense | null;
  orgId: string;
  token?: string;
}

export function ExpenseVoidModal({
  isOpen,
  onClose,
  expense,
  orgId,
  token,
}: ExpenseVoidModalProps) {
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const voidMutation = useVoidExpense(orgId, token);

  if (!isOpen || !expense) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const parseResult = expenseVoidSchema.safeParse({ reason });
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0]?.message || "Invalid reason");
      return;
    }

    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `void-exp-${expense.id}-${Date.now()}`;

      await voidMutation.mutateAsync({
        expenseId: expense.id,
        payload: parseResult.data,
        idempotencyKey,
      });
      setReason("");
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to void expense");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="expense-void-modal-title"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 id="expense-void-modal-title" className="text-lg font-semibold text-red-600">
            Void Expense
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500 focus:outline-none"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="py-4 space-y-4">
          <div className="rounded-md bg-red-50 p-3 text-xs text-red-800 border border-red-200 space-y-1">
            <p className="font-semibold">Owner-Only Critical Action:</p>
            <p>
              Voiding permanently removes this expense (
              {formatMoney(expense.amount_minor, expense.currency_code)}) from active business
              totals.
            </p>
          </div>

          {formError && (
            <div
              role="alert"
              className="rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200"
            >
              {formError}
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Reason for Voiding (Required)
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Duplicate expense entry, incorrect vendor voucher"
              className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-red-500 focus:outline-none"
              required
            />
          </div>

          <div className="border-t pt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={voidMutation.isPending}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={voidMutation.isPending}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 focus:outline-none"
            >
              {voidMutation.isPending ? "Voiding..." : "Confirm Void"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
