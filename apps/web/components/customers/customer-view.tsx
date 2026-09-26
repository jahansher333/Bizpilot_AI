"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Customer } from "@/lib/schemas/customers";
import { useArchiveCustomer, useCustomers } from "@/hooks/use-customers";
import { CustomerModal } from "@/components/customers/customer-modal";

interface CustomerViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
}

export function CustomerView({ orgId, userRole = "owner", token }: CustomerViewProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | undefined>("active");
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { data, isLoading, error } = useCustomers(
    orgId,
    {
      status: statusFilter,
      search: search.trim() || undefined,
      limit: 100,
      offset: 0,
    },
    token
  );

  const archiveMutation = useArchiveCustomer(orgId, token);

  const canMutate = userRole.toLowerCase() === "owner" || userRole.toLowerCase() === "manager";
  const canCreate = true; // Owner, Manager, and Staff can create customers

  const handleOpenCreate = () => {
    setSelectedCustomer(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (customer: Customer) => {
    setSelectedCustomer(customer);
    setIsModalOpen(true);
  };

  const handleArchive = async (customer: Customer) => {
    if (!window.confirm(`Are you sure you want to archive customer "${customer.name}"?`)) {
      return;
    }
    try {
      await archiveMutation.mutateAsync(customer.id);
    } catch (err) {
      console.error("Failed to archive customer", err);
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Customer Directory
          </h1>
          <p className="text-sm text-slate-500">
            Manage customer contact records for repeat sales, order association, and balance tracking.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/workspace/${orgId}/orders`}
            className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
          >
            View Orders
          </Link>
          {canCreate && (
            <button
              onClick={handleOpenCreate}
              className="inline-flex items-center rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
            >
              Add Customer
            </button>
          )}
        </div>
      </div>

      {/* Walk-in notice banner */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/80 p-3.5 text-xs text-blue-900 flex items-center gap-2.5">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-200 text-blue-800 font-bold text-xs">
          i
        </span>
        <div>
          <span className="font-semibold">Walk-in alternative:</span> Recording a customer profile is optional. Orders can be entered directly as anonymous walk-in sales.
        </div>
      </div>

      {/* Controls: Search & Status Filter */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search by customer name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm placeholder-slate-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 shadow-xs"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setStatusFilter("active")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              statusFilter === "active"
                ? "bg-slate-800 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setStatusFilter("archived")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              statusFilter === "archived"
                ? "bg-slate-800 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            Archived
          </button>
          <button
            onClick={() => setStatusFilter(undefined)}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              statusFilter === undefined
                ? "bg-slate-800 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Content Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading customers...</div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-rose-600">Failed to load customer list.</div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">No customers found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50/80">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Customer</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Contact</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Notes</th>
                  <th className="px-4 py-3 text-left font-semibold text-slate-600">Status</th>
                  <th className="px-4 py-3 text-right font-semibold text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {data.items.map((customer) => (
                  <tr key={customer.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="px-4 py-3 font-semibold text-slate-900">{customer.name}</td>
                    <td className="px-4 py-3 text-slate-600">
                      <div>{customer.phone || "—"}</div>
                      {customer.email && (
                        <div className="text-xs text-slate-400">{customer.email}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500 max-w-xs truncate">
                      {customer.notes || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize border ${
                          customer.status === "active"
                            ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                            : "bg-slate-100 text-slate-600 border-slate-200"
                        }`}
                      >
                        {customer.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end items-center gap-2">
                        <Link
                          href={`/workspace/${orgId}/orders?customerId=${customer.id}`}
                          className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 hover:bg-emerald-100"
                        >
                          New Order
                        </Link>
                        {canMutate && customer.status === "active" ? (
                          <>
                            <button
                              onClick={() => handleOpenEdit(customer)}
                              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-xs"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleArchive(customer)}
                              className="rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                            >
                              Archive
                            </button>
                          </>
                        ) : !canMutate ? (
                          <span className="text-xs text-slate-400 py-1">Read-only</span>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Customer Create/Edit Modal */}
      <CustomerModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        orgId={orgId}
        customer={selectedCustomer}
        token={token}
      />
    </div>
  );
}
