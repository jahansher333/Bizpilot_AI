"use client";

import React, { useEffect, useRef, useState } from "react";
import { Order, orderVoidSchema } from "@/lib/schemas/orders";
import { useVoidOrder } from "@/hooks/use-orders";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

interface OrderVoidModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: Order | null;
  orgId: string;
  token?: string;
}

/** Design "33 · Confirmation flows": destructive, focus starts on the safe button. Owner-only (backend enforced). */
export function OrderVoidModal({ isOpen, onClose, order, orgId, token }: OrderVoidModalProps) {
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const voidMutation = useVoidOrder(orgId, token);
  const { notify } = useToast();

  useEffect(() => {
    if (isOpen) {
      setReason("");
      setFormError(null);
    }
  }, [isOpen, order?.id]);

  if (!order) return null;

  const units = (order.items ?? []).reduce((sum, it) => sum + it.quantity, 0);

  async function confirm() {
    if (!order) return;
    setFormError(null);
    const parsed = orderVoidSchema.safeParse({ reason });
    if (!parsed.success) {
      setFormError(parsed.error.issues[0].message);
      return;
    }
    try {
      await voidMutation.mutateAsync({
        orderId: order.id,
        payload: parsed.data,
        idempotencyKey: `web-void-${order.id}-${Date.now()}`,
      });
      notify({ title: `Order ${order.order_number} voided`, description: units > 0 ? `${units} units returned to stock.` : undefined });
      onClose();
    } catch (err) {
      setFormError(err instanceof Error && err.message ? err.message : "Couldn’t void the order.");
    }
  }

  return (
    <Modal
      open={isOpen}
      tone="danger"
      title={`Void order ${order.order_number}?`}
      description="It stays in your records, marked Voided, and stops counting toward sales. Its items go back into stock. This can’t be undone."
      onClose={onClose}
      initialFocusRef={cancelRef}
      footer={
        <>
          <button ref={cancelRef} type="button" className="btn btn-secondary" onClick={onClose} disabled={voidMutation.isPending}>
            Keep order
          </button>
          <button type="button" className="btn btn-danger" onClick={confirm} disabled={voidMutation.isPending} aria-busy={voidMutation.isPending}>
            {voidMutation.isPending && <span className="spinner" />}
            Void order
          </button>
        </>
      }
    >
      <div className="field">
        <label className="label" htmlFor="void-reason">
          Reason <span className="opt">· required, shown in history</span>
        </label>
        <textarea
          id="void-reason"
          className="input"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Duplicate entry"
          aria-invalid={!!formError}
          aria-describedby={formError ? "void-error" : undefined}
          style={{ height: "auto", paddingTop: 8, paddingBottom: 8 }}
        />
      </div>
      <p className="t-caption">Payments recorded against this order stay recorded. Void or correct them separately in Payments.</p>
      {formError && (
        <div className="alert a-danger" role="alert" id="void-error">
          {formError}
        </div>
      )}
    </Modal>
  );
}
