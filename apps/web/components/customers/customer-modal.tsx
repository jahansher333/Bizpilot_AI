"use client";

import React, { useEffect, useState } from "react";
import {
  Customer,
  customerCreateSchema,
  customerUpdateSchema,
} from "@/lib/schemas/customers";
import { useCreateCustomer, useUpdateCustomer } from "@/hooks/use-customers";

interface CustomerModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  customer?: Customer | null;
  token?: string;
}

export function CustomerModal({
  isOpen,
  onClose,
  orgId,
  customer,
  token,
}: CustomerModalProps) {
  const isEditing = Boolean(customer);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreateCustomer(orgId, token);
  const updateMutation = useUpdateCustomer(orgId, token);
  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (customer) {
      setName(customer.name);
      setPhone(customer.phone || "");
      setEmail(customer.email || "");
      setNotes(customer.notes || "");
    } else {
      setName("");
      setPhone("");
      setEmail("");
      setNotes("");
    }
    setError(null);
  }, [customer, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (isEditing && customer) {
      const parsed = customerUpdateSchema.safeParse({
        name,
        phone: phone || undefined,
        email: email || undefined,
        notes: notes || undefined,
      });

      if (!parsed.success) {
        setError(parsed.error.issues[0]?.message || "Validation failed");
        return;
      }

      try {
        await updateMutation.mutateAsync({
          customerId: customer.id,
          payload: parsed.data,
        });
        onClose();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to update customer";
        setError(msg);
      }
    } else {
      const parsed = customerCreateSchema.safeParse({
        name,
        phone: phone || undefined,
        email: email || undefined,
        notes: notes || undefined,
      });

      if (!parsed.success) {
        setError(parsed.error.issues[0]?.message || "Validation failed");
        return;
      }

      try {
        await createMutation.mutateAsync(parsed.data);
        onClose();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to create customer";
        setError(msg);
      }
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="customer-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 id="customer-modal-title" className="text-xl font-bold text-gray-900">
          {isEditing ? "Edit Customer" : "Add Customer"}
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          {isEditing
            ? "Update contact details and preferences for this customer."
            : "Record a new customer profile. Phone numbers must be unique within active customers."}
        </p>

        {error && (
          <div role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
          <div>
            <label htmlFor="customer-name" className="block text-sm font-medium text-gray-700">
              Customer Name <span className="text-red-500">*</span>
            </label>
            <input
              id="customer-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Tariq Khan, Al-Rehman Traders"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
              required
            />
          </div>

          <div>
            <label htmlFor="customer-phone" className="block text-sm font-medium text-gray-700">
              Phone Number
            </label>
            <input
              id="customer-phone"
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="e.g. 0300-1234567"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
            />
            <p className="mt-1 text-xs text-gray-400">
              Unique for active customers. Digits and Pakistani +92 formats supported.
            </p>
          </div>

          <div>
            <label htmlFor="customer-email" className="block text-sm font-medium text-gray-700">
              Email Address
            </label>
            <input
              id="customer-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. customer@example.com"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
            />
          </div>

          <div>
            <label htmlFor="customer-notes" className="block text-sm font-medium text-gray-700">
              Notes
            </label>
            <textarea
              id="customer-notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes or delivery preferences..."
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
            />
          </div>

          <div className="mt-6 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none disabled:opacity-50"
            >
              {isPending ? "Saving..." : isEditing ? "Save Changes" : "Create Customer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
