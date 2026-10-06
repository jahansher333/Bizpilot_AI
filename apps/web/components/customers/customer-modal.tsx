"use client";

import React, { useEffect, useState } from "react";
import { Customer, customerCreateSchema, customerUpdateSchema } from "@/lib/schemas/customers";
import { useCreateCustomer, useUpdateCustomer } from "@/hooks/use-customers";
import { Modal } from "@/components/ui/modal";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

interface CustomerModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  customer?: Customer | null;
  token?: string;
  onSaved?: (customer: Customer) => void;
}

/** Add / edit customer. Only the name is required; walk-in sales need no customer at all. */
export function CustomerModal({ isOpen, onClose, orgId, customer, token, onSaved }: CustomerModalProps) {
  const isEditing = Boolean(customer);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const createMutation = useCreateCustomer(orgId, token);
  const updateMutation = useUpdateCustomer(orgId, token);
  const isPending = createMutation.isPending || updateMutation.isPending;
  const { notify } = useToast();

  useEffect(() => {
    if (!isOpen) return;
    setName(customer?.name ?? "");
    setPhone(customer?.phone ?? "");
    setEmail(customer?.email ?? "");
    setNotes(customer?.notes ?? "");
    setError(null);
  }, [customer, isOpen]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const raw = { name, phone: phone || undefined, email: email || undefined, notes: notes || undefined };
    try {
      if (isEditing && customer) {
        const parsed = customerUpdateSchema.safeParse(raw);
        if (!parsed.success) {
          setError(parsed.error.issues[0]?.message || "Check the details and try again");
          return;
        }
        const saved = await updateMutation.mutateAsync({ customerId: customer.id, payload: parsed.data });
        notify({ title: "Customer updated" });
        onSaved?.(saved);
      } else {
        const parsed = customerCreateSchema.safeParse(raw);
        if (!parsed.success) {
          setError(parsed.error.issues[0]?.message || "Check the details and try again");
          return;
        }
        const saved = await createMutation.mutateAsync(parsed.data);
        notify({ title: "Customer added", description: saved.name });
        onSaved?.(saved);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t save the customer.");
    }
  }

  return (
    <Modal
      open={isOpen}
      title={isEditing ? "Edit customer" : "Add customer"}
      description="Only the name is required. Phone numbers must be unique among active customers."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </button>
          <button type="submit" form="customer-form" className="btn btn-primary" disabled={isPending} aria-busy={isPending}>
            {isPending && <span className="spinner" />}
            {isEditing ? "Save changes" : "Add customer"}
          </button>
        </>
      }
    >
      <form id="customer-form" onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {error && (
          <div className="alert a-danger" role="alert">
            <Icon name="alert" />
            <div>{error}</div>
          </div>
        )}
        <div className="field">
          <label className="label" htmlFor="cust-name">
            Customer name
          </label>
          <input className="input" id="cust-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Bilal General Store" />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(180px, 100%), 1fr))", gap: 12 }}>
          <div className="field">
            <label className="label" htmlFor="cust-phone">
              Phone <span className="opt">· optional</span>
            </label>
            <input className="input num" id="cust-phone" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0300 1234567" />
          </div>
          <div className="field">
            <label className="label" htmlFor="cust-email">
              Email <span className="opt">· optional</span>
            </label>
            <input className="input" id="cust-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label className="label" htmlFor="cust-notes">
            Notes <span className="opt">· optional</span>
          </label>
          <textarea className="input" id="cust-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Area, delivery instructions, credit terms…" />
        </div>
      </form>
    </Modal>
  );
}
