"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { usePayments } from "@/hooks/use-payments";
import { useOrders } from "@/hooks/use-orders";
import { useDashboard } from "@/hooks/use-dashboard";
import { PAYMENT_CHANNEL_LABEL, Payment, paymentChannelEnum } from "@/lib/schemas/payments";
import { Icon } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { RecordStatusBadge } from "@/components/finance/record-meta";
import { orderWhen, useCustomerNames, WALK_IN } from "@/components/orders/order-meta";
import { PaymentRecordSheet } from "@/components/payments/payment-record-sheet";
import { PaymentDetailSheet } from "@/components/payments/payment-detail-sheet";
import { PaymentCorrectModal } from "@/components/payments/payment-correct-modal";
import { PaymentVoidModal } from "@/components/payments/payment-void-modal";

interface PaymentsViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
  initialOrderId?: string;
  initialCustomerId?: string;
  /** Opened from "Record payment" elsewhere: open the form pre-filled instead of filtering the list. */
  startRecording?: boolean;
}

type StatusFilter = "all" | "active" | "corrected" | "voided";
const STATUSES: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Recorded" },
  { key: "corrected", label: "Corrected" },
  { key: "voided", label: "Voided" },
];
const PAGE_SIZE = 50;
const METRIC = { font: "600 24px/32px var(--font)" } as const;

