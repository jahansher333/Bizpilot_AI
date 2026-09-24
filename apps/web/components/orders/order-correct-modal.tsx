"use client";

import React, { useState, useEffect } from "react";
import { formatMoney, Order, orderCorrectSchema } from "@/lib/schemas/orders";
import { useCorrectOrder } from "@/hooks/use-orders";
import { useProducts } from "@/hooks/use-catalog";
import { useCustomers } from "@/hooks/use-customers";

interface LineItemDraft {
  id: string;
  product_id: string;
  quantity: number;
  unit_price_minor: number;
}

interface OrderCorrectModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: Order | null;
  orgId: string;
  token?: string;
}

export function OrderCorrectModal({
  isOpen,
  onClose,
  order,
  orgId,
  token,
}: OrderCorrectModalProps) {
  const [reason, setReason] = useState("");
  const [customerId, setCustomerId] = useState<string>("");
  const [items, setItems] = useState<LineItemDraft[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: productsData } = useProducts(orgId, { status: "active", limit: 100 }, token);
  const { data: customersData } = useCustomers(orgId, { status: "active", limit: 100 }, token);
  const correctMutation = useCorrectOrder(orgId, token);

  useEffect(() => {
    if (order) {
      setReason("");
      setCustomerId(order.customer_id || "");
      if (order.items && order.items.length > 0) {
        setItems(
          order.items.map((it, idx) => ({
            id: `item-${idx}-${it.id}`,
            product_id: it.product_id || "",
            quantity: it.quantity,
            unit_price_minor: it.unit_price_minor,
          }))
        );
      } else {
        setItems([{ id: "item-1", product_id: "", quantity: 1, unit_price_minor: 0 }]);
      }
    }
  }, [order]);

  if (!isOpen || !order) return null;

  const products = productsData?.items || [];
  const customers = customersData?.items || [];

  const handleProductChange = (index: number, productId: string) => {
    const selectedProd = products.find((p) => p.id === productId);
    const updated = [...items];
    updated[index] = {
      ...updated[index],
      product_id: productId,
      unit_price_minor: selectedProd ? selectedProd.default_price_minor : 0,
    };
    setItems(updated);
  };

  const handleQuantityChange = (index: number, qtyStr: string) => {
    const val = parseInt(qtyStr, 10);
    const updated = [...items];
    updated[index] = {
      ...updated[index],
      quantity: isNaN(val) ? 0 : val,
    };
    setItems(updated);
  };

  const handlePriceChange = (index: number, priceMajorStr: string) => {
    const val = parseFloat(priceMajorStr);
    const updated = [...items];
    updated[index] = {
      ...updated[index],
      unit_price_minor: isNaN(val) ? 0 : Math.round(val * 100),
    };
    setItems(updated);
  };

  const handleAddItem = () => {
    setItems([
      ...items,
      { id: `item-${Date.now()}`, product_id: "", quantity: 1, unit_price_minor: 0 },
    ]);
  };

  const handleRemoveItem = (index: number) => {
    if (items.length <= 1) return;
    setItems(items.filter((_, i) => i !== index));
  };

  const grandTotalMinor = items.reduce(
    (sum, it) => sum + (it.quantity > 0 ? it.quantity * it.unit_price_minor : 0),
    0
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const payload = {
      reason,
      customer_id: customerId.trim() || undefined,
      items: items.map((it) => ({
        product_id: it.product_id,
        quantity: it.quantity,
        unit_price_minor: it.unit_price_minor,
      })),
      currency_code: "PKR",
    };

    const parseResult = orderCorrectSchema.safeParse(payload);
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0].message);
      return;
    }

    try {
      const idempotencyKey = `web-correct-${order.id}-${Date.now()}`;
      await correctMutation.mutateAsync({
        orderId: order.id,
        payload: parseResult.data,
        idempotencyKey,
      });
      onClose();
    } catch (err: any) {
      setFormError(err.message || "Failed to correct order");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 className="text-lg font-semibold text-amber-700">
            Correct Order {order.order_number}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500 focus:outline-none"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto py-4 space-y-4">
          <div className="rounded-md bg-amber-50 p-3 text-xs text-amber-800 border border-amber-200 space-y-1">
            <p className="font-semibold">Correction Semantics:</p>
            <p>
              Order <strong>{order.order_number}</strong> will be marked as <strong>corrected</strong>. A replacement order will be generated and linked bi-directionally. Previous quantities will be reversed and replacement quantities deducted from warehouse stock.
            </p>
          </div>

          {formError && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200">
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
              placeholder="e.g. Quantity adjusted per customer call / wrong item selected"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Customer
            </label>
            <select
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
            >
              <option value="">Walk-in Customer (Anonymous)</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} {c.phone ? `(${c.phone})` : ""}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-gray-700">Replacement Line Items</label>
              <button
                type="button"
                onClick={handleAddItem}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
              >
                + Add Item
              </button>
            </div>

            <div className="space-y-3">
              {items.map((it, idx) => {
                const lineTotal = it.quantity > 0 ? it.quantity * it.unit_price_minor : 0;
                return (
                  <div
                    key={it.id}
                    className="flex flex-col sm:flex-row items-start sm:items-center gap-2 border rounded-md p-2 bg-gray-50"
                  >
                    <div className="flex-1 w-full sm:w-auto">
                      <select
                        aria-label={`Replacement item ${idx + 1}`}
                        value={it.product_id}
                        onChange={(e) => handleProductChange(idx, e.target.value)}
                        className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:border-indigo-500 focus:outline-none"
                        required
                      >
                        <option value="">Select product...</option>
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} ({p.code}) — {formatMoney(p.default_price_minor)}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="w-24">
                      <input
                        type="number"
                        min="1"
                        placeholder="Qty"
                        value={it.quantity || ""}
                        onChange={(e) => handleQuantityChange(idx, e.target.value)}
                        className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs text-right focus:border-indigo-500 focus:outline-none"
                        required
                      />
                    </div>

                    <div className="w-28">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="Price"
                        value={(it.unit_price_minor / 100).toFixed(2)}
                        onChange={(e) => handlePriceChange(idx, e.target.value)}
                        className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs text-right focus:border-indigo-500 focus:outline-none"
                        required
                      />
                    </div>

                    <div className="w-28 text-right font-medium text-xs text-gray-700 py-1">
                      {formatMoney(lineTotal)}
                    </div>

                    {items.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveItem(idx)}
                        className="text-red-500 hover:text-red-700 text-xs px-1"
                        title="Remove item"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex justify-between items-center bg-gray-100 p-3 rounded-md">
            <span className="text-sm font-semibold text-gray-700">Replacement Total:</span>
            <span className="text-lg font-bold text-gray-900">{formatMoney(grandTotalMinor)}</span>
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
              disabled={correctMutation.isPending}
              className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-amber-700 focus:outline-none disabled:opacity-50"
            >
              {correctMutation.isPending ? "Submitting Correction..." : "Save Correction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
