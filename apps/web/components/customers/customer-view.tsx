"use client";

import React, { useState } from "react";
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
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Customer Directory
          </h1>
          <p className="text-sm text-gray-500">
            Manage customer contact records for repeat sales, order association, and balance tracking.
          </p>
        </div>
        {canCreate && (
          <div className="flex gap-2">
            <button
              onClick={handleOpenCreate}
              className="inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none"
            >
              Add Customer
            </button>
          </div>
        )}
      </div>

      {/* Walk-in notice banner */}
      <div className="rounded-md border border-blue-100 bg-blue-50 p-3 text-xs text-blue-800">
        <span className="font-semibold">Walk-in alternative:</span> Recording a customer profile is optional. Orders can be entered directly as anonymous walk-in sales.
      </div>

      {/* Controls: Search & Status Filter */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Search by customer name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setStatusFilter("active")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              statusFilter === "active"
                ? "bg-indigo-50 text-indigo-700 font-semibold"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setStatusFilter("archived")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              statusFilter === "archived"
                ? "bg-indigo-50 text-indigo-700 font-semibold"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            Archived
          </button>
          <button
            onClick={() => setStatusFilter(undefined)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              statusFilter === undefined
                ? "bg-indigo-50 text-indigo-700 font-semibold"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="py-12 text-center text-sm text-gray-500">
            Loading customers...
          </div>
        ) : error ? (
          <div className="py-12 text-center text-sm text-red-600">
            Failed to load customers.
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-500">
            No customer records found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
              <thead className="bg-gray-50 text-xs font-medium uppercase tracking-wider text-gray-500">
                <tr>
                  <th scope="col" className="px-6 py-3">Customer Name</th>
                  <th scope="col" className="px-6 py-3">Phone</th>
                  <th scope="col" className="px-6 py-3">Email</th>
                  <th scope="col" className="px-6 py-3">Notes</th>
                  <th scope="col" className="px-6 py-3">Status</th>
                  <th scope="col" className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {data.items.map((cust) => (
                  <tr key={cust.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-4 font-medium text-gray-900">
                      {cust.name}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-gray-600">
                      {cust.phone || <span className="text-gray-300 italic">None</span>}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-gray-600">
                      {cust.email || <span className="text-gray-300 italic">None</span>}
                    </td>
                    <td className="max-w-xs truncate px-6 py-4 text-gray-500">
                      {cust.notes || <span className="text-gray-300 italic">—</span>}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      {cust.status === "active" ? (
                        <span className="inline-flex rounded-full bg-green-100 px-2 text-xs font-semibold leading-5 text-green-800">
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex rounded-full bg-gray-100 px-2 text-xs font-semibold leading-5 text-gray-800">
                          Archived
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-xs font-medium space-x-2">
                      {canMutate && cust.status === "active" && (
                        <>
                          <button
                            onClick={() => handleOpenEdit(cust)}
                            className="text-indigo-600 hover:text-indigo-900"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleArchive(cust)}
                            className="text-red-600 hover:text-red-900"
                          >
                            Archive
                          </button>
                        </>
                      )}
                      {!canMutate && (
                        <span className="text-gray-400 italic">Read-only</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Customer Modal */}
      {isModalOpen && (
        <CustomerModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          orgId={orgId}
          customer={selectedCustomer}
          token={token}
        />
      )}
    </div>
  );
}
