"use client";

import React, { useState } from "react";
import { formatMoney, Payment, paymentVoidSchema } from "@/lib/schemas/payments";
import { useVoidPayment } from "@/hooks/use-payments";

interface PaymentVoidModalProps {
  isOpen: boolean;
  onClose: () => void;
  payment: Payment | null;
  orgId: string;
  token?: string;
}

export function PaymentVoidModal({
  isOpen,
  onClose,
  payment,
  orgId,
  token,
}: PaymentVoidModalProps) {
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const voidMutation = useVoidPayment(orgId, token);

  if (!isOpen || !payment) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const parseResult = paymentVoidSchema.safeParse({ reason });
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0]?.message || "Invalid reason");
      return;
    }

    try {
      const idempotencyKey = typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `void-${payment.id}-${Date.now()}`;

      await voidMutation.mutateAsync({
        paymentId: payment.id,
        payload: parseResult.data,
        idempotencyKey,
      });
      setReason("");
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to void payment");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="void-modal-title"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 id="void-modal-title" className="text-lg font-semibold text-red-600">
            Void Payment {payment.payment_number}
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
              Voiding this payment permanently marks it as <strong>voided</strong> ({formatMoney(payment.amount_minor, payment.currency_code)}). It will be excluded from all daily and dashboard receipt totals.
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
              placeholder="e.g. Dishonored cheque, duplicate cash receipt entry"
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
              disabled={voidMutation.isPending || reason.trim().length < 3}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none disabled:bg-gray-400"
            >
              {voidMutation.isPending ? "Voiding..." : "Confirm Void"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
