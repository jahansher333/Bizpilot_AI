"use client";

import React, { useState, useEffect } from "react";
import {
  formatMoney,
  Expense,
  ExpenseCategory,
  ExpensePaymentMethod,
  expenseCorrectSchema,
  toMinorUnits,
} from "@/lib/schemas/expenses";
import { useCorrectExpense } from "@/hooks/use-expenses";

interface ExpenseCorrectModalProps {
  isOpen: boolean;
  onClose: () => void;
  expense: Expense | null;
  categories?: ExpenseCategory[];
  orgId: string;
  token?: string;
}

export function ExpenseCorrectModal({
  isOpen,
  onClose,
  expense,
  categories = [],
  orgId,
  token,
}: ExpenseCorrectModalProps) {
  const [reason, setReason] = useState("");
  const [amountMajor, setAmountMajor] = useState<string>("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [paymentMethod, setPaymentMethod] = useState<ExpensePaymentMethod>("cash");
  const [payee, setPayee] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  const correctMutation = useCorrectExpense(orgId, token);

  useEffect(() => {
    if (expense) {
      setReason("");
      setAmountMajor((expense.amount_minor / 100).toFixed(2));
      setCategoryId(expense.expense_category_id || "");
      setPaymentMethod(expense.payment_method);
      setPayee(expense.payee || "");
      setDescription(expense.description || "");
      setFormError(null);
    }
  }, [expense]);

  if (!isOpen || !expense) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const val = parseFloat(amountMajor);
    if (isNaN(val) || val <= 0) {
      setFormError("Amount must be greater than zero");
      return;
    }

    const payload = {
      reason: reason.trim(),
      amount_minor: toMinorUnits(val),
      expense_category_id: categoryId.trim() || undefined,
      payment_method: paymentMethod,
      payee: payee.trim() || undefined,
      description: description.trim() || undefined,
      currency_code: expense.currency_code || "PKR",
    };

    const parseResult = expenseCorrectSchema.safeParse(payload);
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0]?.message || "Invalid correction input");
      return;
    }

    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `correct-exp-${expense.id}-${Date.now()}`;

      await correctMutation.mutateAsync({
        expenseId: expense.id,
        payload: parseResult.data,
        idempotencyKey,
      });
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to correct expense");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="expense-correct-modal-title"
    >
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 id="expense-correct-modal-title" className="text-lg font-semibold text-amber-600">
            Correct Expense
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
          <div className="rounded-md bg-amber-50 p-3 text-xs text-amber-800 border border-amber-200 space-y-1">
            <p className="font-semibold">Correction Notice:</p>
            <p>
              This will mark the current expense record ({formatMoney(expense.amount_minor, expense.currency_code)})
              as <strong>corrected</strong> and create a linked replacement record with your adjustments.
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
              Reason for Correction (Required)
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Adjusted invoice amount, updated category"
              className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-amber-500 focus:outline-none"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Corrected Amount ({expense.currency_code}) *
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={amountMajor}
                onChange={(e) => setAmountMajor(e.target.value)}
                className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-amber-500 focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Category</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-amber-500 focus:outline-none"
              >
                <option value="">(None / General)</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Payment Method</label>
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value as ExpensePaymentMethod)}
                className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-amber-500 focus:outline-none"
              >
                <option value="cash">Cash</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="cheque">Cheque</option>
                <option value="mobile_wallet">Mobile Wallet</option>
                <option value="digital">Digital</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Payee / Vendor</label>
              <input
                type="text"
                value={payee}
                onChange={(e) => setPayee(e.target.value)}
                placeholder="Vendor or recipient name"
                className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-amber-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Description / Memo</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Operational reason for expense..."
              className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-amber-500 focus:outline-none"
            />
          </div>

          <div className="border-t pt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={correctMutation.isPending}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={correctMutation.isPending}
              className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50 focus:outline-none"
            >
              {correctMutation.isPending ? "Applying..." : "Save Correction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
