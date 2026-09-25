"use client";

import React, { useState, useEffect } from "react";
import { formatMoney, Payment, PaymentChannel, paymentCorrectSchema } from "@/lib/schemas/payments";
import { useCorrectPayment } from "@/hooks/use-payments";
import { useCustomers } from "@/hooks/use-customers";
import { useOrders } from "@/hooks/use-orders";

interface PaymentCorrectModalProps {
  isOpen: boolean;
  onClose: () => void;
  payment: Payment | null;
  orgId: string;
  token?: string;
}

export function PaymentCorrectModal({
  isOpen,
  onClose,
  payment,
  orgId,
  token,
}: PaymentCorrectModalProps) {
  const [reason, setReason] = useState("");
  const [amountMajor, setAmountMajor] = useState<string>("");
  const [channel, setChannel] = useState<PaymentChannel>("cash");
  const [accountLabel, setAccountLabel] = useState<string>("");
  const [customerId, setCustomerId] = useState<string>("");
  const [orderId, setOrderId] = useState<string>("");
  const [externalReference, setExternalReference] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: customersData } = useCustomers(orgId, { status: "active", limit: 100 }, token);
  const { data: ordersData } = useOrders(orgId, { status: "active", limit: 100 }, token);
  const correctMutation = useCorrectPayment(orgId, token);

  useEffect(() => {
    if (payment) {
      setReason("");
      setAmountMajor((payment.amount_minor / 100).toFixed(2));
      setChannel(payment.channel);
      setAccountLabel(payment.account_label || "");
      setCustomerId(payment.customer_id || "");
      setOrderId(payment.order_id || "");
      setExternalReference(payment.external_reference || "");
      setNotes(payment.notes || "");
      setFormError(null);
    }
  }, [payment]);

  if (!isOpen || !payment) return null;

  const customers = customersData?.items || [];
  const orders = ordersData?.items || [];

  const parsedAmountMinor = (() => {
    const val = parseFloat(amountMajor);
    return isNaN(val) ? 0 : Math.round(val * 100);
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const payload = {
      reason: reason.trim(),
      amount_minor: parsedAmountMinor,
      channel,
      account_label: accountLabel.trim() || undefined,
      customer_id: customerId.trim() || undefined,
      order_id: orderId.trim() || undefined,
      external_reference: externalReference.trim() || undefined,
      currency_code: payment.currency_code || "PKR",
      notes: notes.trim() || undefined,
    };

    const parseResult = paymentCorrectSchema.safeParse(payload);
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0]?.message || "Invalid correction input");
      return;
    }

    try {
      const idempotencyKey = typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `correct-${payment.id}-${Date.now()}`;

      await correctMutation.mutateAsync({
        paymentId: payment.id,
        payload: parseResult.data,
        idempotencyKey,
      });
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to correct payment");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="correct-modal-title"
    >
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <div>
            <h2 id="correct-modal-title" className="text-lg font-semibold text-amber-700">
              Correct Payment {payment.payment_number}
            </h2>
            <p className="text-xs text-gray-500">
              Prior Amount: {formatMoney(payment.amount_minor, payment.currency_code)}
            </p>
          </div>
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
            <p className="font-semibold">Managerial Correction Workflow:</p>
            <p>
              This operation marks the original receipt as <strong>corrected</strong> and atomically creates a new replacement receipt linked to it. The active totals will immediately reflect the replacement amount.
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

          {/* Reason */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Reason for Correction (Required) <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Correcting mistyped cash amount / wrong customer selected"
              className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-amber-500 focus:outline-none"
              required
            />
          </div>

          {/* Replacement Amount */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Replacement Amount (PKR) <span className="text-red-500">*</span>
            </label>
            <div className="relative rounded-md shadow-sm">
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
                className="block w-full rounded-md border border-gray-300 pl-10 pr-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
              />
            </div>
            {parsedAmountMinor > 0 && (
              <p className="mt-1 text-xs text-gray-500">
                Minor units: {parsedAmountMinor} ({formatMoney(parsedAmountMinor)})
              </p>
            )}
          </div>

          {/* Channel */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Replacement Channel <span className="text-red-500">*</span>
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as PaymentChannel)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
            >
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cheque">Cheque</option>
              <option value="mobile_wallet">Mobile Wallet</option>
              <option value="other">Other</option>
            </select>
          </div>

          {/* Account Label */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Account Label / Drawer
            </label>
            <input
              type="text"
              value={accountLabel}
              onChange={(e) => setAccountLabel(e.target.value)}
              maxLength={100}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
            />
          </div>

          {/* Customer Selection */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Customer
            </label>
            <select
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
            >
              <option value="">Walk-in / No Customer Assigned</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.phone})
                </option>
              ))}
            </select>
          </div>

          {/* Order Selection */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Linked Order
            </label>
            <select
              value={orderId}
              onChange={(e) => setOrderId(e.target.value)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
            >
              <option value="">Standalone Receipt</option>
              {orders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.order_number} — {formatMoney(o.order_total_minor, o.currency_code)}
                </option>
              ))}
            </select>
          </div>

          {/* External Reference */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              External Reference
            </label>
            <input
              type="text"
              value={externalReference}
              onChange={(e) => setExternalReference(e.target.value)}
              maxLength={100}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Notes
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
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
              disabled={correctMutation.isPending || reason.trim().length < 3 || parsedAmountMinor <= 0}
              className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 focus:outline-none disabled:bg-gray-400"
            >
              {correctMutation.isPending ? "Applying Correction..." : "Apply Correction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
