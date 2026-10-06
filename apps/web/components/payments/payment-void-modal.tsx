"use client";

import React, { useEffect, useRef, useState } from "react";
import { useVoidPayment } from "@/hooks/use-payments";
import { Payment, paymentVoidSchema } from "@/lib/schemas/payments";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

interface PaymentVoidModalProps {
  isOpen: boolean;
  onClose: () => void;
  payment: Payment | null;
  orgId: string;
  token?: string;
}

/** Destructive: focus starts on the safe button. Owner-only (backend payments:void). */
export function PaymentVoidModal({ isOpen, onClose, payment, orgId, token }: PaymentVoidModalProps) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const voidMutation = useVoidPayment(orgId, token);
  const { notify } = useToast();

  useEffect(() => {
    if (isOpen) {
      setReason("");
      setError(null);
    }
  }, [isOpen, payment?.id]);

  if (!payment) return null;

  async function confirm() {
    if (!payment) return;
    setError(null);
    const parsed = paymentVoidSchema.safeParse({ reason });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return;
    }
    try {
      await voidMutation.mutateAsync({ paymentId: payment.id, payload: parsed.data, idempotencyKey: `web-void-${payment.id}-${Date.now()}` });
      notify({ title: `Payment ${payment.payment_number} voided` });
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t void the payment.");
    }
  }

  return (
    <Modal
      open={isOpen}
      tone="danger"
      title={`Void payment ${payment.payment_number}?`}
      description="It stays in your records, marked Voided, and stops counting toward collections and customer balances. This can’t be undone."
      onClose={onClose}
      initialFocusRef={keepRef}
      footer={
        <>
          <button ref={keepRef} type="button" className="btn btn-secondary" onClick={onClose} disabled={voidMutation.isPending}>
            Keep payment
          </button>
          <button type="button" className="btn btn-danger" onClick={() => void confirm()} disabled={voidMutation.isPending} aria-busy={voidMutation.isPending}>
            {voidMutation.isPending && <span className="spinner" />}
            Void payment
          </button>
        </>
      }
    >
      <div className="field">
        <label className="label" htmlFor="pv-reason">
          Reason <span className="opt">· required, shown in history</span>
        </label>
        <textarea
          id="pv-reason"
          className="input"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Recorded twice"
          aria-invalid={!!error}
          aria-describedby={error ? "pv-error" : undefined}
          style={{ height: "auto", paddingTop: 8, paddingBottom: 8 }}
        />
      </div>
      {error && (
        <div className="alert a-danger" role="alert" id="pv-error">
          {error}
        </div>
      )}
    </Modal>
  );
}
