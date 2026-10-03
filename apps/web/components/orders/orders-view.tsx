"use client";

import React, { useState, useContext } from "react";
import Link from "next/link";
import { formatMoney, Order } from "@/lib/schemas/orders";
import { useOrders } from "@/hooks/use-orders";
import { AuthContext } from "@/components/providers/auth-provider";
import { OrderCreateModal } from "@/components/orders/order-create-modal";
import { OrderDetailModal } from "@/components/orders/order-detail-modal";
import { OrderVoidModal } from "@/components/orders/order-void-modal";
import { OrderCorrectModal } from "@/components/orders/order-correct-modal";

interface OrdersViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
  initialCustomerId?: string;
}

export function OrdersView({ orgId, userRole = "owner", token, initialCustomerId }: OrdersViewProps) {
  const auth = useContext(AuthContext);
  const effectiveToken = token || auth?.token || undefined;
  const [statusFilter, setStatusFilter] = useState<string | undefined>("all");
  const [selectedCustomerId] = useState<string | undefined>(initialCustomerId);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isVoidOpen, setIsVoidOpen] = useState(false);
  const [isCorrectOpen, setIsCorrectOpen] = useState(false);

  const effectiveStatus = statusFilter === "all" ? undefined : statusFilter;

  const { data, isLoading, error, refetch } = useOrders(
    orgId,
    {
      status: effectiveStatus,
      customerId: selectedCustomerId,
      limit: 100,
      offset: 0,
    },
    effectiveToken
  );

  const normalizedRole = userRole.toLowerCase();
  const isOwner = normalizedRole === "owner";
  const isManager = normalizedRole === "manager";
  const isStaff = normalizedRole === "staff";

  // Permission flags:
  // - orders:create -> Owner, Manager, Staff
  // - orders:correct -> Owner, Manager
  // - orders:void -> Owner only
  const canCreate = isOwner || isManager || isStaff;
  const canCorrect = isOwner || isManager;
  const canVoid = isOwner;

  const orders = data?.items || [];

  const handleOpenDetail = (order: Order) => {
    setSelectedOrder(order);
    setIsDetailOpen(true);
  };

  const handleOpenVoid = (order: Order) => {
    setSelectedOrder(order);
    setIsVoidOpen(true);
  };

  const handleOpenCorrect = (order: Order) => {
    setSelectedOrder(order);
    setIsCorrectOpen(true);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-tertiary-fixed text-on-tertiary-fixed border-tertiary-fixed-dim";
      case "voided":
        return "bg-error-container text-on-error-container border-error/20";
      case "corrected":
        return "bg-amber-100 text-amber-800 border-amber-200";
      default:
        return "bg-surface-container text-on-surface-variant border-outline-variant";
    }
  };

  return (
    <div className="space-y-6 p-4 sm:p-6 lg:p-8 bg-surface min-h-screen">
      {/* Header (Stitch Orders & Sales Top Bar) */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-label-caps text-[11px] uppercase tracking-wider text-primary font-semibold">
              Commercial Operations
            </span>
            <span className="text-outline">•</span>
            <span className="font-mono text-xs text-outline">Atomic Deductions</span>
          </div>
          <h1 className="mt-1 font-display-lg text-2xl sm:text-3xl font-bold tracking-tight text-on-surface">
            Orders & Sales
          </h1>
          <p className="mt-1 font-body-md text-sm text-on-surface-variant">
            Record customer sales, deduct warehouse stock atomically, and manage order lifecycles.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href={`/workspace/${orgId}/customers`}
            className="inline-flex items-center rounded-xl border border-outline-variant/60 bg-surface-container-lowest px-3.5 py-2 font-body-sm text-xs font-semibold text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
          >
            Customers Directory
          </Link>
          {canCreate && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="inline-flex items-center rounded-xl bg-primary hover:bg-primary-container px-4 py-2 font-body-sm text-xs font-semibold text-on-primary shadow-xs transition-all active:scale-[0.99]"
            >
              New Order Entry
            </button>
          )}
        </div>
      </div>

      {/* Role notice banner if Staff */}
      {isStaff && (
        <div className="rounded-2xl border border-amber-300/80 bg-amber-50/80 p-3.5 text-xs text-amber-950 shadow-xs flex items-center gap-2">
          <span className="font-bold">🛡️ Staff Permissions:</span>
          <span>You have permission to record new customer sales and view orders. Voiding and correcting orders require managerial authority.</span>
        </div>
      )}

      {selectedCustomerId && (
        <div className="flex items-center justify-between rounded-2xl border border-primary/30 bg-primary-fixed/30 px-4 py-2.5 text-xs text-primary shadow-xs">
          <span>Filtering orders for customer: <strong className="font-mono">{selectedCustomerId}</strong></span>
          <Link href={`/workspace/${orgId}/orders`} className="font-semibold underline hover:text-on-primary-fixed-variant">
            Show All Orders
          </Link>
        </div>
      )}

      {/* Filter Tabs (Stitch Segmented Style) */}
      <div className="flex items-center p-1 bg-surface-container-high rounded-xl w-fit shadow-xs gap-1">
        {(["all", "active", "voided", "corrected"] as const).map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`rounded-lg px-3 py-1.5 font-label-md text-xs font-semibold capitalize transition-all ${
              statusFilter === st
                ? "bg-surface-container-lowest text-primary shadow-xs"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Orders Table (Stitch Enterprise Ledger Table) */}
      <div className="overflow-hidden rounded-2xl border border-surface-container-high/80 bg-surface-container-lowest shadow-xs">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-outline">
            Loading orders...
          </div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-error">
            Failed to load orders: {error.message}
            <div className="mt-2">
              <button
                onClick={() => refetch()}
                className="text-xs text-primary underline font-medium"
              >
                Retry
              </button>
            </div>
          </div>
        ) : orders.length === 0 ? (
          <div className="p-8 text-center text-sm text-outline">
            No orders found. {canCreate && "Click 'New Order Entry' to record your first sale."}
          </div>
        ) : (
          <table className="min-w-full divide-y divide-surface-container-high text-sm">
            <thead className="bg-surface-container-low/40">
              <tr>
                <th className="px-4 py-3 text-left font-label-caps uppercase text-outline text-[11px]">Order #</th>
                <th className="px-4 py-3 text-left font-label-caps uppercase text-outline text-[11px]">Status</th>
                <th className="px-4 py-3 text-left font-label-caps uppercase text-outline text-[11px]">Date</th>
                <th className="px-4 py-3 text-right font-label-caps uppercase text-outline text-[11px]">Total</th>
                <th className="px-4 py-3 text-right font-label-caps uppercase text-outline text-[11px]">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low bg-surface-container-lowest">
              {orders.map((order) => (
                <tr key={order.id} className="hover:bg-surface-container-low/50 transition-colors font-body-sm">
                  <td className="px-4 py-3 font-semibold text-primary font-mono font-data-cell">
                    {order.order_number}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full border px-2 py-0.5 font-data-badge text-xs font-semibold capitalize ${getStatusBadge(
                        order.status
                      )}`}
                    >
                      {order.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-on-surface-variant font-mono text-xs">
                    {new Date(order.ordered_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-on-surface font-mono">
                    {formatMoney(order.order_total_minor, order.currency_code)}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      onClick={() => handleOpenDetail(order)}
                      className="text-xs text-primary hover:text-primary-container font-semibold"
                    >
                      View
                    </button>

                    {order.status === "active" && canCorrect && (
                      <button
                        onClick={() => handleOpenCorrect(order)}
                        className="text-xs text-amber-700 hover:text-amber-900 font-semibold"
                      >
                        Correct
                      </button>
                    )}

                    {order.status === "active" && canVoid && (
                      <button
                        onClick={() => handleOpenVoid(order)}
                        className="text-xs text-error hover:text-on-error-container font-semibold"
                      >
                        Void
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modals */}
      <OrderCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        orgId={orgId}
        token={effectiveToken}
        initialCustomerId={selectedCustomerId}
      />

      <OrderDetailModal
        isOpen={isDetailOpen}
        onClose={() => {
          setIsDetailOpen(false);
          setSelectedOrder(null);
        }}
        order={selectedOrder}
      />

      <OrderVoidModal
        isOpen={isVoidOpen}
        onClose={() => {
          setIsVoidOpen(false);
          setSelectedOrder(null);
        }}
        order={selectedOrder}
        orgId={orgId}
        token={effectiveToken}
      />

      <OrderCorrectModal
        isOpen={isCorrectOpen}
        onClose={() => {
          setIsCorrectOpen(false);
          setSelectedOrder(null);
        }}
        order={selectedOrder}
        orgId={orgId}
        token={effectiveToken}
      />
    </div>
  );
}
