"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { productThumb } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";
import { Money, formatMinor } from "@/components/ui/money";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { WALK_IN } from "@/components/orders/order-meta";
import { Pos } from "@/components/orders/use-pos";

const LOW = 10;
const TITLES = ["Add products", "Cart", "Customer", "Review", "Done"];
const TOUCH = { minWidth: 44, minHeight: 44 } as const;

/** Design canvas "Mobile · Create order": products → cart → customer → review, with a sticky CTA. */
export function OrderPosMobile({ orgId, pos }: { orgId: string; pos: Pos }) {
  const { products, visible, inCart, lines, total, units, customerId, customerName, error, done } = pos;
  const [step, setStep] = useState(0);
  const [custQuery, setCustQuery] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const base = `/workspace/${orgId}`;
  const current = done ? 4 : step;

  // Move focus to the step title so screen readers announce each step.
  useEffect(() => {
    headingRef.current?.focus();
  }, [current]);

  const cq = custQuery.trim().toLowerCase();
  const customers = [{ id: "", name: WALK_IN, phone: "No details saved" }, ...pos.customers.map((c) => ({ id: c.id, name: c.name, phone: c.phone ?? "" }))].filter(
    (c) => !cq || c.id === customerId || `${c.name} ${c.phone}`.toLowerCase().includes(cq)
  );

  function newOrder() {
    pos.reset();
    setStep(0);
    setCustQuery("");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "calc(100dvh - 60px)", background: "var(--bg)" }}>
      <header style={{ position: "sticky", top: 0, zIndex: 5, background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
        <div style={{ height: 56, display: "flex", alignItems: "center", gap: 4, padding: "0 8px 0 4px" }}>
          {current === 0 || current === 4 ? (
            <Link className="btn btn-ghost icon-btn" style={TOUCH} href={`${base}/orders`} aria-label="Close">
              <Icon name="close" size="lg" />
            </Link>
          ) : (
            <button type="button" className="btn btn-ghost icon-btn" style={TOUCH} aria-label="Back" onClick={() => setStep((s) => Math.max(0, s - 1))}>
              <Icon name="chevronLeft" size="lg" />
            </button>
          )}
          <h1 ref={headingRef} tabIndex={-1} className="t-h3" style={{ flex: 1, outline: "none" }}>
            {TITLES[current]}
          </h1>
          {current < 4 && <span className="t-caption" style={{ paddingRight: 8 }}>{`Step ${current + 1} of 4`}</span>}
        </div>
        <div style={{ height: 3, background: "var(--surface-sunken)" }} role="progressbar" aria-label="Order progress" aria-valuemin={1} aria-valuemax={4} aria-valuenow={Math.min(current + 1, 4)}>
          <div style={{ height: "100%", width: `${Math.min(100, (current + 1) * 25)}%`, background: "var(--brand)", transition: "width 300ms var(--ease-out)" }} />
        </div>
      </header>

      <div style={{ flex: 1, padding: "14px 16px 24px" }} aria-live="polite">
        {current === 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="ig" style={{ height: 46 }}>
              <span className="pre plain">
                <Icon name="search" size="lg" />
              </span>
              <input placeholder="Search product or code" aria-label="Search products" value={pos.q} onChange={(e) => pos.setQ(e.target.value)} style={{ fontSize: 15 }} />
            </div>
            {pos.categories.length > 0 && (
              <div style={{ display: "flex", gap: 6, overflowX: "auto", margin: "0 -16px", padding: "0 16px" }} role="group" aria-label="Category">
                <button type="button" className="chip" aria-pressed={pos.cat === "all"} onClick={() => pos.setCat("all")} style={{ height: 36, flex: "none" }}>
                  All
                </button>
                {pos.categories.map((c) => (
                  <button key={c.id} type="button" className="chip" aria-pressed={pos.cat === c.id} onClick={() => pos.setCat(c.id)} style={{ height: 36, flex: "none" }}>
                    {c.name}
                  </button>
                ))}
              </div>
            )}
            {products.error && <ErrorState title="Couldn’t load products" onRetry={products.refetch} />}
            {products.isLoading && <Skeleton height={64} />}
            {!products.isLoading && !products.error && products.items.length === 0 && (
              <div className="card">
                <EmptyState icon="products" title="No products to sell yet" action={<Link className="btn btn-primary" href={`${base}/catalog`}>Go to Products</Link>} />
              </div>
            )}
            {visible.length > 0 && (
              <ul className="card" style={{ overflow: "hidden" }} aria-label="Products">
                {visible.map((p) => {
                  const qty = inCart.get(p.id) ?? 0;
                  const out = p.stock === 0;
                  const full = qty >= p.stock;
                  const low = !out && p.stock <= LOW;
                  return (
                    <li key={p.id} style={{ borderBottom: "1px solid var(--border)" }}>
                      <button
                        type="button"
                        onClick={() => pos.add(p)}
                        disabled={full}
                        aria-label={`${p.name}, PKR ${formatMinor(p.default_price_minor)}, ${out ? "out of stock" : full ? "all available stock is in the cart" : `${p.stock} in stock, add to order`}`}
                        style={{ width: "100%", minHeight: 64, display: "flex", gap: 12, alignItems: "center", padding: "10px 14px", border: 0, background: qty > 0 ? "var(--brand-tint)" : "var(--surface)", textAlign: "left", font: "inherit", color: "inherit", cursor: full ? "not-allowed" : "pointer", opacity: out ? 0.55 : 1 }}
                      >
                        <span className="thumb">{productThumb(p.code, p.name)}</span>
                        <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                          <span style={{ font: "500 14px/19px var(--font)" }}>{p.name}</span>
                          <span style={{ font: "500 12px/16px var(--font)", color: out ? "var(--danger)" : low || full ? "var(--warning)" : "var(--text-muted)" }}>
                            {out ? "Out of stock" : full ? `All ${p.stock} in cart` : low ? `Low · ${p.stock} left` : `${p.stock} in stock`}
                          </span>
                        </span>
                        <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                          <Money amountMinor={p.default_price_minor} currency={p.currency_code} className="strong t-body-sm" />
                          {qty > 0 && <span className="badge b-brand pop-in" style={{ height: 20 }}>× {qty}</span>}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {products.items.length > 0 && visible.length === 0 && <p className="t-body-sm muted">No products match “{pos.q.trim()}”.</p>}
          </div>
        )}

        {current === 1 && (
          <ul className="card" style={{ padding: "0 14px" }} aria-label="Cart items">
            {lines.length === 0 && (
              <li className="empty">
                <span className="t-h4">Cart is empty</span>
                <button type="button" className="btn btn-secondary" onClick={() => setStep(0)}>
                  Add products
                </button>
              </li>
            )}
            {lines.map((l) => (
              <li key={l.productId} style={{ padding: "14px 0", borderBottom: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <span style={{ font: "500 14px/19px var(--font)" }}>{l.name}</span>
                  <Money amountMinor={l.qty * l.priceMinor} className="strong" />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <div className="ig" style={{ height: 44, width: 140 }}>
                    <button type="button" className="btn btn-ghost icon-btn" style={{ height: "100%", borderRadius: 0, width: 44 }} aria-label={`Decrease ${l.name}`} onClick={() => pos.setQty(l.productId, l.qty - 1)}>
                      <Icon name="minus" />
                    </button>
                    <span className="num" style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 600 }} aria-label={`Quantity of ${l.name}`}>
                      {l.qty}
                    </span>
                    <button type="button" className="btn btn-ghost icon-btn" style={{ height: "100%", borderRadius: 0, width: 44 }} aria-label={`Increase ${l.name}`} onClick={() => pos.setQty(l.productId, l.qty + 1)} disabled={l.qty >= l.max}>
                      <Icon name="plus" />
                    </button>
                  </div>
                  <span className="t-caption" style={{ textAlign: "right" }}>
                    PKR {formatMinor(l.priceMinor)} each{l.qty >= l.max ? " · max in stock" : ""}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}

        {current === 2 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="ig" style={{ height: 46 }}>
              <span className="pre plain">
                <Icon name="search" size="lg" />
              </span>
              <input placeholder="Name or phone" aria-label="Find customer" value={custQuery} onChange={(e) => setCustQuery(e.target.value)} style={{ fontSize: 15 }} />
            </div>
            <fieldset className="card" style={{ margin: 0, padding: 0, border: "1px solid var(--border)", overflow: "hidden" }}>
              <legend className="sr-only">Customer</legend>
              {customers.map((c) => (
                <label key={c.id || "walk-in"} style={{ display: "flex", gap: 12, alignItems: "center", minHeight: 60, padding: "8px 14px", borderBottom: "1px solid var(--border)", background: c.id === customerId ? "var(--brand-tint)" : "var(--surface)", cursor: "pointer" }}>
                  <span className={`av${c.id ? "" : " n"}`}>{c.id ? initials(c.name) : "WI"}</span>
                  <span style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                    <span style={{ font: "500 14px/19px var(--font)" }}>{c.name}</span>
                    {c.phone && <span className="t-caption num">{c.phone}</span>}
                  </span>
                  <input type="radio" name="mpos-customer" checked={c.id === customerId} onChange={() => pos.chooseCustomer(c.id)} style={{ width: 20, height: 20, accentColor: "var(--brand)" }} />
                </label>
              ))}
            </fieldset>
          </div>
        )}

        {current === 3 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="card" style={{ padding: 14, display: "flex", gap: 12, alignItems: "center" }}>
              <span className={`av${customerId ? "" : " n"}`}>{customerId ? initials(customerName) : "WI"}</span>
              <div style={{ flex: 1 }}>
                <div className="t-caption">Customer</div>
                <div className="t-h4">{customerName}</div>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={() => setStep(2)}>
                Change
              </button>
            </div>
            <div className="card" style={{ padding: "4px 14px" }}>
              {lines.map((l) => (
                <div key={l.productId} className="t-body-sm" style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
                  <span>
                    {l.name} × {l.qty}
                  </span>
                  <Money amountMinor={l.qty * l.priceMinor} />
                </div>
              ))}
              <div className="t-h3" style={{ display: "flex", justifyContent: "space-between", padding: "12px 0" }}>
                <span>Total</span>
                <Money amountMinor={total} />
              </div>
            </div>
            <p className="t-caption">Completing updates stock immediately. You can record payment next.</p>
            {error && (
              <div className="alert a-danger" role="alert">
                <Icon name="alert" />
                <span>{error}</span>
              </div>
            )}
          </div>
        )}

        {current === 4 && done && (
          <div role="status" style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 14, paddingTop: 48 }}>
            <span className="dlg-icon ok pop-in" style={{ width: 72, height: 72 }}>
              <Icon name="check" size="xl" className="check-anim" />
            </span>
            <h2 className="t-h1">Order completed</h2>
            <span className="mono muted">
              {done.order_number} · {customerName}
            </span>
            <Money amountMinor={done.order_total_minor} currency={done.currency_code} style={{ font: "600 34px/40px var(--font)" }} />
          </div>
        )}
      </div>

      <div style={{ position: "sticky", bottom: 0, padding: "12px 16px 20px", background: "var(--surface)", borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 8 }}>
        {current === 0 && (
          <button type="button" className="btn btn-primary btn-lg btn-block" onClick={() => setStep(1)} disabled={lines.length === 0} style={{ justifyContent: "space-between", height: 52 }}>
            <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
              <span style={{ minWidth: 24, height: 24, borderRadius: 999, background: "rgba(255,255,255,.2)", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 12 }}>{units}</span>
              View cart
            </span>
            <span className="num">PKR {formatMinor(total)}</span>
          </button>
        )}
        {current === 1 && (
          <button type="button" className="btn btn-primary btn-lg btn-block" onClick={() => setStep(2)} disabled={lines.length === 0} style={{ height: 52 }}>
            Choose customer
          </button>
        )}
        {current === 2 && (
          <button type="button" className="btn btn-primary btn-lg btn-block" onClick={() => setStep(3)} style={{ height: 52 }}>
            Review order
          </button>
        )}
        {current === 3 && (
          <button type="button" className="btn btn-primary btn-lg btn-block" onClick={() => void pos.complete()} disabled={pos.pending || lines.length === 0} aria-busy={pos.pending} style={{ height: 52 }}>
            {pos.pending ? (
              <>
                <span className="spinner" />
                Completing…
              </>
            ) : (
              `Complete order · PKR ${formatMinor(total)}`
            )}
          </button>
        )}
        {current === 4 && done && (
          <>
            <Link className="btn btn-primary btn-lg btn-block" href={`${base}/payments?record=1&orderId=${done.id}${done.customer_id ? `&customerId=${done.customer_id}` : ""}`} style={{ height: 52 }}>
              Record payment
            </Link>
            <button type="button" className="btn btn-secondary btn-lg btn-block" onClick={newOrder}>
              New order
            </button>
          </>
        )}
      </div>
    </div>
  );
}
