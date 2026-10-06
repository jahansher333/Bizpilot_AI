"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useArchiveCustomer, useCustomer, useCustomerBalances } from "@/hooks/use-customers";
import { useOrders } from "@/hooks/use-orders";
import { usePayments } from "@/hooks/use-payments";
import { Order } from "@/lib/schemas/orders";
import { Payment } from "@/lib/schemas/payments";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";
import { Money } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { CustomerModal } from "@/components/customers/customer-modal";

interface CustomerDetailProps {
  orgId: string;
  customerId: string;
  userRole?: string;
  token?: string;
}

const CHANNEL: Record<string, string> = { cash: "Cash", bank_transfer: "Bank transfer", digital: "Digital wallet", other: "Other" };
const ORDER_STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "Completed", cls: "b-success" },
  corrected: { label: "Corrected", cls: "b-warning" },
  voided: { label: "Voided", cls: "b-danger" },
};
const PAYMENT_STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "Recorded", cls: "b-info" },
  corrected: { label: "Corrected", cls: "b-warning" },
  voided: { label: "Voided", cls: "b-danger" },
};

function when(iso: string) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

function since(iso: string) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", month: "short", year: "numeric" }).format(new Date(iso));
}

type Tab = "overview" | "orders" | "payments";

/** Design canvas "15 · Customer detail". */
export function CustomerDetail({ orgId, customerId, userRole = "staff", token }: CustomerDetailProps) {
  const canSeeBalance = userRole === "owner" || userRole === "manager";
  const canArchive = canSeeBalance;
  const [tab, setTab] = useState<Tab>("overview");
  const [editOpen, setEditOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const { notify } = useToast();

  const customer = useCustomer(orgId, customerId, token);
  const balance = useCustomerBalances(orgId, customerId, canSeeBalance, token);
  const orders = useOrders(orgId, { customerId, limit: 100 }, token);
  const payments = usePayments(orgId, { customerId, limit: 100 }, token);
  const archiveMutation = useArchiveCustomer(orgId, token);

  const base = `/workspace/${orgId}`;

  if (customer.error) {
    return (
      <div className="main page-in">
        <BackLink base={base} />
        <ErrorState title="Couldn’t load this customer" message="They may have been removed, or you may not have access." onRetry={() => void customer.refetch()} />
      </div>
    );
  }
  if (!customer.data) {
    return (
      <div className="main page-in" aria-busy="true" aria-label="Loading customer">
        <BackLink base={base} />
        <Skeleton width={260} height={28} />
        <Skeleton height={160} />
      </div>
    );
  }

  const c = customer.data;
  const b = balance.data?.items[0];
  const currency = balance.data?.currency_code ?? "PKR";
  const orderItems: Order[] = orders.data?.items ?? [];
  const paymentItems: Payment[] = payments.data?.items ?? [];
  const activity = [
    ...orderItems.map((o) => ({ kind: "order" as const, at: o.ordered_at, order: o })),
    ...paymentItems.map((p) => ({ kind: "payment" as const, at: p.received_at, payment: p })),
  ].sort((x, y) => (x.at < y.at ? 1 : -1));

  async function confirmArchive() {
    setArchiveError(null);
    try {
      await archiveMutation.mutateAsync(c.id);
      notify({ title: `${c.name} archived`, description: "Past orders and payments stay readable." });
      setArchiveOpen(false);
    } catch (err) {
      setArchiveError(err instanceof Error && err.message ? err.message : "Couldn’t archive the customer.");
    }
  }

  return (
    <div className="main page-in">
      <BackLink base={base} />
      <div className="ph">
        <div style={{ display: "flex", gap: 16, alignItems: "center", minWidth: 0 }}>
          <span className="av xl">{initials(c.name)}</span>
          <div className="ph-t">
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <h1 className="t-h1">{c.name}</h1>
              <span className={`badge ${c.status === "active" ? "b-success" : "b-neutral"}`}>{c.status === "active" ? "Active" : "Archived"}</span>
            </div>
            <div className="t-body-sm secondary" style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              {c.phone && <span className="num">{c.phone}</span>}
              {c.email && <span>{c.email}</span>}
              <span>Customer since {since(c.created_at)}</span>
            </div>
          </div>
        </div>
        <div className="ph-a">
          <button type="button" className="btn btn-ghost" onClick={() => setEditOpen(true)}>
            Edit
          </button>
          {canArchive && c.status === "active" && (
            <button type="button" className="btn btn-ghost" onClick={() => setArchiveOpen(true)}>
              Archive
            </button>
          )}
          {c.status === "active" && (
            <>
              <Link className="btn btn-secondary" href={`${base}/payments?customerId=${c.id}`}>
                Record payment
              </Link>
              <Link className="btn btn-primary" href={`${base}/orders/new?customerId=${c.id}`}>
                <Icon name="plus" />
                Create order
              </Link>
            </>
          )}
        </div>
      </div>

      <section className="sum-grid" aria-label="Customer summary">
        <div className="card metric">
          <span className="metric-l">Total orders</span>
          <span className="num" style={{ font: "600 24px/32px var(--font)" }}>
            {canSeeBalance ? (b?.order_count ?? "—") : orderItems.filter((o) => o.status === "active").length}
          </span>
          <span className="metric-c">{canSeeBalance && b ? `${b.voided_order_count} voided, not counted` : "Completed orders"}</span>
        </div>
        {canSeeBalance && (
          <>
            <div className="card metric">
              <span className="metric-l">Total purchases</span>
              {b ? <Money amountMinor={b.total_orders_minor} currency={currency} style={{ font: "600 24px/32px var(--font)" }} /> : <span>—</span>}
              <span className="metric-c">Completed orders</span>
            </div>
            <div className="card metric" style={{ borderColor: b && b.balance_minor > 0 ? "var(--warning-border)" : undefined }}>
              <span className="metric-l">Balance</span>
              {b ? <Money amountMinor={b.balance_minor} currency={currency} style={{ font: "600 24px/32px var(--font)" }} /> : <span>—</span>}
              <span className="metric-c">
                {b ? (
                  <>
                    Purchases − <Money amountMinor={b.total_payments_minor} currency={currency} /> paid
                  </>
                ) : (
                  "Purchases − recorded payments"
                )}
              </span>
            </div>
          </>
        )}
      </section>

      {c.notes && (
        <div className="alert a-neutral">
          <Icon name="info" />
          <span>{c.notes}</span>
        </div>
      )}

      <div className="tabs" role="tablist" aria-label="Customer sections">
        <button type="button" className="tab" role="tab" aria-selected={tab === "overview"} onClick={() => setTab("overview")}>
          Overview
        </button>
        <button type="button" className="tab" role="tab" aria-selected={tab === "orders"} onClick={() => setTab("orders")}>
          Orders{orders.data && <span className="count">{orders.data.total}</span>}
        </button>
        <button type="button" className="tab" role="tab" aria-selected={tab === "payments"} onClick={() => setTab("payments")}>
          Payments{payments.data && <span className="count">{payments.data.total}</span>}
        </button>
      </div>

      {(orders.error || payments.error) && <ErrorState title="Couldn’t load this customer’s activity" onRetry={() => void (orders.refetch(), payments.refetch())} />}

      {tab === "overview" && (
        <section className="card fade-in" aria-labelledby="cd-act">
          <div className="card-h">
            <h2 className="t-h3" id="cd-act">
              Activity
            </h2>
            <span className="t-caption">Orders and payments, newest first</span>
          </div>
          <div className="card-b">
            {(orders.isLoading || payments.isLoading) && <Skeleton height={80} />}
            {orders.data && payments.data && activity.length === 0 && (
              <EmptyState icon="orders" title="No orders or payments yet" description="Create an order for this customer to start their history." />
            )}
            {activity.length > 0 && (
              <ol className="tl stagger">
                {activity.map((a) =>
                  a.kind === "order" ? (
                    <li key={`o-${a.order.id}`} className="tl-row">
                      <span className={`tl-dot ${a.order.status === "voided" ? "bad" : a.order.status === "corrected" ? "warn" : ""}`}>
                        <Icon name="orders" />
                      </span>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, paddingTop: 3 }}>
                        <div>
                          <div className="t-h4">
                            <span className="mono">{a.order.order_number}</span> · Order {ORDER_STATUS[a.order.status]?.label.toLowerCase() ?? a.order.status}
                          </div>
                          <div className="t-caption">
                            {a.order.items.length} {a.order.items.length === 1 ? "item" : "items"} · {when(a.order.ordered_at)}
                          </div>
                        </div>
                        <Money amountMinor={a.order.order_total_minor} currency={a.order.currency_code} className={a.order.status === "active" ? "strong" : "struck"} />
                      </div>
                    </li>
                  ) : (
                    <li key={`p-${a.payment.id}`} className="tl-row">
                      <span className={`tl-dot ${a.payment.status === "active" ? "in" : "bad"}`}>
                        <Icon name="payments" />
                      </span>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, paddingTop: 3 }}>
                        <div>
                          <div className="t-h4">
                            Payment {a.payment.status === "active" ? "recorded" : PAYMENT_STATUS[a.payment.status]?.label.toLowerCase()} · {CHANNEL[a.payment.channel] ?? a.payment.channel}
                          </div>
                          <div className="t-caption">
                            {a.payment.external_reference ? `Ref. ${a.payment.external_reference} · ` : ""}
                            {when(a.payment.received_at)}
                          </div>
                        </div>
                        <Money
                          amountMinor={a.payment.amount_minor}
                          currency={a.payment.currency_code}
                          className={a.payment.status === "active" ? "strong" : "struck"}
                          style={a.payment.status === "active" ? { color: "var(--success)" } : undefined}
                        />
                      </div>
                    </li>
                  )
                )}
              </ol>
            )}
          </div>
        </section>
      )}

      {tab === "orders" && orders.data && (
        <div className="tbl-wrap fade-in">
          {orderItems.length === 0 ? (
            <EmptyState icon="orders" title="No orders yet" />
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Order #</th>
                  <th className="r">Items</th>
                  <th className="r">Total</th>
                  <th>Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {orderItems.map((o) => (
                  <tr key={o.id} className={o.status === "active" ? "" : "is-void"}>
                    <td>
                      <Link className={`link mono${o.status === "active" ? "" : " struck"}`} href={`${base}/orders/${o.id}`}>
                        {o.order_number}
                      </Link>
                    </td>
                    <td className="r">{o.items.length}</td>
                    <td className="r">
                      <Money amountMinor={o.order_total_minor} currency={o.currency_code} className={o.status === "active" ? "strong" : "struck"} />
                    </td>
                    <td>
                      <span className={`badge ${ORDER_STATUS[o.status]?.cls ?? "b-neutral"}`}>{ORDER_STATUS[o.status]?.label ?? o.status}</span>
                    </td>
                    <td className="muted">{when(o.ordered_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "payments" && payments.data && (
        <div className="tbl-wrap fade-in">
          {paymentItems.length === 0 ? (
            <EmptyState icon="payments" title="No payments yet" />
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Payment</th>
                  <th className="r">Amount</th>
                  <th>Method</th>
                  <th>Reference</th>
                  <th>Date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {paymentItems.map((p) => (
                  <tr key={p.id} className={p.status === "active" ? "" : "is-void"}>
                    <td className="mono">{p.payment_number}</td>
                    <td className="r">
                      <Money amountMinor={p.amount_minor} currency={p.currency_code} className={p.status === "active" ? "strong" : "struck"} />
                    </td>
                    <td>{CHANNEL[p.channel] ?? p.channel}</td>
                    <td className="muted">{p.external_reference || "—"}</td>
                    <td className="muted">{when(p.received_at)}</td>
                    <td>
                      <span className={`badge ${PAYMENT_STATUS[p.status]?.cls ?? "b-neutral"}`}>{PAYMENT_STATUS[p.status]?.label ?? p.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {canSeeBalance && (
        <p className="t-caption">Balances come from recorded orders and payments in BizPilot. They are not an accounting ledger or a bank statement.</p>
      )}

      <CustomerModal isOpen={editOpen} onClose={() => setEditOpen(false)} orgId={orgId} customer={c} token={token} />
      <Modal
        open={archiveOpen}
        tone="warning"
        title={`Archive ${c.name}?`}
        description="They won’t appear in new orders or payments. Their past orders and payments stay readable."
        onClose={() => {
          setArchiveOpen(false);
          setArchiveError(null);
        }}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setArchiveOpen(false)} disabled={archiveMutation.isPending}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" onClick={confirmArchive} disabled={archiveMutation.isPending} aria-busy={archiveMutation.isPending}>
              {archiveMutation.isPending && <span className="spinner" />}
              Archive customer
            </button>
          </>
        }
      >
        {archiveError && (
          <div className="alert a-danger" role="alert">
            {archiveError}
          </div>
        )}
      </Modal>
    </div>
  );
}

function BackLink({ base }: { base: string }) {
  return (
    <Link className="link t-body-sm" href={`${base}/customers`} style={{ display: "inline-flex", alignItems: "center", gap: 4, alignSelf: "flex-start" }}>
      <Icon name="chevronLeft" size="sm" />
      Customers
    </Link>
  );
}
