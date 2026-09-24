"use client";

import React, { useState } from "react";
import { Product } from "@/lib/schemas/catalog";
import { useRecordAdjustment, useRecordCorrection } from "@/hooks/use-inventory";

interface AdjustmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  product: Product;
  currentOnHand: number;
  mode: "adjustment" | "correction";
  token?: string;
}

export function AdjustmentModal({
  isOpen,
  onClose,
  orgId,
  product,
  currentOnHand,
  mode,
  token,
}: AdjustmentModalProps) {
  const [deltaStr, setDeltaStr] = useState<string>("5");
  const [reason, setReason] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const adjustMutation = useRecordAdjustment(orgId, token);
  const correctMutation = useRecordCorrection(orgId, token);

  const isPending = adjustMutation.isPending || correctMutation.isPending;

  if (!isOpen) return null;

  const isAdjustment = mode === "adjustment";
  const title = isAdjustment ? "Adjust Stock" : "Record Inventory Correction";
  const subtitle = isAdjustment
    ? "Record physical stock adjustments (+/- delta). Reason is mandatory."
    : "Record verified count variance correction. Reason is mandatory.";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const delta = parseInt(deltaStr, 10);
    if (isNaN(delta) || delta === 0) {
      setError("Quantity delta must be a non-zero integer");
      return;
    }

    if (reason.trim().length < 3) {
      setError("Reason is required (minimum 3 characters)");
      return;
    }

    if (currentOnHand + delta < 0) {
      setError(`Insufficient stock: current balance is ${currentOnHand}, resulting balance cannot be negative`);
      return;
    }

    try {
      if (isAdjustment) {
        await adjustMutation.mutateAsync({
          input: {
            product_id: product.id,
            quantity_delta: delta,
            reason: reason.trim(),
          },
        });
      } else {
        await correctMutation.mutateAsync({
          input: {
            product_id: product.id,
            quantity_delta: delta,
            reason: reason.trim(),
          },
        });
      }
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record transaction";
      setError(msg);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="adjustment-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 id="adjustment-modal-title" className="text-xl font-bold text-gray-900">
          {title}
        </h2>
        <p className="mt-1 text-sm text-gray-500">{subtitle}</p>

        <div className="mt-3 rounded-md bg-gray-50 p-3 text-xs text-gray-600">
          <p>
            <span className="font-semibold">Product:</span> {product.name} ({product.code})
          </p>
          <p>
            <span className="font-semibold">Current On-Hand:</span> {currentOnHand} {product.base_unit}
          </p>
        </div>

        {error && (
          <div role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
          <div>
            <label htmlFor="delta-input" className="block text-sm font-medium text-gray-700">
              Quantity Delta (+ to increase, - to decrease)
            </label>
            <input
              id="delta-input"
              type="number"
              value={deltaStr}
              onChange={(e) => setDeltaStr(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
              required
            />
          </div>

          <div>
            <label htmlFor="adj-reason-input" className="block text-sm font-medium text-gray-700">
              Reason (minimum 3 characters)
            </label>
            <input
              id="adj-reason-input"
              type="text"
              value={reason}
              placeholder="e.g., Storeroom recount, Damaged packaging"
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
              required
            />
          </div>

          <div className="mt-6 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none disabled:opacity-50"
            >
              {isPending ? "Submitting..." : isAdjustment ? "Save Adjustment" : "Save Correction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
