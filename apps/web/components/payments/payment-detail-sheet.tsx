"use client";

import React from "react";
import Link from "next/link";
import { usePayment } from "@/hooks/use-payments";
import { useOrder } from "@/hooks/use-orders";
import { useOptionalAuth } from "@/hooks/use-auth";
import { PAYMENT_CHANNEL_LABEL, Payment } from "@/lib/schemas/payments";
import { Icon } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { Sheet } from "@/components/ui/sheet";
import { RecordStatusBadge } from "@/components/finance/record-meta";
import { orderWhen, useCustomerNames, WALK_IN } from "@/components/orders/order-meta";

interface PaymentDetailSheetProps {
  payment: Payment | null;
  onClose: () => void;
  orgId: string;
  token?: string;
  canCorrect: boolean;
  canVoid: boolean;
  onCorrect: (p: Payment) => void;
  onVoid: (p: Payment) => void;
  onOpenPayment: (p: Payment) => void;
}

/** Design "21 · Payment detail" sheet: the record, its links and its correction history. */
export function PaymentDetailSheet({ payment, onClose, orgId, token, canCorrect, canVoid, onCorrect, onVoid, onOpenPayment }: PaymentDetailSheetProps) {
  const p = payment;
  const names = useCustomerNames(orgId, token);
  const order = useOrder(orgId, p?.order_id ?? "", token);
  const replacement = usePayment(orgId, p?.replaced_by_payment_id ?? "", token);
  const original = usePayment(orgId, p?.corrects_payment_id ?? "", token);
  const currentUserId = useOptionalAuth()?.user?.id;
  const base = `/workspace/${orgId}`;

  if (!p) return null;
  const active = p.status === "active";

  const rows: { label: string; value: React.ReactNode }[] = [
    { label: "Customer", value: p.customer_id ? <Link className="link" href={`${base}/customers/${p.customer_id}`}>{names.get(p.customer_id) ?? "Customer"}</Link> : WALK_IN },
    { label: "Related order", value: p.order_id ? <Link className="link mono" href={`${base}/orders/${p.order_id}`}>{order.data?.order_number ?? "Open order"}</Link> : "—" },
    { label: "Method", value: PAYMENT_CHANNEL_LABEL[p.channel] ?? p.channel },
    ...(p.external_reference ? [{ label: "Reference", value: <span className="mono">{p.external_reference}</span> }] : []),
    ...(p.account_label ? [{ label: "Account", value: p.account_label }] : []),
    { label: "Date", value: orderWhen(p.received_at) },
    ...(currentUserId && p.created_by_user_id === currentUserId ? [{ label: "Recorded by", value: "You" }] : []),
  ];

  return (
    <Sheet
      open={!!p}
      title={p.payment_number}
      onClose={onClose}
      footer={
        active && (canCorrect || canVoid) ? (
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, width: "100%" }}>
            {canVoid ? (
              <button type="button" className="btn btn-danger-outline" onClick={() => onVoid(p)}>
                <Icon name="ban" />
                Void payment…
              </button>
            ) : (
              <span />
            )}
            {canCorrect && (
              <button type="button" className="btn btn-secondary" onClick={() => onCorrect(p)}>
                <Icon name="edit" />
                Correct payment
              </button>
            )}
          </div>
        ) : active ? (
          <span className="t-caption">Only Owners and Managers can correct or void payments.</span>
        ) : undefined
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "8px 0 4px" }}>
        <RecordStatusBadge status={p.status} />
        <Money amountMinor={p.amount_minor} currency={p.currency_code} className={active ? "" : "struck"} style={{ font: "600 40px/46px var(--font)", letterSpacing: "-0.03em" }} />
      </div>

      {p.status === "corrected" && (
        <div className="alert a-warning">
          <Icon name="edit" />
          <span style={{ flex: 1 }}>Corrected. It no longer counts; the replacement holds the right details.</span>
          {replacement.data && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenPayment(replacement.data!)}>
              Open {replacement.data.payment_number}
            </button>
          )}
        </div>
      )}
      {p.status === "voided" && (
        <div className="alert a-danger">
          <Icon name="ban" />
          <span>Voided. Kept for your records; it doesn’t count toward collections or balances.</span>
        </div>
      )}
      {p.corrects_payment_id && (
        <div className="alert a-neutral">
          <Icon name="info" />
          <span style={{ flex: 1 }}>Replaces {original.data?.payment_number ?? "an earlier payment"}, which is kept and marked Corrected.</span>
          {original.data && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenPayment(original.data!)}>
              Open {original.data.payment_number}
            </button>
          )}
        </div>
      )}

      <dl className="well" style={{ margin: 0, padding: "4px 16px" }}>
        {rows.map((r, i) => (
          <div key={r.label} className="t-body-sm" style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "10px 0", borderBottom: i < rows.length - 1 ? "1px solid var(--border)" : undefined }}>
            <dt className="secondary">{r.label}</dt>
            <dd style={{ margin: 0, textAlign: "right" }}>{r.value}</dd>
          </div>
        ))}
      </dl>

      {p.notes && (
        <div className="field">
          <span className="label">Note</span>
          <p className="t-body-sm">{p.notes}</p>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span className="t-h4">History</span>
        <ol className="tl">
          {p.status === "voided" && p.voided_at && (
            <li className="tl-row">
              <span className="tl-dot bad">
                <Icon name="ban" />
              </span>
              <div style={{ paddingTop: 3 }}>
                <div className="t-h4">Voided</div>
                <div className="t-caption">{orderWhen(p.voided_at)}</div>
              </div>
            </li>
          )}
          {p.status === "corrected" && replacement.data && (
            <li className="tl-row">
              <span className="tl-dot warn">
                <Icon name="edit" />
              </span>
              <div style={{ paddingTop: 3 }}>
                <div className="t-h4">Corrected → {replacement.data.payment_number}</div>
                <div className="t-caption">{orderWhen(replacement.data.created_at)}</div>
              </div>
            </li>
          )}
          <li className="tl-row">
            <span className="tl-dot in">
              <Icon name="check" />
            </span>
            <div style={{ paddingTop: 3 }}>
              <div className="t-h4">{p.corrects_payment_id ? "Replacement · recorded" : "Original · recorded"}</div>
              <div className="t-caption">{orderWhen(p.created_at)}</div>
            </div>
          </li>
        </ol>
        <p className="t-caption">Corrections and voids appear here and keep the original visible.</p>
      </div>
    </Sheet>
  );
}
