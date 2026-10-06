"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Order } from "@/lib/schemas/orders";
import { useOrders } from "@/hooks/use-orders";
import { useDashboard } from "@/hooks/use-dashboard";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";
import { Money } from "@/components/ui/money";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { OrderStatusBadge, orderWhen, useCustomerNames, WALK_IN } from "@/components/orders/order-meta";
import { OrderVoidModal } from "@/components/orders/order-void-modal";

interface OrdersViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
  initialCustomerId?: string;
}

type StatusFilter = "all" | "active" | "corrected" | "voided";
const FILTERS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Completed" },
  { key: "corrected", label: "Corrected" },
  { key: "voided", label: "Voided" },
];
const PAGE_SIZE = 50;

/** Design canvas "16 · Orders". Correct: Owner/Manager. Void: Owner. The backend enforces both. */
export function OrdersView({ orgId, userRole = "staff", token, initialCustomerId }: OrdersViewProps) {
  const canSeeSales = userRole === "owner" || userRole === "manager";
  const canCorrect = canSeeSales;
  const canVoid = userRole === "owner";
  const [status, setStatus] = useState<StatusFilter>("all");
  const [page, setPage] = useState(0);
  const [voiding, setVoiding] = useState<Order | null>(null);

  const { data, isLoading, error, refetch } = useOrders(
    orgId,
    { status: status === "all" ? undefined : status, customerId: initialCustomerId, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
    token
  );
  const today = useDashboard(canSeeSales ? orgId : "", { period: "today" }, token);
  const names = useCustomerNames(orgId, token);

  const base = `/workspace/${orgId}`;
  const orders = data?.items ?? [];
  const customerName = (o: Order) => (o.customer_id ? (names.get(o.customer_id) ?? "Customer") : WALK_IN);
  const filteredName = initialCustomerId ? names.get(initialCustomerId) : undefined;
  const newOrderHref = initialCustomerId ? `${base}/orders/new?customerId=${initialCustomerId}` : `${base}/orders/new`;

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Orders</h1>
          <p className="t-body secondary">Every sale, including corrected and voided ones.</p>
        </div>
        <div className="ph-a">
          <Link className="btn btn-primary" href={newOrderHref}>
            <Icon name="plus" />
            New order
          </Link>
        </div>
      </div>

      {canSeeSales && (
        <section className="sum-grid" aria-label="Orders today">
          <div className="card metric">
            <span className="metric-l">Completed today</span>
            <span className="num" style={{ font: "600 24px/32px var(--font)" }}>
              {today.data?.sales.order_count ?? "—"}
            </span>
            <span className="metric-c">Count toward sales · voided and corrected excluded</span>
          </div>
          <div className="card metric">
            <span className="metric-l">Sales today</span>
            {today.data ? (
              <Money amountMinor={today.data.sales.total_sales_minor} currency={today.data.sales.currency_code} style={{ font: "600 24px/32px var(--font)" }} />
            ) : (
              <span className="num" style={{ font: "600 24px/32px var(--font)" }}>
                —
              </span>
            )}
            <span className="metric-c">Completed orders only</span>
          </div>
        </section>
      )}

      {initialCustomerId && (
        <div className="alert a-neutral">
          <Icon name="customers" />
          <span style={{ flex: 1 }}>
            Showing orders for <b>{filteredName ?? "one customer"}</b>
          </span>
          <Link className="btn btn-secondary btn-sm" href={`${base}/orders`}>
            Show all orders
          </Link>
        </div>
      )}

      <div className="toolbar">
        <div className="seg" role="group" aria-label="Status">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              aria-pressed={status === f.key}
              onClick={() => {
                setStatus(f.key);
                setPage(0);
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorState title="Couldn’t load orders" message="Nothing was lost — check your connection, then try again." onRetry={() => void refetch()} />}

      {isLoading && (
        <div className="tbl-wrap" aria-busy="true" aria-label="Loading orders" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <Skeleton width={70} height={12} />
              <Skeleton width={28} height={28} radius={14} />
              <Skeleton width={180} height={12} />
            </div>
          ))}
        </div>
      )}

      {data && orders.length === 0 && (
        <div className="card">
          {status === "all" ? (
            <EmptyState
              icon="orders"
              title="No orders yet"
              description="Record a sale and stock is deducted automatically."
              action={
                <Link className="btn btn-primary" href={newOrderHref}>
                  New order
                </Link>
              }
            />
          ) : (
            <EmptyState icon="orders" title={`No ${FILTERS.find((f) => f.key === status)?.label.toLowerCase()} orders`} />
          )}
        </div>
      )}

      {orders.length > 0 && (
        <>
          <div className="tbl-wrap desk-only fade-in">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Customer</th>
                  <th className="r">Items</th>
                  <th className="r">Total</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th className="r">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const done = o.status === "active";
                  const name = customerName(o);
                  return (
                    <tr key={o.id} className={done ? "" : "is-void"}>
                      <td>
                        <Link className={`link mono${done ? "" : " struck"}`} href={`${base}/orders/${o.id}`}>
                          {o.order_number}
                        </Link>
                      </td>
                      <td>
                        <div className="cell-main">
                          <span className={`av${o.customer_id ? "" : " n"}`}>{o.customer_id ? initials(name) : "WI"}</span>
                          <span>{name}</span>
                        </div>
                      </td>
                      <td className="r">{o.items?.length ?? 0}</td>
                      <td className="r">
                        <Money amountMinor={o.order_total_minor} currency={o.currency_code} className={done ? "strong" : "strong struck"} />
                      </td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: 2, alignItems: "flex-start" }}>
                          <OrderStatusBadge status={o.status} />
                          {o.corrects_order_id && <span className="t-caption">Replacement order</span>}
                        </div>
                      </td>
                      <td className="muted">{orderWhen(o.ordered_at ?? o.created_at)}</td>
                      <td className="r">
                        <span className="row-actions">
                          <Link className="btn btn-ghost btn-sm" href={`${base}/orders/${o.id}`} aria-label={`View ${o.order_number}`}>
                            View
                          </Link>
                          {done && canCorrect && (
                            <Link className="btn btn-ghost btn-sm" href={`${base}/orders/${o.id}?action=correct`} aria-label={`Correct ${o.order_number}`}>
                              Correct
                            </Link>
                          )}
                          {done && canVoid && (
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setVoiding(o)} aria-label={`Void ${o.order_number}`}>
                              Void
                            </button>
                          )}
                        </span>
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
                  <button type="button" className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" disabled={(page + 1) * PAGE_SIZE >= data.total} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>

          <ul className="only-sm" style={{ flexDirection: "column", gap: 8 }} aria-label="Orders">
            {orders.map((o) => {
              const done = o.status === "active";
              return (
                <li key={o.id}>
                  <Link className="card" href={`${base}/orders/${o.id}`} style={{ padding: "12px 14px", display: "flex", gap: 12, alignItems: "center", textDecoration: "none", color: "inherit" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className={`mono strong${done ? "" : " struck"}`}>{o.order_number}</div>
                      <div className="t-caption">
                        {customerName(o)} · {orderWhen(o.ordered_at ?? o.created_at)}
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                      <Money amountMinor={o.order_total_minor} currency={o.currency_code} className={done ? "strong t-body-sm" : "strong t-body-sm struck"} />
                      <OrderStatusBadge status={o.status} />
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      )}

      <OrderVoidModal isOpen={!!voiding} onClose={() => setVoiding(null)} order={voiding} orgId={orgId} token={token} />
    </div>
  );
}
