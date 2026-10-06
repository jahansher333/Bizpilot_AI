"use client";

import React, { useEffect, useRef } from "react";
import Link from "next/link";
import { productThumb } from "@/lib/stock";
import { useMediaQuery, PHONE_QUERY } from "@/hooks/use-media-query";
import { Icon } from "@/components/ui/icon";
import { Money, formatMinor } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { PriceInput, QtyStepper } from "@/components/orders/order-cart";
import { WALK_IN } from "@/components/orders/order-meta";
import { OrderPosMobile } from "@/components/orders/order-pos-mobile";
import { Pos, usePos } from "@/components/orders/use-pos";

interface OrderPosProps {
  orgId: string;
  token?: string;
  initialCustomerId?: string;
}

const LOW = 10;

/** Create order: the desktop POS, or the design's 4-step flow on phones (under 760px). */
export function OrderPos({ orgId, token, initialCustomerId }: OrderPosProps) {
  const pos = usePos(orgId, token, initialCustomerId);
  const phone = useMediaQuery(PHONE_QUERY);
  return phone ? <OrderPosMobile orgId={orgId} pos={pos} /> : <OrderPosDesktop orgId={orgId} pos={pos} />;
}

/** Design canvas "17 · Create order (POS)": catalogue left, cart right. */
function OrderPosDesktop({ orgId, pos }: { orgId: string; pos: Pos }) {
  const { products, q, setQ, cat, setCat, query, visible, inCart, lines, total, units, customerName, customerId, add, setQty, setPrice, error, done } = pos;
  const searchRef = useRef<HTMLInputElement>(null);
  const base = `/workspace/${orgId}`;
  const complete = pos.complete;
  const reset = () => {
    pos.reset();
    searchRef.current?.focus();
  };

  // "/" focuses search; Ctrl/⌘+Enter completes the order.
  const completeRef = useRef(complete);
  completeRef.current = complete;
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing = !!target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT");
      if (e.key === "/" && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        void completeRef.current();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div style={{ flex: 1, display: "flex", flexWrap: "wrap", alignItems: "stretch", minHeight: 0 }}>
      <section aria-label="Products" className="page-in" style={{ flex: "65 1 520px", minWidth: 0, padding: "24px 28px", display: "flex", flexDirection: "column", gap: 16 }}>
        <Link className="link t-body-sm" href={`${base}/orders`} style={{ display: "inline-flex", alignItems: "center", gap: 4, alignSelf: "flex-start" }}>
          <Icon name="chevronLeft" size="sm" />
          Orders
        </Link>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <h1 className="t-h1">New order</h1>
          <span className="t-caption desk-only">
            Press <span className="kbd">/</span> to search · <span className="kbd">Enter</span> adds the first match
          </span>
        </div>
        <div className="ig lg" style={{ height: 46 }}>
          <span className="pre plain">
            <Icon name="search" size="lg" />
          </span>
          <input
            ref={searchRef}
            placeholder="Search product name or code"
            aria-label="Search products"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                const first = visible.find((p) => (inCart.get(p.id) ?? 0) < p.stock);
                if (first) add(first);
              }
            }}
            style={{ fontSize: 15, fontWeight: 400 }}
          />
        </div>
        {pos.categories.length > 0 && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} role="group" aria-label="Category">
            <button type="button" className="chip" aria-pressed={cat === "all"} onClick={() => setCat("all")}>
              All
            </button>
            {pos.categories.map((c) => (
              <button key={c.id} type="button" className="chip" aria-pressed={cat === c.id} onClick={() => setCat(c.id)}>
                {c.name}
              </button>
            ))}
          </div>
        )}

        {products.error && <ErrorState title="Couldn’t load products" onRetry={products.refetch} />}
        {products.isLoading && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(190px, 100%), 1fr))", gap: 10 }} aria-busy="true" aria-label="Loading products">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Skeleton key={i} height={120} radius={8} />
            ))}
          </div>
        )}
        {!products.isLoading && !products.error && products.items.length === 0 && (
          <div className="card">
            <EmptyState
              icon="products"
              title="No products to sell yet"
              description="Add products and record their opening stock, then come back to create an order."
              action={
                <Link className="btn btn-primary" href={`${base}/catalog`}>
                  Go to Products
                </Link>
              }
            />
          </div>
        )}
        {products.items.length > 0 && visible.length === 0 && (
          <div className="card">
            <EmptyState icon="search" title={query ? `No products match “${q.trim()}”` : "No products in this category"} description="Search by product code, or add it from Products." />
          </div>
        )}
        {visible.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(190px, 100%), 1fr))", gap: 10 }}>
            {visible.map((p) => {
              const qty = inCart.get(p.id) ?? 0;
              const out = p.stock === 0;
              const full = qty >= p.stock;
              const low = !out && p.stock <= LOW;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => add(p)}
                  disabled={full}
                  aria-label={`${p.name}, PKR ${formatMinor(p.default_price_minor)}, ${out ? "out of stock" : full ? "all available stock is in the cart" : `${p.stock} in stock, add to order`}`}
                  style={{
                    textAlign: "left",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    padding: 12,
                    borderRadius: 8,
                    border: `1px solid ${qty > 0 ? "var(--brand)" : "var(--border)"}`,
                    background: out ? "var(--surface-sunken)" : "var(--surface)",
                    cursor: full ? "not-allowed" : "pointer",
                    font: "inherit",
                    color: "inherit",
                    opacity: out ? 0.6 : 1,
                    transition: "border-color 120ms, box-shadow 120ms",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <span className="thumb">{productThumb(p.code, p.name)}</span>
                    {qty > 0 && (
                      <span className="pop-in" style={{ minWidth: 24, height: 24, padding: "0 6px", borderRadius: 999, background: "var(--brand)", color: "var(--on-brand)", display: "inline-flex", alignItems: "center", justifyContent: "center", font: "600 12px var(--font)" }}>
                        {qty}
                      </span>
                    )}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2, minHeight: 40 }}>
                    <span style={{ font: "500 13.5px/18px var(--font)" }}>{p.name}</span>
                    <span className="mono muted" style={{ fontSize: 11 }}>
                      {p.code}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                    <Money amountMinor={p.default_price_minor} currency={p.currency_code} className="strong" />
                    <span style={{ font: "500 11.5px var(--font)", color: out ? "var(--danger)" : low ? "var(--warning)" : "var(--text-muted)" }}>
                      {out ? "Out of stock" : low ? `Low · ${p.stock} left` : `${p.stock} in stock`}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <aside aria-label="Order cart" style={{ flex: "35 1 360px", minWidth: 0, background: "var(--surface)", borderLeft: "1px solid var(--border)", display: "flex", flexDirection: "column", position: "sticky", top: 0, maxHeight: "calc(100vh - 60px)", minHeight: 520 }}>
        <div style={{ padding: "18px 20px", borderBottom: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 8 }}>
          <label className="label" htmlFor="pos-customer">
            Customer
          </label>
          <select id="pos-customer" className="input" value={customerId} onChange={(e) => pos.chooseCustomer(e.target.value)} style={{ height: 44 }}>
            <option value="">{WALK_IN}</option>
            {pos.customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.phone ? ` · ${c.phone}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: "8px 20px" }} aria-live="polite">
          {lines.length === 0 ? (
            <div className="empty" style={{ padding: "48px 8px" }}>
              <span className="empty-art">
                <Icon name="cart" />
              </span>
              <span className="t-h4">Cart is empty</span>
              <span className="t-body-sm muted">Tap a product to add it.</span>
            </div>
          ) : (
            <ul aria-label="Cart items">
              {lines.map((l) => (
                <li key={l.productId} className="reveal" style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "8px 12px", padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ minWidth: 0, font: "500 13.5px/18px var(--font)" }}>{l.name}</div>
                  <Money amountMinor={l.qty * l.priceMinor} className="strong" style={{ textAlign: "right" }} />
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <QtyStepper line={l} onChange={(n) => setQty(l.productId, n)} />
                    <PriceInput line={l} onChange={(n) => setPrice(l.productId, n)} />
                    {l.qty >= l.max && (
                      <span className="t-caption" style={{ color: "var(--warning)" }}>
                        Max · {l.max} in stock
                      </span>
                    )}
                  </div>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setQty(l.productId, 0)} aria-label={`Remove ${l.name}`} style={{ justifySelf: "end", alignSelf: "center", color: "var(--text-muted)" }}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div style={{ padding: "16px 20px 20px", borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 12, background: "var(--surface)" }}>
          {error && (
            <div className="alert a-danger" role="alert">
              <Icon name="alert" />
              <span>{error}</span>
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between" }} className="t-body">
            <span className="secondary">
              {units} {units === 1 ? "item" : "items"} · {customerName}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span className="t-h3">Total</span>
            <Money amountMinor={total} style={{ font: "600 26px/32px var(--font)", letterSpacing: "-0.02em" }} />
          </div>
          <button
            type="button"
            className={`btn btn-primary btn-lg btn-block${pos.pending ? " is-loading" : ""}`}
            disabled={lines.length === 0 || pos.pending}
            aria-busy={pos.pending}
            onClick={() => void complete()}
          >
            {pos.pending ? (
              <>
                <span className="spinner" />
                Completing order…
              </>
            ) : (
              <>
                Complete order
                <span className="kbd desk-only" style={{ background: "transparent", color: "inherit", borderColor: "rgba(255,255,255,.4)" }}>
                  Ctrl ↵
                </span>
              </>
            )}
          </button>
          <Link className="btn btn-ghost btn-block" href={`${base}/orders`}>
            Cancel
          </Link>
        </div>
      </aside>

      <Modal
        open={!!done}
        title={done ? `Order ${done.order_number} completed` : ""}
        description={done ? `${customerName} · ${units} ${units === 1 ? "item" : "items"} · stock updated` : undefined}
        onClose={reset}
        footer={
          done && (
            <>
              <Link className="btn btn-secondary" href={`${base}/payments?record=1&orderId=${done.id}${done.customer_id ? `&customerId=${done.customer_id}` : ""}`}>
                Record payment
              </Link>
              <Link className="btn btn-secondary" href={`${base}/orders/${done.id}`}>
                View order
              </Link>
              <button type="button" className="btn btn-primary" onClick={reset}>
                New order
              </button>
            </>
          )
        }
      >
        {done && <Money amountMinor={done.order_total_minor} currency={done.currency_code} style={{ font: "600 32px/40px var(--font)", letterSpacing: "-0.02em" }} />}
      </Modal>
    </div>
  );
}
