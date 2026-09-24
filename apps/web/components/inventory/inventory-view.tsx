"use client";

import React, { useMemo, useState } from "react";
import { useProducts } from "@/hooks/use-catalog";
import { useInventoryBalances } from "@/hooks/use-inventory";
import { Product } from "@/lib/schemas/catalog";
import { OpeningStockModal } from "@/components/inventory/opening-stock-modal";
import { AdjustmentModal } from "@/components/inventory/adjustment-modal";
import { MovementHistoryModal } from "@/components/inventory/movement-history-modal";

interface InventoryViewProps {
  orgId: string;
  userRole?: string;
  token?: string;
}

export function InventoryView({ orgId, userRole = "owner", token }: InventoryViewProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [openingModalOpen, setOpeningModalOpen] = useState(false);
  const [selectedProductForOpening, setSelectedProductForOpening] = useState<string | undefined>();

  const [adjustModalOpen, setAdjustModalOpen] = useState(false);
  const [adjustMode, setAdjustMode] = useState<"adjustment" | "correction">("adjustment");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [selectedProductForHistory, setSelectedProductForHistory] = useState<Product | null>(null);

  const { data: productsData, isLoading: productsLoading } = useProducts(
    orgId,
    { status: "active", limit: 100 },
    token
  );
  const { data: balancesData, isLoading: balancesLoading } = useInventoryBalances(orgId, 100, 0, token);

  const normalizedRole = userRole.toLowerCase().trim();
  const canMutate = normalizedRole === "owner" || normalizedRole === "manager";

  // Build map of product_id -> balance
  const balanceMap = useMemo(() => {
    const map = new Map<string, { onHand: number; version: number }>();
    if (balancesData?.items) {
      for (const b of balancesData.items) {
        map.set(b.product_id, { onHand: b.on_hand_quantity, version: b.version });
      }
    }
    return map;
  }, [balancesData]);

  // Filter products by search term
  const filteredProducts = useMemo(() => {
    if (!productsData?.items) return [];
    if (!searchTerm.trim()) return productsData.items;
    const term = searchTerm.toLowerCase();
    return productsData.items.filter(
      (p) => p.name.toLowerCase().includes(term) || p.code.toLowerCase().includes(term)
    );
  }, [productsData, searchTerm]);

  const isLoading = productsLoading || balancesLoading;

  const handleOpenOpeningModal = (productId?: string) => {
    setSelectedProductForOpening(productId);
    setOpeningModalOpen(true);
  };

  const handleOpenAdjustModal = (product: Product, mode: "adjustment" | "correction") => {
    setSelectedProduct(product);
    setAdjustMode(mode);
    setAdjustModalOpen(true);
  };

  const handleOpenHistoryModal = (product: Product) => {
    setSelectedProductForHistory(product);
    setHistoryModalOpen(true);
  };

  return (
    <div className="space-y-6 p-6">
      {/* Top Banner & Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Inventory Management</h1>
          <p className="text-sm text-gray-500">
            Track real-time stock balances, manage adjustments, and audit stock movements.
          </p>
        </div>

        {canMutate && (
          <div className="flex gap-2">
            <button
              onClick={() => handleOpenOpeningModal()}
              disabled={!productsData?.items?.length}
              className="inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none disabled:opacity-50"
            >
              Record Opening Stock
            </button>
          </div>
        )}
      </div>

      {/* Search & Filter Bar */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Search by product name or code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="py-12 text-center text-sm text-gray-500">Loading inventory records...</div>
        ) : filteredProducts.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-sm text-gray-500">
              {productsData?.items?.length === 0
                ? "No active products found in catalog. Create products first."
                : "No products match your search query."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Product</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Base Unit</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">On-Hand Stock</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {filteredProducts.map((p) => {
                  const balInfo = balanceMap.get(p.id);
                  const isInitialized = balInfo !== undefined;
                  const onHand = isInitialized ? balInfo.onHand : 0;

                  return (
                    <tr key={p.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-gray-900">{p.name}</div>
                        <div className="text-xs text-gray-500">{p.code}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-600 capitalize">{p.base_unit}</td>
                      <td className="px-4 py-3 text-right font-semibold text-gray-900">
                        {isInitialized ? onHand : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {!isInitialized ? (
                          <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800">
                            Uninitialized
                          </span>
                        ) : onHand <= 0 ? (
                          <span className="inline-flex rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800">
                            Out of Stock
                          </span>
                        ) : onHand <= 10 ? (
                          <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                            Low Stock
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                            In Stock
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleOpenHistoryModal(p)}
                            className="rounded border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                          >
                            History
                          </button>

                          {canMutate && (
                            <>
                              {!isInitialized ? (
                                <button
                                  onClick={() => handleOpenOpeningModal(p.id)}
                                  className="rounded bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                                >
                                  Opening Stock
                                </button>
                              ) : (
                                <>
                                  <button
                                    onClick={() => handleOpenAdjustModal(p, "adjustment")}
                                    className="rounded bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                                  >
                                    Adjust Stock
                                  </button>
                                  <button
                                    onClick={() => handleOpenAdjustModal(p, "correction")}
                                    className="rounded border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100"
                                  >
                                    Correct Count
                                  </button>
                                </>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      {productsData?.items && (
        <OpeningStockModal
          isOpen={openingModalOpen}
          onClose={() => setOpeningModalOpen(false)}
          orgId={orgId}
          products={productsData.items}
          token={token}
          preselectedProductId={selectedProductForOpening}
        />
      )}

      {selectedProduct && (
        <AdjustmentModal
          isOpen={adjustModalOpen}
          onClose={() => {
            setAdjustModalOpen(false);
            setSelectedProduct(null);
          }}
          orgId={orgId}
          product={selectedProduct}
          currentOnHand={balanceMap.get(selectedProduct.id)?.onHand ?? 0}
          mode={adjustMode}
          token={token}
        />
      )}

      {selectedProductForHistory && (
        <MovementHistoryModal
          isOpen={historyModalOpen}
          onClose={() => {
            setHistoryModalOpen(false);
            setSelectedProductForHistory(null);
          }}
          orgId={orgId}
          product={selectedProductForHistory}
          token={token}
        />
      )}
    </div>
  );
}
