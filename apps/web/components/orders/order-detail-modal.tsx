"use client";

import React, { useEffect } from "react";
import { formatMoney, Order } from "@/lib/schemas/orders";

interface OrderDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: Order | null;
}

export function OrderDetailModal({ isOpen, onClose, order }: OrderDetailModalProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
      }
    }
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, onClose]);

  if (!isOpen || !order) return null;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800 border-green-200";
      case "voided":
        return "bg-red-100 text-red-800 border-red-200";
      case "corrected":
        return "bg-amber-100 text-amber-800 border-amber-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="order-detail-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-3">
            <h2 id="order-detail-modal-title" className="text-lg font-semibold text-gray-900">
              Order {order.order_number}
            </h2>
            <span
              className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${getStatusBadge(
                order.status
              )}`}
            >
              {order.status}
            </span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close order details"
            className="text-gray-400 hover:text-gray-500 focus:outline-none"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {/* Status notices */}
          {order.status === "voided" && (
            <div className="rounded-md bg-red-50 p-3 text-xs text-red-700 border border-red-200">
              <span className="font-semibold">Voided Order:</span> This order was voided. Inventory stock deductions were reversed to warehouse balance.
            </div>
          )}

          {order.status === "corrected" && (
            <div className="rounded-md bg-amber-50 p-3 text-xs text-amber-800 border border-amber-200">
              <span className="font-semibold">Corrected Order:</span> This order was replaced by order ID: {order.replaced_by_order_id}.
            </div>
          )}

          {order.corrects_order_id && (
            <div className="rounded-md bg-blue-50 p-3 text-xs text-blue-800 border border-blue-200">
              <span className="font-semibold">Replacement Order:</span> This order corrects and replaces previous order ID: {order.corrects_order_id}.
            </div>
          )}

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-4 text-xs bg-gray-50 p-3 rounded-md border">
            <div>
              <span className="text-gray-500 block">Ordered At:</span>
              <span className="font-medium text-gray-800">
                {new Date(order.ordered_at).toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-gray-500 block">Customer:</span>
              <span className="font-medium text-gray-800">
                {order.customer_id ? `Customer ID: ${order.customer_id.substring(0, 8)}...` : "Walk-in Customer"}
              </span>
            </div>
          </div>

          {/* Line items table */}
          <div>
            <h3 className="text-xs font-semibold text-gray-700 mb-2">Order Items (Immutable Snapshots)</h3>
            <div className="overflow-x-auto border rounded-md">
              <table className="min-w-full divide-y divide-gray-200 text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-500">Product</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-500">Code</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-500">Qty</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-500">Unit Price</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-500">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {order.items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-3 py-2 font-medium text-gray-900">
                        {item.product_name_snapshot}
                      </td>
                      <td className="px-3 py-2 text-gray-500 font-mono">
                        {item.product_code_snapshot}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {item.quantity} {item.unit_snapshot}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {formatMoney(item.unit_price_minor, item.currency_code)}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold text-gray-900">
                        {formatMoney(item.line_total_minor, item.currency_code)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Grand total */}
          <div className="flex justify-between items-center bg-gray-100 p-3 rounded-md">
            <span className="text-sm font-semibold text-gray-700">Order Total:</span>
            <span className="text-lg font-bold text-gray-900">
              {formatMoney(order.order_total_minor, order.currency_code)}
            </span>
          </div>
        </div>

        <div className="border-t pt-4 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-md bg-gray-200 px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-300 focus:outline-none"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
