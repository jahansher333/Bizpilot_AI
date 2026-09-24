"use client";

import React, { useState } from "react";
import { Order, orderVoidSchema } from "@/lib/schemas/orders";
import { useVoidOrder } from "@/hooks/use-orders";

interface OrderVoidModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: Order | null;
  orgId: string;
  token?: string;
}

export function OrderVoidModal({
  isOpen,
  onClose,
  order,
  orgId,
  token,
}: OrderVoidModalProps) {
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const voidMutation = useVoidOrder(orgId, token);

  if (!isOpen || !order) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const parseResult = orderVoidSchema.safeParse({ reason });
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0].message);
      return;
    }

    try {
      const idempotencyKey = `web-void-${order.id}-${Date.now()}`;
      await voidMutation.mutateAsync({
        orderId: order.id,
        payload: parseResult.data,
        idempotencyKey,
      });
      onClose();
    } catch (err: any) {
      setFormError(err.message || "Failed to void order");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 className="text-lg font-semibold text-red-600">
            Void Order {order.order_number}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500 focus:outline-none"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="py-4 space-y-4">
          <div className="rounded-md bg-red-50 p-3 text-xs text-red-800 border border-red-200 space-y-1">
            <p className="font-semibold">Owner-Only Critical Action:</p>
            <p>
              Voiding this order will permanently change its status to <strong>voided</strong> and restore all deducted product quantities to warehouse inventory balances.
            </p>
          </div>

          {formError && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200">
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
              placeholder="e.g. Customer cancelled order before dispatch / duplicate entry"
              className="block w-full rounded-md border border-gray-300 p-2 text-sm focus:border-red-500 focus:outline-none"
              required
            />
          </div>

          <div className="border-t pt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={voidMutation.isPending}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-700 focus:outline-none disabled:opacity-50"
            >
              {voidMutation.isPending ? "Voiding Order..." : "Confirm Void Order"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
