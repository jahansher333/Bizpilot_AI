"use client";

import React, { useState } from "react";
import {
  ExpensePaymentMethod,
  expenseCreateSchema,
  formatMoney,
} from "@/lib/schemas/expenses";
import { useCreateExpense, useExpenseCategories } from "@/hooks/use-expenses";

interface ExpenseCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  token?: string;
}

export function ExpenseCreateModal({
  isOpen,
  onClose,
  orgId,
  token,
}: ExpenseCreateModalProps) {
  const [amountMajor, setAmountMajor] = useState<string>("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [paymentMethod, setPaymentMethod] = useState<ExpensePaymentMethod>("cash");
  const [payee, setPayee] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: categoriesData } = useExpenseCategories(orgId, "active", token);
  const createMutation = useCreateExpense(orgId, token);

  if (!isOpen) return null;

  const categories = categoriesData?.items || [];

  const parsedAmountMinor = (() => {
    const val = parseFloat(amountMajor);
    return isNaN(val) ? 0 : Math.round(val * 100);
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const payload = {
      amount_minor: parsedAmountMinor,
      expense_category_id: categoryId.trim() || undefined,
      payment_method: paymentMethod,
      payee: payee.trim() || undefined,
      description: description.trim() || undefined,
      currency_code: "PKR",
    };

    const parseResult = expenseCreateSchema.safeParse(payload);
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0]?.message || "Invalid expense input");
      return;
    }

    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `exp-idem-${Date.now()}`;

      await createMutation.mutateAsync({
        payload: parseResult.data,
        idempotencyKey,
      });

      setAmountMajor("");
      setCategoryId("");
      setPaymentMethod("cash");
      setPayee("");
      setDescription("");
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to record expense");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="expense-modal-title"
    >
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 id="expense-modal-title" className="text-lg font-semibold text-gray-900">
            Record Operating Expense
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {formError && (
          <div
            role="alert"
            className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200"
          >
            {formError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {/* Amount */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Amount (PKR) <span className="text-red-500">*</span>
            </label>
            <div className="mt-1 relative rounded-md shadow-sm">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                <span className="text-gray-500 sm:text-sm">Rs.</span>
              </div>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={amountMajor}
                onChange={(e) => setAmountMajor(e.target.value)}
                placeholder="0.00"
                className="block w-full rounded-md border border-gray-300 pl-10 pr-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>
            {parsedAmountMinor > 0 && (
              <p className="mt-1 text-xs text-gray-500">
                Minor units: {parsedAmountMinor} ({formatMoney(parsedAmountMinor)})
              </p>
            )}
          </div>

          {/* Category */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Category (Optional)
            </label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            >
              <option value="">Uncategorized Expense</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Payment Method */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Payment Method <span className="text-red-500">*</span>
            </label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as ExpensePaymentMethod)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            >
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cheque">Cheque</option>
              <option value="mobile_wallet">Mobile Wallet</option>
              <option value="digital">Digital / Online</option>
              <option value="other">Other</option>
            </select>
          </div>

          {/* Payee */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Payee / Vendor (Optional)
            </label>
            <input
              type="text"
              value={payee}
              onChange={(e) => setPayee(e.target.value)}
              placeholder="e.g. K-Electric, Sui Southern Gas, Landlord"
              maxLength={255}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Description / Notes (Optional)
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Operational context, bill numbers, invoice references..."
              maxLength={1000}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              disabled={createMutation.isPending}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || parsedAmountMinor <= 0}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 focus:outline-none disabled:bg-gray-400"
            >
              {createMutation.isPending ? "Recording..." : "Record Expense"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
