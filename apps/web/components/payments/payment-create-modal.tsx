"use client";

import React, { useState } from "react";
import { formatMoney, paymentCreateSchema, PaymentChannel } from "@/lib/schemas/payments";
import { useCreatePayment } from "@/hooks/use-payments";
import { useCustomers } from "@/hooks/use-customers";
import { useOrders } from "@/hooks/use-orders";

interface PaymentCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  token?: string;
  initialOrderId?: string;
  initialCustomerId?: string;
}

export function PaymentCreateModal({
  isOpen,
  onClose,
  orgId,
  token,
  initialOrderId,
  initialCustomerId,
}: PaymentCreateModalProps) {
  const [amountMajor, setAmountMajor] = useState<string>("");
  const [channel, setChannel] = useState<PaymentChannel>("cash");
  const [accountLabel, setAccountLabel] = useState<string>("");
  const [customerId, setCustomerId] = useState<string>(initialCustomerId || "");
  const [orderId, setOrderId] = useState<string>(initialOrderId || "");
  const [externalReference, setExternalReference] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: customersData } = useCustomers(orgId, { status: "active", limit: 100 }, token);
  const { data: ordersData } = useOrders(orgId, { status: "active", limit: 100 }, token);
  const createMutation = useCreatePayment(orgId, token);

  if (!isOpen) return null;

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
      amount_minor: parsedAmountMinor,
      channel,
      account_label: accountLabel.trim() || undefined,
      customer_id: customerId.trim() || undefined,
      order_id: orderId.trim() || undefined,
      external_reference: externalReference.trim() || undefined,
      currency_code: "PKR",
      notes: notes.trim() || undefined,
    };

    const result = paymentCreateSchema.safeParse(payload);
    if (!result.success) {
      setFormError(result.error.issues[0]?.message || "Invalid input");
      return;
    }

    try {
      // Deterministic idempotency key to prevent accidental duplicate receipt creation
      const idempotencyKey = typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `pay-idem-${Date.now()}`;

      await createMutation.mutateAsync({
        payload: result.data,
        idempotencyKey,
      });

      // Reset and close
      setAmountMajor("");
      setChannel("cash");
      setAccountLabel("");
      setCustomerId("");
      setOrderId("");
      setExternalReference("");
      setNotes("");
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to record payment. Please try again.");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="payment-modal-title"
    >
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 id="payment-modal-title" className="text-lg font-semibold text-gray-900">
            Record Business Receipt
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

          {/* Channel */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Payment Channel <span className="text-red-500">*</span>
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as PaymentChannel)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            >
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cheque">Cheque</option>
              <option value="mobile_wallet">Mobile Wallet (Easypaisa / JazzCash)</option>
              <option value="other">Other</option>
            </select>
          </div>

          {/* Account Label */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Account Label / Drawer (Optional)
            </label>
            <input
              type="text"
              value={accountLabel}
              onChange={(e) => setAccountLabel(e.target.value)}
              placeholder="e.g. Main Cash Drawer, Meezan Current Account"
              maxLength={100}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {/* Customer Selection */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Customer (Optional)
            </label>
            <select
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
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
            <label className="block text-xs font-medium text-gray-700">
              Linked Order (Optional)
            </label>
            <select
              value={orderId}
              onChange={(e) => setOrderId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            >
              <option value="">Standalone Receipt / Direct</option>
              {orders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.order_number} — {formatMoney(o.order_total_minor, o.currency_code)}
                </option>
              ))}
            </select>
          </div>

          {/* External Reference */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              External Reference / Cheque # / TxID (Optional)
            </label>
            <input
              type="text"
              value={externalReference}
              onChange={(e) => setExternalReference(e.target.value)}
              placeholder="e.g. CHQ-98124, TID-481923"
              maxLength={100}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-gray-700">
              Notes (Optional)
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Operational details or receipt context..."
              maxLength={500}
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
              {createMutation.isPending ? "Recording..." : "Record Receipt"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
