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
    <div className="space-y-6 p-6 max-w-[1600px] mx-auto">
      {/* Top Executive Header & Primary Actions */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display-lg text-2xl lg:text-3xl font-semibold tracking-tight text-on-surface">
            Customer Directory
          </h1>
          <p className="font-body-md text-sm text-on-surface-variant max-w-3xl mt-1">
            Manage customer names and optional contact details. Orders and payments can be linked to a customer or recorded as walk-in.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            href={`/workspace/${orgId}/orders`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3.5 py-2 font-body-sm text-sm font-medium text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[18px] text-outline">shopping_bag</span>
            <span>View Orders</span>
          </Link>
          {canCreate && (
            <button
              onClick={handleOpenCreate}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-body-sm text-sm font-medium text-on-primary shadow-sm hover:bg-primary-container active:scale-[0.99] transition-all"
            >
              <span className="material-symbols-outlined text-[18px]">person_add</span>
              <span>Add Customer</span>
            </button>
          )}
        </div>
      </div>

      {/* Customer count */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-surface-container-lowest p-5 rounded-xl shadow-xs border border-surface-container-high/60 flex items-start justify-between">
          <div className="space-y-1">
            <span className="font-label-caps text-xs uppercase text-on-surface-variant tracking-wider">
              Customers (current filter)
            </span>
            <div className="font-data-metric text-2xl font-bold text-on-surface">
              {data ? data.total : "—"}
            </div>
          </div>
          <div className="w-9 h-9 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-[20px]">groups</span>
          </div>
        </div>
      </div>

      {/* Walk-in notice banner */}
      <div className="rounded-xl border border-secondary/20 bg-surface-container-low p-4 text-xs text-on-surface flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-[18px]">info</span>
          </div>
          <div>
            <span className="font-semibold text-on-surface">Walk-in alternative:</span>{" "}
            <span className="text-on-surface-variant">
              Recording a customer profile is optional. Orders can be entered directly as anonymous walk-in sales.
            </span>
          </div>
        </div>
      </div>

      {/* Controls: Search & Status Filter */}
      <div className="bg-surface-container-lowest p-4 rounded-xl shadow-xs border border-surface-container-high/60 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-md">
          <span className="material-symbols-outlined absolute left-3 top-2.5 text-outline text-[18px]">
            search
          </span>
          <input
            type="text"
            placeholder="Search by customer name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="block w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest pl-9 pr-3 py-2 font-body-sm text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
          />
        </div>
        <div className="flex items-center p-1 rounded-lg bg-surface-container-low border border-surface-container-high/60">
          <button
            onClick={() => setStatusFilter("active")}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
              statusFilter === "active"
                ? "bg-surface-container-lowest text-primary shadow-xs"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setStatusFilter("archived")}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
              statusFilter === "archived"
                ? "bg-surface-container-lowest text-primary shadow-xs"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Archived
          </button>
          <button
            onClick={() => setStatusFilter(undefined)}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
              statusFilter === undefined
                ? "bg-surface-container-lowest text-primary shadow-xs"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Content Table */}
      <div className="overflow-hidden rounded-xl border border-surface-container-high/60 bg-surface-container-lowest shadow-xs">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">Loading customers...</div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-error">Failed to load customer list.</div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">No customers found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low text-on-surface-variant font-label-caps text-xs uppercase h-10 select-none border-b border-surface-container-high/60">
                  <th className="px-4 py-3 font-semibold">Customer</th>
                  <th className="px-4 py-3 font-semibold">Contact</th>
                  <th className="px-4 py-3 font-semibold">Notes</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low font-body-md text-sm text-on-surface">
                {data.items.map((customer) => {
                  const initials = customer.name
                    ? customer.name
                        .split(" ")
                        .map((n) => n[0])
                        .slice(0, 2)
                        .join("")
                        .toUpperCase()
                    : "CU";

                  return (
                    <tr
                      key={customer.id}
                      className="hover:bg-surface-container-low/60 transition-colors group"
                    >
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-surface-container-high text-primary font-semibold flex items-center justify-center text-sm shrink-0">
                            {initials}
                          </div>
                          <div className="flex flex-col min-w-0">
                            <span className="font-semibold text-on-surface truncate">
                              {customer.name}
                            </span>
                            <span className="font-data-badge text-xs text-outline">
                              ID: {customer.id.slice(0, 8)}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex flex-col">
                          <span className="font-data-cell text-sm text-on-surface">
                            {customer.phone || "—"}
                          </span>
                          {customer.email && (
                            <span className="text-xs text-on-surface-variant">{customer.email}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-on-surface-variant max-w-xs truncate">
                        {customer.notes || "—"}
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-data-badge text-xs font-semibold capitalize ${
                            customer.status === "active"
                              ? "bg-tertiary-container/15 text-tertiary"
                              : "bg-surface-container-high text-on-surface-variant"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              customer.status === "active" ? "bg-tertiary" : "bg-outline"
                            }`}
                          ></span>
                          {customer.status}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <div className="flex justify-end items-center gap-2">
                          <Link
                            href={`/workspace/${orgId}/orders?customerId=${customer.id}`}
                            className="inline-flex items-center gap-1 rounded-lg border border-primary/20 bg-primary/5 px-2.5 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition-colors"
                          >
                            <span className="material-symbols-outlined text-[14px]">add_shopping_cart</span>
                            <span>New Order</span>
                          </Link>
                          {canMutate && customer.status === "active" ? (
                            <>
                              <button
                                onClick={() => handleOpenEdit(customer)}
                                className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-2.5 py-1 text-xs font-medium text-on-surface hover:bg-surface-container-high shadow-xs transition-colors"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => handleArchive(customer)}
                                className="rounded-lg border border-error/20 bg-error/5 px-2.5 py-1 text-xs font-medium text-error hover:bg-error/10 transition-colors"
                              >
                                Archive
                              </button>
                            </>
                          ) : !canMutate ? (
                            <span className="text-xs text-on-surface-variant py-1">Read-only</span>
                          ) : null}
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
