"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useOrder } from "@/hooks/use-orders";
import { usePayments } from "@/hooks/use-payments";
import { useOptionalAuth } from "@/hooks/use-auth";
import { productThumb } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { OrderStatusBadge, orderWhen, useCustomerNames, WALK_IN } from "@/components/orders/order-meta";
import { OrderCorrection } from "@/components/orders/order-correction";
import { OrderVoidModal } from "@/components/orders/order-void-modal";

interface OrderDetailProps {
  orgId: string;
  orderId: string;
  userRole?: string;
  token?: string;
  initialAction?: "correct" | null;
}

const CHANNEL: Record<string, string> = { cash: "Cash", bank_transfer: "Bank transfer", digital: "Digital wallet", other: "Other" };

/** Design canvas "18–19 · Order detail & correction". */
export function OrderDetail({ orgId, orderId, userRole = "staff", token, initialAction = null }: OrderDetailProps) {
  const canCorrect = userRole === "owner" || userRole === "manager";
  const canVoid = userRole === "owner";
  const router = useRouter();
  const currentUserId = useOptionalAuth()?.user?.id;
  const [mode, setMode] = useState<"view" | "correct">(initialAction === "correct" && canCorrect ? "correct" : "view");
  const [voidOpen, setVoidOpen] = useState(false);

  const order = useOrder(orgId, orderId, token);
  const o = order.data;
  const payments = usePayments(orgId, { orderId, limit: 100 }, token);
  const replacement = useOrder(orgId, o?.replaced_by_order_id ?? "", token);
  const original = useOrder(orgId, o?.corrects_order_id ?? "", token);
  const names = useCustomerNames(orgId, token);

  const base = `/workspace/${orgId}`;

  if (order.error) {
    return (
      <div className="main page-in">
        <BackLink base={base} />
        <ErrorState title="Couldn’t load this order" message="It may not exist, or you may not have access." onRetry={() => void order.refetch()} />
      </div>
    );
  }
  if (!o) {
    return (
      <div className="main page-in" aria-busy="true" aria-label="Loading order">
        <BackLink base={base} />
        <Skeleton width={260} height={28} />
        <Skeleton height={220} />
      </div>
    );
  }

  if (mode === "correct") {
    return (
      <div className="main page-in">
        <BackLink base={base} />
        <OrderCorrection orgId={orgId} order={o} token={token} onCancel={() => setMode("view")} onCorrected={(r) => router.push(`${base}/orders/${r.id}`)} />
      </div>
    );
  }

  const done = o.status === "active";
  const amtCls = done ? "" : " struck";
  const items = o.items ?? [];
  const units = items.reduce((s, it) => s + it.quantity, 0);
  const customer = o.customer_id ? (names.get(o.customer_id) ?? "Customer") : WALK_IN;
  const paid = (payments.data?.items ?? []).filter((p) => p.status === "active").reduce((s, p) => s + p.amount_minor, 0);
  const by = currentUserId && o.created_by_user_id === currentUserId ? "By you" : null;

  const history = [
    { at: o.ordered_at, title: "Order completed", sub: `stock −${units}`, dot: "", icon: "check" as const },
    ...(payments.data?.items ?? []).map((p) => ({ at: p.received_at, title: p.status === "active" ? "Payment recorded" : `Payment ${p.status}`, sub: `${p.payment_number} · ${CHANNEL[p.channel] ?? p.channel}`, dot: p.status === "active" ? "in" : "bad", icon: "payments" as const })),
    ...(o.status === "corrected" && replacement.data ? [{ at: replacement.data.created_at, title: `Corrected → ${replacement.data.order_number}`, sub: "Replacement created", dot: "warn", icon: "edit" as const }] : []),
    ...(o.status === "voided" && o.voided_at ? [{ at: o.voided_at, title: "Voided", sub: `${units} units returned to stock`, dot: "bad", icon: "ban" as const }] : []),
  ].sort((a, b) => (a.at < b.at ? 1 : -1));

  return (
    <div className="main page-in">
      <BackLink base={base} />
      <div className="ph">
        <div className="ph-t">
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <h1 className="t-h1">Order #{o.order_number}</h1>
            <OrderStatusBadge status={o.status} />
            {o.status === "corrected" && <span className="badge b-neutral">Original</span>}
            {o.corrects_order_id && <span className="badge b-brand">Replacement</span>}
          </div>
          <div className="t-body-sm secondary" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <span>{o.customer_id ? <Link className="link" href={`${base}/customers/${o.customer_id}`}>{customer}</Link> : customer}</span>
            <span>Created {orderWhen(o.ordered_at)}</span>
            {by && <span>{by}</span>}
          </div>
        </div>
        <div className="ph-a">
          {done && !canCorrect && (
            <span className="t-caption" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
              <Icon name="lock" size="sm" />
              Only Owners and Managers can correct orders
            </span>
          )}
          {done && canVoid && (
            <button type="button" className="btn btn-danger-outline" onClick={() => setVoidOpen(true)}>
              <Icon name="ban" />
              Void order
            </button>
          )}
          {done && canCorrect && (
            <button type="button" className="btn btn-secondary" onClick={() => setMode("correct")}>
              <Icon name="edit" />
              Correct order
            </button>
          )}
          {done && (
            <Link className="btn btn-primary" href={`${base}/payments`}>
              Record payment
            </Link>
          )}
        </div>
      </div>

      {o.status === "corrected" && (
        <div className="alert a-warning reveal" role="status">
          <Icon name="edit" />
          <div style={{ flex: 1 }}>
            <div className="a-t">This order was corrected{replacement.data ? ` ${orderWhen(replacement.data.created_at).replace(/^(Today|Yesterday)/, (m) => m.toLowerCase())}` : ""}</div>
            It no longer counts toward sales. The replacement order holds the corrected items.
          </div>
          {o.replaced_by_order_id && (
            <Link className="btn btn-secondary btn-sm" href={`${base}/orders/${o.replaced_by_order_id}`}>
              Open {replacement.data?.order_number ?? "replacement"}
            </Link>
          )}
        </div>
      )}
      {o.status === "voided" && (
        <div className="alert a-danger reveal" role="status">
          <Icon name="ban" />
          <div>
            <div className="a-t">Voided{o.voided_at ? ` ${orderWhen(o.voided_at).replace(/^(Today|Yesterday)/, (m) => m.toLowerCase())}` : ""}</div>
            Kept for your records. It doesn’t count toward sales, and its {units} units were returned to stock.
          </div>
        </div>
      )}
      {o.corrects_order_id && (
        <div className="alert a-neutral">
          <Icon name="info" />
          <span style={{ flex: 1 }}>This order replaces {original.data?.order_number ?? "an earlier order"}, which is kept and marked Corrected.</span>
          <Link className="btn btn-secondary btn-sm" href={`${base}/orders/${o.corrects_order_id}`}>
            Open {original.data?.order_number ?? "original"}
          </Link>
        </div>
      )}

      <div className="split">
        <div className="l">
          <section className="card" aria-labelledby="it-h" style={{ overflow: "hidden" }}>
            <div className="card-h">
              <h2 className="t-h3" id="it-h">
                Items
              </h2>
              <span className="t-caption">
                {items.length} {items.length === 1 ? "product" : "products"} · {units} {units === 1 ? "unit" : "units"}
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th className="r">Qty</th>
                    <th className="r">Price</th>
                    <th className="r">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => (
                    <tr key={it.id}>
                      <td>
                        <div className="cell-main">
                          <span className="thumb">{productThumb(it.product_code_snapshot, it.product_name_snapshot)}</span>
                          <div>
                            <div className="t">{it.product_name_snapshot}</div>
                            <div className="cell-sub mono">{it.product_code_snapshot}</div>
                          </div>
                        </div>
                      </td>
                      <td className="r">
                        {it.quantity} <span className="muted">{it.unit_snapshot}</span>
                      </td>
                      <td className="r">
                        <Money amountMinor={it.unit_price_minor} currency={it.currency_code} />
                      </td>
                      <td className="r">
                        <Money amountMinor={it.line_total_minor} currency={it.currency_code} className={`strong${amtCls}`} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ padding: "14px 18px", borderTop: "1px solid var(--border)", display: "flex", gap: 40, justifyContent: "flex-end", alignItems: "baseline" }}>
              <span className="t-h3">Total</span>
              <Money amountMinor={o.order_total_minor} currency={o.currency_code} className={amtCls.trim()} style={{ font: "600 24px/30px var(--font)", minWidth: 110, textAlign: "right" }} />
            </div>
          </section>
        </div>
        <div className="r">
          <section className="card" aria-labelledby="pay-h">
            <div className="card-h">
              <h2 className="t-h4" id="pay-h">
                Related payments
              </h2>
              {done && payments.data && (paid >= o.order_total_minor ? <span className="badge b-success">Paid in full</span> : paid > 0 ? <span className="badge b-warning">Part paid</span> : <span className="badge b-neutral">Unpaid</span>)}
            </div>
            {payments.error && <div style={{ padding: "0 18px 14px" }}><ErrorState title="Couldn’t load payments" onRetry={() => void payments.refetch()} /></div>}
            {payments.isLoading && <div style={{ padding: "12px 18px" }}><Skeleton height={36} /></div>}
            {payments.data && payments.data.items.length === 0 && <p className="t-body-sm muted" style={{ padding: "12px 18px" }}>No payments recorded against this order.</p>}
            {payments.data?.items.map((p) => (
              <div key={p.id} style={{ padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, borderTop: "1px solid var(--border)" }}>
                <div>
                  <span className={`mono${p.status === "active" ? "" : " struck"}`}>{p.payment_number}</span>
                  <div className="t-caption">
                    {CHANNEL[p.channel] ?? p.channel} · {orderWhen(p.received_at)}
                  </div>
                </div>
                <Money amountMinor={p.amount_minor} currency={p.currency_code} className={p.status === "active" ? "strong" : "struck"} />
              </div>
            ))}
            {!done && (payments.data?.items.length ?? 0) > 0 && (
              <div className="alert a-neutral" style={{ margin: "0 18px 14px", fontSize: 12.5 }}>
                <Icon name="info" size="sm" />
                <span>These payments stay recorded. Correct or void them separately in Payments if needed.</span>
              </div>
            )}
          </section>
          <section className="card" aria-labelledby="hist-h">
            <div className="card-h">
              <h2 className="t-h4" id="hist-h">
                History
              </h2>
            </div>
            <div className="card-b">
              <ol className="tl">
                {history.map((h, i) => (
                  <li key={i} className="tl-row">
                    <span className={`tl-dot ${h.dot}`}>
                      <Icon name={h.icon} />
                    </span>
                    <div style={{ paddingTop: 3 }}>
                      <div className="t-h4">{h.title}</div>
                      <div className="t-caption">
                        {orderWhen(h.at)} · {h.sub}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        </div>
      </div>

      <OrderVoidModal isOpen={voidOpen} onClose={() => setVoidOpen(false)} order={o} orgId={orgId} token={token} />
    </div>
  );
}

function BackLink({ base }: { base: string }) {
  return (
    <Link className="link t-body-sm" href={`${base}/orders`} style={{ display: "inline-flex", alignItems: "center", gap: 4, alignSelf: "flex-start" }}>
      <Icon name="chevronLeft" size="sm" />
      Orders
    </Link>
  );
}
