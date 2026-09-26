"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
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
  const [statusFilter, setStatusFilter] = useState<"all" | "in_stock" | "low_stock" | "out_of_stock" | "uninitialized">("all");
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

  // Operational metrics
  const stockMetrics = useMemo(() => {
    let inStockCount = 0;
    let lowStockCount = 0;
    let outOfStockCount = 0;
    let uninitializedCount = 0;

    if (productsData?.items) {
      for (const p of productsData.items) {
        const bal = balanceMap.get(p.id);
        if (!bal) {
          uninitializedCount++;
        } else if (bal.onHand <= 0) {
          outOfStockCount++;
        } else if (bal.onHand <= 10) {
          lowStockCount++;
        } else {
          inStockCount++;
        }
      }
    }

    return { inStockCount, lowStockCount, outOfStockCount, uninitializedCount };
  }, [productsData, balanceMap]);

  // Filter products by search term and status
  const filteredProducts = useMemo(() => {
    if (!productsData?.items) return [];
    let list = productsData.items;

    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      list = list.filter(
        (p) => p.name.toLowerCase().includes(term) || p.code.toLowerCase().includes(term)
      );
    }

    if (statusFilter !== "all") {
      list = list.filter((p) => {
        const bal = balanceMap.get(p.id);
        if (statusFilter === "uninitialized") return !bal;
        if (!bal) return false;
        if (statusFilter === "out_of_stock") return bal.onHand <= 0;
        if (statusFilter === "low_stock") return bal.onHand > 0 && bal.onHand <= 10;
        if (statusFilter === "in_stock") return bal.onHand > 10;
        return true;
      });
    }

    return list;
  }, [productsData, searchTerm, statusFilter, balanceMap]);

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
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Inventory Management</h1>
          <p className="text-sm text-slate-500">
            Track real-time stock balances, manage adjustments, and audit stock movements.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/workspace/${orgId}/catalog`}
            className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
          >
            Manage Catalog
          </Link>
          {canMutate && (
            <button
              onClick={() => handleOpenOpeningModal()}
              disabled={!productsData?.items?.length}
              className="inline-flex items-center rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2 disabled:opacity-50"
            >
              Record Opening Stock
            </button>
          )}
        </div>
      </div>

      {/* Operational Stock Alert Banner */}
      {(stockMetrics.lowStockCount > 0 || stockMetrics.outOfStockCount > 0) && (
        <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50/70 p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 text-amber-800 font-bold text-sm">
              !
            </span>
            <div>
              <p className="text-sm font-semibold text-amber-900">Stock Availability Attention Required</p>
              <p className="text-xs text-amber-700">
                {stockMetrics.outOfStockCount > 0 && `${stockMetrics.outOfStockCount} product(s) out of stock. `}
                {stockMetrics.lowStockCount > 0 && `${stockMetrics.lowStockCount} product(s) below reorder threshold (≤10).`}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setStatusFilter(stockMetrics.outOfStockCount > 0 ? "out_of_stock" : "low_stock")}
            className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 shadow-xs hover:bg-amber-50"
          >
            Filter Affected
          </button>
        </div>
      )}

      {/* Search & Filter Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search by product name or code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm placeholder-slate-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 shadow-xs"
          />
        </div>

        {/* Status Filter Chips */}
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setStatusFilter("all")}
            className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
              statusFilter === "all"
                ? "bg-slate-800 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            All ({productsData?.items?.length ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("in_stock")}
            className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
              statusFilter === "in_stock"
                ? "bg-emerald-700 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            In Stock ({stockMetrics.inStockCount})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("low_stock")}
            className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
              statusFilter === "low_stock"
                ? "bg-amber-600 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            Low Stock ({stockMetrics.lowStockCount})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("out_of_stock")}
            className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
              statusFilter === "out_of_stock"
                ? "bg-rose-600 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            Out of Stock ({stockMetrics.outOfStockCount})
          </button>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        {isLoading ? (
          <div className="py-12 text-center text-sm text-slate-500">Loading inventory records...</div>
        ) : filteredProducts.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-sm text-slate-500">
              {productsData?.items?.length === 0
                ? "No active products found in catalog. Create products first."
                : "No products match your search query."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50/80">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Product</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Base Unit</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-600">On-Hand Stock</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Status</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filteredProducts.map((p) => {
                  const balInfo = balanceMap.get(p.id);
                  const isInitialized = balInfo !== undefined;
                  const onHand = isInitialized ? balInfo.onHand : 0;

                  return (
                    <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{p.name}</div>
                        <div className="text-xs text-slate-500">{p.code}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-600 capitalize">{p.base_unit}</td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-900">
                        {isInitialized ? onHand : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {!isInitialized ? (
                          <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 border border-slate-200">
                            Uninitialized
                          </span>
                        ) : onHand <= 0 ? (
                          <span className="inline-flex rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700 border border-rose-200">
                            Out of Stock
                          </span>
                        ) : onHand <= 10 ? (
                          <span className="inline-flex rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800 border border-amber-200">
                            Low Stock
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 border border-emerald-200">
                            In Stock
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleOpenHistoryModal(p)}
                            className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-xs"
                          >
                            History
                          </button>

                          {canMutate && (
                            <>
                              {!isInitialized ? (
                                <button
                                  onClick={() => handleOpenOpeningModal(p.id)}
                                  className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200 hover:bg-emerald-100"
                                >
                                  Opening Stock
                                </button>
                              ) : (
                                <>
                                  <button
                                    onClick={() => handleOpenAdjustModal(p, "adjustment")}
                                    className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200 hover:bg-emerald-100"
                                  >
                                    Adjust Stock
                                  </button>
                                  <button
                                    onClick={() => handleOpenAdjustModal(p, "correction")}
                                    className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-xs"
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