/** Design canvas "20–22 · Payments". Record: all roles. Correct: Owner/Manager. Void: Owner. */
export function PaymentsView({ orgId, userRole = "staff", token, initialOrderId, initialCustomerId, startRecording = false }: PaymentsViewProps) {
  const canCorrect = userRole === "owner" || userRole === "manager";
  const canVoid = userRole === "owner";
  const filterOrderId = startRecording ? undefined : initialOrderId;
  const filterCustomerId = startRecording ? undefined : initialCustomerId;

  const [status, setStatus] = useState<StatusFilter>("all");
  const [channel, setChannel] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [recordOpen, setRecordOpen] = useState(startRecording);
  const [detail, setDetail] = useState<Payment | null>(null);
  const [correcting, setCorrecting] = useState<Payment | null>(null);
  const [voiding, setVoiding] = useState<Payment | null>(null);

  const { data, isLoading, error, refetch } = usePayments(
    orgId,
    { status: status === "all" ? undefined : status, channel: channel === "all" ? undefined : channel, customerId: filterCustomerId, orderId: filterOrderId, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
    token
  );
  const today = useDashboard(orgId, { period: "today" }, token);
  const month = useDashboard(orgId, { period: "this_month" }, token);
  const names = useCustomerNames(orgId, token);
  const { data: orders } = useOrders(orgId, { limit: 100 }, token);
  const orderNumbers = useMemo(() => new Map((orders?.items ?? []).map((o) => [o.id, o.order_number])), [orders]);

  const base = `/workspace/${orgId}`;
  const payments = data?.items ?? [];
  const filtered = status !== "all" || channel !== "all";
  const customerName = (p: Payment) => (p.customer_id ? (names.get(p.customer_id) ?? "Customer") : WALK_IN);

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Payments</h1>
          <p className="t-body secondary">Money received from customers.</p>
        </div>
        <div className="ph-a">
          <button type="button" className="btn btn-primary" onClick={() => setRecordOpen(true)}>
            <Icon name="plus" />
            Record payment
          </button>
        </div>
      </div>

      <div className="alert a-info">
        <Icon name="info" />
        <div>
          <span className="a-t">Operational receipt recording.</span> Payments are recorded as you report them. Bank reconciliation is not part of this workspace yet.
        </div>
      </div>

      <section className="sum-grid" aria-label="Payment summary">
        <div className="card metric">
          <span className="metric-l">Collected today</span>
          {today.data ? <Money amountMinor={today.data.payments.total_collected_minor} currency={today.data.payments.currency_code} style={METRIC} /> : <span className="num" style={METRIC}>—</span>}
          <span className="metric-c">{today.data ? `${today.data.payments.payment_count} ${today.data.payments.payment_count === 1 ? "payment" : "payments"}` : "Voided excluded"}</span>
        </div>
        <div className="card metric">
          <span className="metric-l">This month</span>
          {month.data ? <Money amountMinor={month.data.payments.total_collected_minor} currency={month.data.payments.currency_code} style={METRIC} /> : <span className="num" style={METRIC}>—</span>}
          <span className="metric-c">Voided and corrected excluded</span>
        </div>
        <div className="card metric">
          <span className="metric-l">Payment count</span>
          <span className="num" style={METRIC}>
            {month.data?.payments.payment_count ?? "—"}
          </span>
          <span className="metric-c">This month</span>
        </div>
      </section>

      {(filterOrderId || filterCustomerId) && (
        <div className="alert a-neutral">
          <Icon name={filterOrderId ? "orders" : "customers"} />
          <span style={{ flex: 1 }}>
            Showing payments for{" "}
            <b>{filterOrderId ? `order ${orderNumbers.get(filterOrderId) ?? ""}`.trim() : (names.get(filterCustomerId!) ?? "one customer")}</b>
          </span>
          <Link className="btn btn-secondary btn-sm" href={`${base}/payments`}>
            Show all payments
          </Link>
        </div>
      )}

      <div className="toolbar">
        <div className="seg" role="group" aria-label="Status">
          {STATUSES.map((s) => (
            <button
              key={s.key}
              type="button"
              aria-pressed={status === s.key}
              onClick={() => {
                setStatus(s.key);
                setPage(0);
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} role="group" aria-label="Method">
          <button
            type="button"
            className="chip"
            aria-pressed={channel === "all"}
            onClick={() => {
              setChannel("all");
              setPage(0);
            }}
          >
            All methods
          </button>
          {paymentChannelEnum.options.map((c) => (
            <button
              key={c}
              type="button"
              className="chip"
              aria-pressed={channel === c}
              onClick={() => {
                setChannel(c);
                setPage(0);
              }}
            >
              {PAYMENT_CHANNEL_LABEL[c]}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorState title="Couldn’t load payments" message="Nothing was lost — check your connection, then try again." onRetry={() => void refetch()} />}

      {isLoading && (
        <div className="tbl-wrap" aria-busy="true" aria-label="Loading payments" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <Skeleton width={80} height={12} />
              <Skeleton width={180} height={12} />
              <Skeleton width={90} height={12} />
            </div>
          ))}
        </div>
      )}

      {data && payments.length === 0 && (
        <div className="card">
          {filtered ? (
            <EmptyState icon="payments" title="No payments match these filters" />
          ) : (
            <EmptyState
              icon="payments"
              title="No payments yet"
              description="Record money as you receive it — cash, bank transfer or wallet — and link it to an order to track what’s still owed."
              action={
                <button type="button" className="btn btn-primary" onClick={() => setRecordOpen(true)}>
                  Record payment
                </button>
              }
            />
          )}
        </div>
      )}

      {payments.length > 0 && (
        <>
          <div className="tbl-wrap desk-only fade-in">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Payment #</th>
                  <th>Customer</th>
                  <th>Order</th>
                  <th className="r">Amount</th>
                  <th>Method</th>
                  <th>Date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => {
                  const active = p.status === "active";
                  return (
                    <tr key={p.id} className={active ? "" : "is-void"}>
                      <td>
                        <button type="button" className={`link mono${active ? "" : " struck"}`} style={{ background: "none", border: 0, padding: 0, cursor: "pointer" }} onClick={() => setDetail(p)}>
                          {p.payment_number}
                        </button>
                      </td>
                      <td>{customerName(p)}</td>
                      <td className="mono muted">{p.order_id ? (orderNumbers.get(p.order_id) ?? "Order") : "—"}</td>
                      <td className="r">
                        <Money amountMinor={p.amount_minor} currency={p.currency_code} className={active ? "strong" : "strong struck"} />
                      </td>
                      <td>{PAYMENT_CHANNEL_LABEL[p.channel] ?? p.channel}</td>
                      <td className="muted">{orderWhen(p.received_at)}</td>
                      <td>
                        <RecordStatusBadge status={p.status} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {data && data.total > PAGE_SIZE && (
              <div className="pager">
                <span>
                  Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, data.total)} of {data.total}
                </span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button type="button" className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage((x) => x - 1)}>
                    Previous
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" disabled={(page + 1) * PAGE_SIZE >= data.total} onClick={() => setPage((x) => x + 1)}>
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>

          <ul className="only-sm" style={{ flexDirection: "column", gap: 8 }} aria-label="Payments">
            {payments.map((p) => {
              const active = p.status === "active";
              return (
                <li key={p.id}>
                  <button type="button" className="card" onClick={() => setDetail(p)} style={{ width: "100%", textAlign: "left", font: "inherit", color: "inherit", padding: "12px 14px", display: "flex", gap: 12, alignItems: "center", cursor: "pointer" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className={`mono strong${active ? "" : " struck"}`}>{p.payment_number}</div>
                      <div className="t-caption">
                        {customerName(p)} · {PAYMENT_CHANNEL_LABEL[p.channel] ?? p.channel} · {orderWhen(p.received_at)}
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                      <Money amountMinor={p.amount_minor} currency={p.currency_code} className={active ? "strong t-body-sm" : "strong t-body-sm struck"} />
                      <RecordStatusBadge status={p.status} />
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}

      <PaymentRecordSheet
        open={recordOpen}
        onClose={() => setRecordOpen(false)}
        orgId={orgId}
        token={token}
        initialOrderId={startRecording ? initialOrderId : filterOrderId}
        initialCustomerId={startRecording ? initialCustomerId : filterCustomerId}
      />
      <PaymentDetailSheet
        payment={correcting || voiding ? null : detail}
        onClose={() => setDetail(null)}
        orgId={orgId}
        token={token}
        canCorrect={canCorrect}
        canVoid={canVoid}
        onCorrect={(p) => setCorrecting(p)}
        onVoid={(p) => setVoiding(p)}
        onOpenPayment={(p) => setDetail(p)}
      />
      <PaymentCorrectModal isOpen={!!correcting} onClose={() => setCorrecting(null)} payment={correcting} orgId={orgId} token={token} onCorrected={(r) => setDetail(r)} />
      <PaymentVoidModal
        isOpen={!!voiding}
        onClose={() => {
          setVoiding(null);
          setDetail(null);
        }}
        payment={voiding}
        orgId={orgId}
        token={token}
      />
    </div>
  );
}
