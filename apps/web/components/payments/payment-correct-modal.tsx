"use client";

import React, { useEffect, useRef, useState } from "react";
import { useCorrectPayment } from "@/hooks/use-payments";
import { useCustomers } from "@/hooks/use-customers";
import { useOrders } from "@/hooks/use-orders";
import { PAYMENT_CHANNEL_LABEL, Payment, PaymentChannel, paymentChannelEnum, paymentCorrectSchema } from "@/lib/schemas/payments";
import { newIdempotencyKey } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { Money, formatMinor } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { parseAmountMinor } from "@/components/finance/record-meta";

interface PaymentCorrectModalProps {
  isOpen: boolean;
  onClose: () => void;
  payment: Payment | null;
  orgId: string;
  token?: string;
  onCorrected?: (replacement: Payment) => void;
}

/** Correction keeps the original (marked Corrected) and records a linked replacement. Owner/Manager. */
export function PaymentCorrectModal({ isOpen, onClose, payment, orgId, token, onCorrected }: PaymentCorrectModalProps) {
  const [amount, setAmount] = useState("");
  const [channel, setChannel] = useState<PaymentChannel>("cash");
  const [customerId, setCustomerId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const idemKey = useRef(newIdempotencyKey());

  const { data: customers } = useCustomers(orgId, { status: "active", limit: 100 }, token);
  const { data: orders } = useOrders(orgId, { status: "active", customerId: customerId || undefined, limit: 100 }, token);
  const correctMutation = useCorrectPayment(orgId, token);
  const { notify } = useToast();

  useEffect(() => {
    if (!isOpen || !payment) return;
    setAmount(formatMinor(payment.amount_minor));
    // Older records may carry a method the backend no longer accepts; fall back to Other.
    setChannel(paymentChannelEnum.safeParse(payment.channel).success ? (payment.channel as PaymentChannel) : "other");
    setCustomerId(payment.customer_id ?? "");
    setOrderId(payment.order_id ?? "");
    setReference(payment.external_reference ?? "");
    setReason("");
    setError(null);
    idemKey.current = newIdempotencyKey();
  }, [isOpen, payment]);

  if (!payment) return null;

  async function submit() {
    if (!payment) return;
    setError(null);
    const amountMinor = parseAmountMinor(amount);
    if (amountMinor === null) {
      setError("Enter an amount greater than 0.");
      return;
    }
    const parsed = paymentCorrectSchema.safeParse({
      reason,
      amount_minor: amountMinor,
      channel,
      customer_id: customerId || undefined,
      order_id: orderId || undefined,
      external_reference: reference.trim() || undefined,
      account_label: payment.account_label ?? undefined,
      notes: payment.notes ?? undefined,
      currency_code: payment.currency_code,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return;
    }
    try {
      const replacement = await correctMutation.mutateAsync({ paymentId: payment.id, payload: parsed.data, idempotencyKey: `web-correct-${idemKey.current}` });
      notify({ title: `Payment ${payment.payment_number} corrected`, description: `Replacement ${replacement.payment_number} recorded.` });
      onCorrected?.(replacement);
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t save the correction. Nothing was changed.");
    }
  }

  return (
    <Modal
      open={isOpen}
      wide
      title={`Correct payment ${payment.payment_number}`}
      description="The original stays in history, marked Corrected, and a replacement payment is recorded."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={correctMutation.isPending}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void submit()} disabled={correctMutation.isPending} aria-busy={correctMutation.isPending}>
            {correctMutation.isPending && <span className="spinner" />}
            Save correction
          </button>
        </>
      }
    >
      <div className="well t-body-sm" style={{ padding: "10px 14px", display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span className="secondary">
          Original · {PAYMENT_CHANNEL_LABEL[payment.channel] ?? payment.channel}
        </span>
        <Money amountMinor={payment.amount_minor} currency={payment.currency_code} className="struck" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))", gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="pc-amt">
            Correct amount
          </label>
          <div className="ig">
            <span className="pre">PKR</span>
            <input id="pc-amt" className="num" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.,]/g, ""))} />
          </div>
        </div>
        <div className="field">
          <label className="label" htmlFor="pc-method">
            Method
          </label>
          <select id="pc-method" className="input" value={channel} onChange={(e) => setChannel(e.target.value as PaymentChannel)}>
            {paymentChannelEnum.options.map((c) => (
              <option key={c} value={c}>
                {PAYMENT_CHANNEL_LABEL[c]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="pc-cust">
            Customer
          </label>
          <select id="pc-cust" className="input" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">Walk-in / not linked</option>
            {payment.customer_id && !customers?.items.some((c) => c.id === payment.customer_id) && <option value={payment.customer_id}>Current customer</option>}
            {customers?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="pc-order">
            Related order
          </label>
          <select id="pc-order" className="input" value={orderId} onChange={(e) => setOrderId(e.target.value)}>
            <option value="">Not linked to an order</option>
            {payment.order_id && !orders?.items.some((o) => o.id === payment.order_id) && <option value={payment.order_id}>Current order</option>}
            {orders?.items.map((o) => (
              <option key={o.id} value={o.id}>
                {o.order_number} · PKR {formatMinor(o.order_total_minor)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label className="label" htmlFor="pc-ref">
          Reference <span className="opt">· optional</span>
        </label>
        <input id="pc-ref" className="input" value={reference} maxLength={100} onChange={(e) => setReference(e.target.value)} />
      </div>
      <div className="field">
        <label className="label" htmlFor="pc-reason">
          Reason <span className="opt">· required, shown in history</span>
        </label>
        <input id="pc-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Amount typed wrong — it was 4,000" />
      </div>
      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <span>{error}</span>
        </div>
      )}
    </Modal>
  );
}
