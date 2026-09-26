"use client";

import React, { useState } from "react";
import Link from "next/link";
import { formatMoney, Order } from "@/lib/schemas/orders";
import { useOrders } from "@/hooks/use-orders";
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
    token
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
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Orders & Sales
          </h1>
          <p className="text-sm text-gray-500">
            Record customer sales, deduct warehouse stock atomically, and manage order lifecycles.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href={`/workspace/${orgId}/customers`}
            className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none"
          >
            Customers Directory
          </Link>
          {canCreate && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="inline-flex items-center rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800 focus:outline-none"
            >
              New Order Entry
            </button>
          )}
        </div>
      </div>

      {/* Role notice banner if Staff */}
      {isStaff && (
        <div className="rounded-md border border-amber-100 bg-amber-50 p-3 text-xs text-amber-800">
          <span className="font-semibold">Staff Permissions:</span> You have permission to record new customer sales and view orders. Voiding and correcting orders require managerial authority.
        </div>
      )}

      {selectedCustomerId && (
        <div className="flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs text-emerald-900">
          <span>Filtering orders for customer: <strong className="font-mono">{selectedCustomerId}</strong></span>
          <Link href={`/workspace/${orgId}/orders`} className="font-medium underline hover:text-emerald-950">
            Show All Orders
          </Link>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-gray-200 pb-2">
        {(["all", "active", "voided", "corrected"] as const).map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
              statusFilter === st
                ? "bg-emerald-100 text-emerald-900 font-semibold"
                : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Orders Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-500">
            Loading orders...
          </div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-red-600">
            Failed to load orders: {error.message}
            <div className="mt-2">
              <button
                onClick={() => refetch()}
                className="text-xs text-indigo-600 underline font-medium"
              >
                Retry
              </button>
            </div>
          </div>
        ) : orders.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">
            No orders found. {canCreate && "Click 'New Order Entry' to record your first sale."}
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Order #</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500">Date</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Total</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {orders.map((order) => (
                <tr key={order.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900 font-mono">
                    {order.order_number}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold capitalize ${getStatusBadge(
                        order.status
                      )}`}
                    >
                      {order.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {new Date(order.ordered_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-gray-900">
                    {formatMoney(order.order_total_minor, order.currency_code)}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      onClick={() => handleOpenDetail(order)}
                      className="text-xs text-indigo-600 hover:text-indigo-900 font-medium"
                    >
                      View
                    </button>

                    {order.status === "active" && canCorrect && (
                      <button
                        onClick={() => handleOpenCorrect(order)}
                        className="text-xs text-amber-600 hover:text-amber-900 font-medium"
                      >
                        Correct
                      </button>
                    )}

                    {order.status === "active" && canVoid && (
                      <button
                        onClick={() => handleOpenVoid(order)}
                        className="text-xs text-red-600 hover:text-red-900 font-medium"
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
        token={token}
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
        token={token}
      />

      <OrderCorrectModal
        isOpen={isCorrectOpen}
        onClose={() => {
          setIsCorrectOpen(false);
          setSelectedOrder(null);
        }}
        order={selectedOrder}
        orgId={orgId}
        token={token}
      />
    </div>
  );
}
