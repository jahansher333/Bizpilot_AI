"use client";

import React, { useEffect, useRef, useState } from "react";
import { useCreatePayment, usePayments } from "@/hooks/use-payments";
import { useCustomers } from "@/hooks/use-customers";
import { useOrder, useOrders } from "@/hooks/use-orders";
import { PAYMENT_CHANNEL_LABEL, Payment, PaymentChannel, paymentCreateSchema } from "@/lib/schemas/payments";
import { newIdempotencyKey } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { Money, formatMinor } from "@/components/ui/money";
import { Sheet } from "@/components/ui/sheet";
import { useToast } from "@/components/ui/toast";
import { parseAmountMinor, pickedDateToIso, todayInput } from "@/components/finance/record-meta";
import { orderWhen } from "@/components/orders/order-meta";

interface PaymentRecordSheetProps {
  open: boolean;
  onClose: () => void;
  orgId: string;
  token?: string;
  initialOrderId?: string;
  initialCustomerId?: string;
}

const CHANNELS: PaymentChannel[] = ["cash", "bank_transfer", "digital", "other"];

/** Design "20 · Record payment" sheet. Every role may record payments (backend payments:create). */
export function PaymentRecordSheet({ open, onClose, orgId, token, initialOrderId, initialCustomerId }: PaymentRecordSheetProps) {
  const [amount, setAmount] = useState("");
  const [amountTouched, setAmountTouched] = useState(false);
  const [customerId, setCustomerId] = useState(initialCustomerId ?? "");
  const [orderId, setOrderId] = useState(initialOrderId ?? "");
  const [channel, setChannel] = useState<PaymentChannel>("cash");
  const [date, setDate] = useState(todayInput());
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Payment | null>(null);
  const idemKey = useRef(newIdempotencyKey());

  const { data: customers } = useCustomers(orgId, { status: "active", limit: 100 }, token);
  const { data: orders } = useOrders(orgId, { status: "active", customerId: customerId || undefined, limit: 100 }, token);
  const order = useOrder(orgId, orderId, token);
  const orderPayments = usePayments(orderId ? orgId : "", { orderId, limit: 100 }, token);
  const createMutation = useCreatePayment(orgId, token);
  const { notify } = useToast();

  useEffect(() => {
    if (!open) return;
    setAmount("");
    setAmountTouched(false);
    setCustomerId(initialCustomerId ?? "");
    setOrderId(initialOrderId ?? "");
    setChannel("cash");
    setDate(todayInput());
    setReference("");
    setNotes("");
    setError(null);
    setSaved(null);
    idemKey.current = newIdempotencyKey();
  }, [open, initialOrderId, initialCustomerId]);

  const paidOnOrder = orderId && orderPayments.data ? orderPayments.data.items.filter((p) => p.status === "active").reduce((s, p) => s + p.amount_minor, 0) : 0;
  const remaining = order.data ? Math.max(0, order.data.order_total_minor - paidOnOrder) : 0;

  // Linking an order fills in its customer and, until the amount is typed, what is still owed on it.
  useEffect(() => {
    if (!order.data || order.data.id !== orderId) return;
    if (!customerId && order.data.customer_id) setCustomerId(order.data.customer_id);
    if (!amountTouched && orderPayments.data && remaining > 0) setAmount(formatMinor(remaining));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order.data, orderPayments.data, orderId]);

  const amountMinor = parseAmountMinor(amount);
  const amountError = amountTouched && amount.trim() !== "" && amountMinor === null;
  const customerName = customers?.items.find((c) => c.id === customerId)?.name;

  function changed() {
    idemKey.current = newIdempotencyKey();
    setError(null);
  }

  async function save() {
    if (amountMinor === null) {
      setAmountTouched(true);
      setError("Enter an amount greater than 0.");
      return;
    }
    const parsed = paymentCreateSchema.safeParse({
      amount_minor: amountMinor,
      channel,
      customer_id: customerId || undefined,
      order_id: orderId || undefined,
      external_reference: reference.trim() || undefined,
      notes: notes.trim() || undefined,
      received_at: pickedDateToIso(date),
      currency_code: "PKR",
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check the payment details.");
      return;
    }
    try {
      const payment = await createMutation.mutateAsync({ payload: parsed.data, idempotencyKey: idemKey.current });
      setSaved(payment);
      notify({ title: "Payment recorded", description: `PKR ${formatMinor(payment.amount_minor)}${customerName ? ` from ${customerName}` : ""} · Dashboard updated` });
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t record the payment. Nothing was saved.");
    }
  }

  return (
    <Sheet
      open={open}
      title="Record payment"
      onClose={onClose}
      footer={
        saved ? (
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        ) : (
          <>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={createMutation.isPending}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={createMutation.isPending} aria-busy={createMutation.isPending}>
              {createMutation.isPending ? (
                <>
                  <span className="spinner" />
                  Recording…
                </>
              ) : amountMinor ? (
                `Record PKR ${formatMinor(amountMinor)}`
              ) : (
                "Record payment"
              )}
            </button>
          </>
        )
      }
    >
      {saved ? (
        <div role="status" style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 12, padding: "32px 0" }}>
          <span className="dlg-icon ok pop-in" style={{ width: 64, height: 64 }}>
            <Icon name="check" size="xl" className="check-anim" />
          </span>
          <h3 className="t-h2">Payment recorded</h3>
          <Money amountMinor={saved.amount_minor} currency={saved.currency_code} style={{ font: "600 30px/36px var(--font)" }} />
          <span className="t-body-sm secondary">
            {[customerName, PAYMENT_CHANNEL_LABEL[saved.channel], order.data?.order_number].filter(Boolean).join(" · ")}
          </span>
        </div>
      ) : (
        <>
          <div className="field">
            <label className="label" htmlFor="rp-amt">
              Amount
            </label>
            <div className={`ig lg${amountError ? " is-error" : ""}`}>
              <span className="pre" style={{ fontSize: 14, fontWeight: 600, color: "var(--text-secondary)" }}>
                PKR
              </span>
              <input
                id="rp-amt"
                className="num"
                inputMode="decimal"
                value={amount}
                onChange={(e) => {
                  changed();
                  setAmountTouched(true);
                  setAmount(e.target.value.replace(/[^\d.,]/g, ""));
                }}
                aria-invalid={amountError}
                aria-describedby="rp-amt-h"
              />
            </div>
            {amountError ? (
              <span className="err" id="rp-amt-h">
                <Icon name="alert" size="sm" />
                Enter an amount greater than 0
              </span>
            ) : order.data ? (
              <span className="hint" id="rp-amt-h">
                Order {order.data.order_number} total is PKR {formatMinor(order.data.order_total_minor)} ·{" "}
                {paidOnOrder > 0 ? `PKR ${formatMinor(paidOnOrder)} paid so far` : "nothing paid yet"}
              </span>
            ) : (
              <span className="hint" id="rp-amt-h">
                Money received, in rupees.
              </span>
            )}
          </div>

          <div className="field">
            <label className="label" htmlFor="rp-cust">
              Customer <span className="opt">· optional</span>
            </label>
            <select
              id="rp-cust"
              className="input"
              value={customerId}
              onChange={(e) => {
                changed();
                setCustomerId(e.target.value);
                if (order.data && e.target.value && order.data.customer_id !== e.target.value) setOrderId("");
              }}
            >
              <option value="">Walk-in / not linked</option>
              {customers?.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="label" htmlFor="rp-order">
              Related order <span className="opt">· optional</span>
            </label>
            <select
              id="rp-order"
              className="input"
              value={orderId}
              onChange={(e) => {
                changed();
                setOrderId(e.target.value);
                setAmountTouched(false);
                setAmount("");
              }}
            >
              <option value="">Not linked to an order</option>
              {order.data && !orders?.items.some((o) => o.id === order.data!.id) && (
                <option value={order.data.id}>
                  {order.data.order_number} · PKR {formatMinor(order.data.order_total_minor)}
                </option>
              )}
              {orders?.items.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.order_number} · PKR {formatMinor(o.order_total_minor)} · {orderWhen(o.ordered_at)}
                </option>
              ))}
            </select>
          </div>

          <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="label">Payment method</legend>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 6 }}>
              {CHANNELS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className="chip"
                  aria-pressed={channel === c}
                  onClick={() => {
                    changed();
                    setChannel(c);
                  }}
                  style={{ justifyContent: "center", borderRadius: 6, height: 38 }}
                >
                  {PAYMENT_CHANNEL_LABEL[c]}
                </button>
              ))}
            </div>
            <span className="hint">
              {channel === "digital" ? "JazzCash, Easypaisa or another wallet — add the transaction ID below." : channel === "other" ? "e.g. a cheque — add the cheque number below." : " "}
            </span>
          </fieldset>

          <div className="field">
            <label className="label" htmlFor="rp-date">
              Date received
            </label>
            <input
              id="rp-date"
              className="input"
              type="date"
              value={date}
              max={todayInput()}
              onChange={(e) => {
                changed();
                setDate(e.target.value);
              }}
            />
          </div>

          <div className="field">
            <label className="label" htmlFor="rp-ref">
              Reference <span className="opt">· optional</span>
            </label>
            <input
              id="rp-ref"
              className="input"
              value={reference}
              maxLength={100}
              onChange={(e) => {
                changed();
                setReference(e.target.value);
              }}
              placeholder="e.g. JazzCash TID, cheque no."
            />
          </div>

          <div className="field">
            <label className="label" htmlFor="rp-notes">
              Note <span className="opt">· optional</span>
            </label>
            <textarea
              id="rp-notes"
              className="input"
              rows={2}
              value={notes}
              maxLength={500}
              onChange={(e) => {
                changed();
                setNotes(e.target.value);
              }}
              style={{ height: "auto", paddingTop: 8, paddingBottom: 8 }}
            />
          </div>

          {error && (
            <div className="alert a-danger" role="alert">
              <Icon name="alert" />
              <span>{error}</span>
            </div>
          )}
        </>
      )}
    </Sheet>
  );
}
