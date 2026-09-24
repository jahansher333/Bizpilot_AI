"use client";

import React, { useState } from "react";
import { Product } from "@/lib/schemas/catalog";
import { useRecordOpeningStock } from "@/hooks/use-inventory";

interface OpeningStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  products: Product[];
  token?: string;
  preselectedProductId?: string;
}

export function OpeningStockModal({
  isOpen,
  onClose,
  orgId,
  products,
  token,
  preselectedProductId,
}: OpeningStockModalProps) {
  const [productId, setProductId] = useState(preselectedProductId || products[0]?.id || "");
  const [quantity, setQuantity] = useState<string>("10");
  const [reason, setReason] = useState<string>("Initial opening stock");
  const [error, setError] = useState<string | null>(null);

  const mutation = useRecordOpeningStock(orgId, token);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const parsedQty = parseInt(quantity, 10);
    if (isNaN(parsedQty) || parsedQty <= 0) {
      setError("Opening quantity must be a positive integer");
      return;
    }

    if (!productId) {
      setError("Please select a product");
      return;
    }

    try {
      await mutation.mutateAsync({
        product_id: productId,
        quantity: parsedQty,
        reason: reason.trim() || undefined,
      });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record opening stock";
      setError(msg);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="opening-stock-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 id="opening-stock-title" className="text-xl font-bold text-gray-900">
          Record Opening Stock
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Initialize stock balance for a product. Opening stock can only be recorded once per product.
        </p>

        {error && (
          <div role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
          <div>
            <label htmlFor="product-select" className="block text-sm font-medium text-gray-700">
              Product
            </label>
            <select
              id="product-select"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              disabled={!!preselectedProductId}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="quantity-input" className="block text-sm font-medium text-gray-700">
              Opening Quantity
            </label>
            <input
              id="quantity-input"
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
              required
            />
          </div>

          <div>
            <label htmlFor="reason-input" className="block text-sm font-medium text-gray-700">
              Reason / Notes
            </label>
            <input
              id="reason-input"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
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
              disabled={mutation.isPending}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none disabled:opacity-50"
            >
              {mutation.isPending ? "Recording..." : "Save Opening Stock"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
