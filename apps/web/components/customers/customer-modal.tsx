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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
    >
      <div className="w-full max-w-lg rounded-2xl bg-surface-container-lowest p-6 shadow-xl border border-surface-container-high/60 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-semibold">
                <span className="material-symbols-outlined text-[18px]">
                  {isEditing ? "edit" : "person_add"}
                </span>
              </div>
              <h2 id="customer-modal-title" className="font-headline-sm text-lg font-bold text-on-surface">
                {isEditing ? "Edit Customer" : "Add Customer"}
              </h2>
            </div>
            <p className="text-xs text-on-surface-variant">
              {isEditing
                ? "Update contact details and preferences for this customer profile."
                : "Record a new customer profile. Phone numbers must be unique within active customers."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-on-surface-variant hover:text-on-surface p-1 rounded-lg hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {error && (
          <div role="alert" className="mt-4 rounded-lg bg-error-container/15 border border-error/20 p-3 text-xs text-error font-medium flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] shrink-0">error</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="mt-5 space-y-4">
          <div>
            <label htmlFor="customer-name" className="block text-xs font-semibold uppercase font-label-caps text-on-surface-variant tracking-wider">
              Customer Name <span className="text-error">*</span>
            </label>
            <input
              id="customer-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Tariq Khan, Al-Rehman Traders"
              className="mt-1.5 block w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
              required
            />
          </div>

          <div>
            <label htmlFor="customer-phone" className="block text-xs font-semibold uppercase font-label-caps text-on-surface-variant tracking-wider">
              Phone Number
            </label>
            <input
              id="customer-phone"
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="e.g. 0300-1234567"
              className="mt-1.5 block w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all font-data-cell"
            />
            <p className="mt-1 text-[11px] text-outline">
              Unique for active customers. Digits and Pakistani +92 formats supported.
            </p>
          </div>

          <div>
            <label htmlFor="customer-email" className="block text-xs font-semibold uppercase font-label-caps text-on-surface-variant tracking-wider">
              Email Address
            </label>
            <input
              id="customer-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. customer@example.com"
              className="mt-1.5 block w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
            />
          </div>

          <div>
            <label htmlFor="customer-notes" className="block text-xs font-semibold uppercase font-label-caps text-on-surface-variant tracking-wider">
              Notes
            </label>
            <textarea
              id="customer-notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes or delivery preferences..."
              className="mt-1.5 block w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
            />
          </div>

          <div className="mt-6 flex items-center justify-end gap-2.5 pt-2 border-t border-surface-container-low">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-outline-variant/40 px-4 py-2 font-body-sm text-sm font-medium text-on-surface hover:bg-surface-container-high transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-lg bg-primary px-4 py-2 font-body-sm text-sm font-medium text-on-primary hover:bg-primary-container active:scale-[0.99] transition-all shadow-sm disabled:opacity-50"
            >
              {isPending ? "Saving..." : isEditing ? "Save Changes" : "Create Customer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
