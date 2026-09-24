"use client";

import React from "react";
import { Product } from "@/lib/schemas/catalog";
import { useInventoryMovements } from "@/hooks/use-inventory";

interface MovementHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  product: Product;
  token?: string;
}

export function MovementHistoryModal({
  isOpen,
  onClose,
  orgId,
  product,
  token,
}: MovementHistoryModalProps) {
  const { data, isLoading, error } = useInventoryMovements(
    orgId,
    { productId: product.id, limit: 50 },
    token
  );

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="movement-history-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between border-b pb-3">
          <div>
            <h2 id="movement-history-title" className="text-xl font-bold text-gray-900">
              Movement History
            </h2>
            <p className="text-sm text-gray-500">
              {product.name} ({product.code})
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 focus:outline-none text-2xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto mt-4">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-gray-500">Loading movements...</p>
          ) : error ? (
            <p className="py-8 text-center text-sm text-red-600">Failed to load movement history</p>
          ) : !data || data.items.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-500">No stock movements recorded yet</p>
          ) : (
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">Date/Time</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">Type</th>
                  <th className="px-3 py-2 text-right font-medium text-gray-500">Delta</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {data.items.map((m) => {
                  const isPositive = m.quantity_delta > 0;
                  return (
                    <tr key={m.id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                        {new Date(m.created_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <span className="inline-flex rounded-full bg-gray-100 px-2 text-xs font-semibold leading-5 text-gray-800 uppercase">
                          {m.movement_type}
                        </span>
                      </td>
                      <td
                        className={`px-3 py-2 text-right font-semibold whitespace-nowrap ${
                          isPositive ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {isPositive ? `+${m.quantity_delta}` : m.quantity_delta}
                      </td>
                      <td className="px-3 py-2 text-gray-600">{m.reason || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="mt-4 pt-3 border-t flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
