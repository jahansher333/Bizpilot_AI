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
    <div className="space-y-6 p-4 sm:p-6 lg:p-8 bg-surface min-h-screen">
      {/* Top Banner & Header (Stitch Inventory Header) */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-label-caps text-[11px] uppercase tracking-wider text-primary font-semibold">
              Warehousing & Logistics
            </span>
            <span className="text-outline">•</span>
            <span className="font-mono text-xs text-outline">Real-Time Balances</span>
          </div>
          <h1 className="mt-1 font-display-lg text-2xl sm:text-3xl font-bold tracking-tight text-on-surface">
            Inventory Management
          </h1>
          <p className="mt-1 font-body-md text-sm text-on-surface-variant">
            Track real-time stock balances, manage adjustments, and audit stock movements.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            href={`/workspace/${orgId}/catalog`}
            className="inline-flex items-center rounded-xl border border-outline-variant/60 bg-surface-container-lowest px-3.5 py-2 text-xs font-semibold text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
          >
            Manage Catalog
          </Link>
          {canMutate && (
            <button
              onClick={() => handleOpenOpeningModal()}
              disabled={!productsData?.items?.length}
              className="inline-flex items-center rounded-xl bg-primary px-4 py-2 font-body-sm text-xs font-semibold text-on-primary shadow-xs hover:bg-primary-container transition-all active:scale-[0.99] disabled:opacity-50"
            >
              Record Opening Stock
            </button>
          )}
        </div>
      </div>

      {/* Operational Stock Alert Banner */}
      {(stockMetrics.lowStockCount > 0 || stockMetrics.outOfStockCount > 0) && (
        <div className="flex items-center justify-between rounded-2xl border border-amber-300/80 bg-amber-50/80 p-4 shadow-xs">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-100 text-amber-800 font-bold text-sm shadow-xs">
              ⚠️
            </span>
            <div>
              <p className="text-sm font-semibold text-amber-950">Stock Availability Attention Required</p>
              <p className="text-xs text-amber-800">
                {stockMetrics.outOfStockCount > 0 && `${stockMetrics.outOfStockCount} product(s) out of stock. `}
                {stockMetrics.lowStockCount > 0 && `${stockMetrics.lowStockCount} product(s) below reorder threshold (≤10).`}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setStatusFilter(stockMetrics.outOfStockCount > 0 ? "out_of_stock" : "low_stock")}
            className="rounded-xl border border-amber-300 bg-white px-3 py-1.5 font-label-md text-xs font-semibold text-amber-900 shadow-xs hover:bg-amber-50 transition-colors"
          >
            Filter Affected
          </button>
        </div>
      )}

      {/* Search & Filter Bar (Stitch Precision Control Bar) */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search by product name or code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="block w-full rounded-xl border border-outline-variant/60 bg-surface-container-lowest px-3.5 py-2 font-body-sm text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
          />
        </div>

        {/* Status Filter Chips */}
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setStatusFilter("all")}
            className={`rounded-xl px-3 py-1.5 font-data-badge text-xs font-semibold transition-all ${
              statusFilter === "all"
                ? "bg-on-surface text-surface shadow-xs"
                : "border border-outline-variant/60 bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            All ({productsData?.items?.length ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("in_stock")}
            className={`rounded-xl px-3 py-1.5 font-data-badge text-xs font-semibold transition-all ${
              statusFilter === "in_stock"
                ? "bg-tertiary text-on-tertiary shadow-xs"
                : "border border-outline-variant/60 bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            In Stock ({stockMetrics.inStockCount})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("low_stock")}
            className={`rounded-xl px-3 py-1.5 font-data-badge text-xs font-semibold transition-all ${
              statusFilter === "low_stock"
                ? "bg-amber-600 text-white shadow-xs"
                : "border border-outline-variant/60 bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            Low Stock ({stockMetrics.lowStockCount})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter("out_of_stock")}
            className={`rounded-xl px-3 py-1.5 font-data-badge text-xs font-semibold transition-all ${
              statusFilter === "out_of_stock"
                ? "bg-error text-on-error shadow-xs"
                : "border border-outline-variant/60 bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            Out of Stock ({stockMetrics.outOfStockCount})
          </button>
        </div>
      </div>

      {/* Table Content (Stitch Enterprise Ledger Table) */}
      <div className="overflow-hidden rounded-2xl border border-surface-container-high/80 bg-surface-container-lowest shadow-xs">
        {isLoading ? (
          <div className="py-12 text-center text-sm text-outline">Loading inventory records...</div>
        ) : filteredProducts.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-sm text-outline">
              {productsData?.items?.length === 0
                ? "No active products found in catalog. Create products first."
                : "No products match your search query."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-surface-container-high text-sm">
              <thead className="bg-surface-container-low/40">
                <tr>
                  <th className="px-4 py-3 text-left font-label-caps uppercase text-outline text-[11px]">Product</th>
                  <th className="px-4 py-3 text-left font-label-caps uppercase text-outline text-[11px]">Base Unit</th>
                  <th className="px-4 py-3 text-right font-label-caps uppercase text-outline text-[11px]">On-Hand Stock</th>
                  <th className="px-4 py-3 text-left font-label-caps uppercase text-outline text-[11px]">Status</th>
                  <th className="px-4 py-3 text-right font-label-caps uppercase text-outline text-[11px]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low bg-surface-container-lowest">
                {filteredProducts.map((p) => {
                  const balInfo = balanceMap.get(p.id);
                  const isInitialized = balInfo !== undefined;
                  const onHand = isInitialized ? balInfo.onHand : 0;

                  return (
                    <tr key={p.id} className="hover:bg-surface-container-low/50 transition-colors font-body-sm">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-on-surface">{p.name}</div>
                        <div className="font-mono text-xs text-primary font-data-cell">{p.code}</div>
                      </td>
                      <td className="px-4 py-3 text-on-surface-variant capitalize">{p.base_unit}</td>
                      <td className="px-4 py-3 text-right font-semibold text-on-surface font-mono">
                        {isInitialized ? onHand : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {!isInitialized ? (
                          <span className="inline-flex rounded-full bg-surface-container px-2.5 py-0.5 font-data-badge text-xs font-medium text-on-surface-variant border border-outline-variant/40">
                            Uninitialized
                          </span>
                        ) : onHand <= 0 ? (
                          <span className="inline-flex rounded-full bg-error-container px-2.5 py-0.5 font-data-badge text-xs font-semibold text-on-error-container border border-error/20">
                            Out of Stock
                          </span>
                        ) : onHand <= 10 ? (
                          <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-0.5 font-data-badge text-xs font-semibold text-amber-800 border border-amber-200">
                            Low Stock
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full bg-tertiary-fixed px-2.5 py-0.5 font-data-badge text-xs font-semibold text-on-tertiary-fixed border border-tertiary-fixed-dim">
                            In Stock
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleOpenHistoryModal(p)}
                            className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest px-2.5 py-1 text-xs font-semibold text-on-surface hover:bg-surface-container-high shadow-xs transition-colors"
                          >
                            History
                          </button>

                          {canMutate && (
                            <>
                              {!isInitialized ? (
                                <button
                                  onClick={() => handleOpenOpeningModal(p.id)}
                                  className="rounded-xl bg-primary-fixed px-2.5 py-1 text-xs font-semibold text-primary border border-primary-fixed-dim hover:bg-primary-fixed-dim transition-colors"
                                >
                                  Opening Stock
                                </button>
                              ) : (
                                <>
                                  <button
                                    onClick={() => handleOpenAdjustModal(p, "adjustment")}
                                    className="rounded-xl bg-primary-fixed px-2.5 py-1 text-xs font-semibold text-primary border border-primary-fixed-dim hover:bg-primary-fixed-dim transition-colors"
                                  >
                                    Adjust Stock
                                  </button>
                                  <button
                                    onClick={() => handleOpenAdjustModal(p, "correction")}
                                    className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest px-2.5 py-1 text-xs font-semibold text-on-surface hover:bg-surface-container-high shadow-xs transition-colors"
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
