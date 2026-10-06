"use client";

import React, { useMemo, useRef, useState } from "react";
import { useCorrectOrder } from "@/hooks/use-orders";
import { useCustomers } from "@/hooks/use-customers";
import { Order, orderCorrectSchema } from "@/lib/schemas/orders";
import { newIdempotencyKey } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { CartLine, PriceInput, QtyStepper, cartTotal, cartUnits, useSellableProducts } from "@/components/orders/order-cart";
import { WALK_IN } from "@/components/orders/order-meta";

interface OrderCorrectionProps {
  orgId: string;
  order: Order;
  token?: string;
  onCancel: () => void;
  /** Called with the replacement order the backend created. */
  onCorrected: (replacement: Order) => void;
}

/**
 * Design "18–19 · Order correction": the original stays visible (marked Corrected) and a linked
 * replacement order is created. Owner/Manager only; the backend enforces it.
 */
export function OrderCorrection({ orgId, order, token, onCancel, onCorrected }: OrderCorrectionProps) {
  const products = useSellableProducts(orgId, token);
  const { data: customers } = useCustomers(orgId, { status: "active", limit: 100 }, token);
  const correctMutation = useCorrectOrder(orgId, token);
  const { notify } = useToast();

  const originalQty = useMemo(() => {
    const m = new Map<string, number>();
    for (const it of order.items ?? []) if (it.product_id) m.set(it.product_id, (m.get(it.product_id) ?? 0) + it.quantity);
    return m;
  }, [order.items]);
  // The original's stock is returned before the replacement is deducted, so it is available again.
  const maxFor = (productId: string) => (products.items.find((p) => p.id === productId)?.stock ?? 0) + (originalQty.get(productId) ?? 0);

  const initial = useMemo<CartLine[]>(
    () =>
      (order.items ?? [])
        .filter((it) => it.product_id)
        .map((it) => ({ productId: it.product_id!, name: it.product_name_snapshot, code: it.product_code_snapshot, unit: it.unit_snapshot, qty: it.quantity, priceMinor: it.unit_price_minor, max: Infinity })),
    [order.items]
  );
  const dropped = (order.items ?? []).filter((it) => !it.product_id);

  const [draft, setDraft] = useState<CartLine[]>(initial);
  const [customerId, setCustomerId] = useState(order.customer_id ?? "");
  const [reason, setReason] = useState("");
  const [addId, setAddId] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idemKey = useRef(newIdempotencyKey());

  const lines = draft.map((l) => ({ ...l, max: products.isLoading ? l.max : maxFor(l.productId) }));
  const kept = lines.filter((l) => l.qty > 0);
  const newTotal = cartTotal(kept);
  const diff = newTotal - order.order_total_minor;
  const changeCount =
    lines.filter((l) => {
      const o = initial.find((i) => i.productId === l.productId);
      return !o || o.qty !== l.qty || o.priceMinor !== l.priceMinor;
    }).length + (customerId !== (order.customer_id ?? "") ? 1 : 0);
  const stockDelta = cartUnits(kept) - (order.items ?? []).reduce((s, it) => s + it.quantity, 0);
  const addable = products.items.filter((p) => !draft.some((l) => l.productId === p.id) && p.stock + (originalQty.get(p.id) ?? 0) > 0);
  const customerName = (id: string) => (id ? (customers?.items.find((c) => c.id === id)?.name ?? "Customer") : WALK_IN);

  function edit(fn: (current: CartLine[]) => CartLine[]) {
    idemKey.current = newIdempotencyKey();
    setError(null);
    setDraft(fn);
  }

  function review() {
    setError(null);
    const parsed = orderCorrectSchema.safeParse({ reason, customer_id: customerId || undefined, items: kept.map((l) => ({ product_id: l.productId, quantity: l.qty, unit_price_minor: l.priceMinor })), currency_code: order.currency_code });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return;
    }
    setReviewing(true);
  }

  async function submit() {
    const parsed = orderCorrectSchema.safeParse({ reason, customer_id: customerId || undefined, items: kept.map((l) => ({ product_id: l.productId, quantity: l.qty, unit_price_minor: l.priceMinor })), currency_code: order.currency_code });
    if (!parsed.success) return;
    try {
      const replacement = await correctMutation.mutateAsync({ orderId: order.id, payload: parsed.data, idempotencyKey: `web-correct-${idemKey.current}` });
      notify({ title: `Order ${order.order_number} corrected`, description: `Replacement ${replacement.order_number} created.` });
      setReviewing(false);
      onCorrected(replacement);
    } catch (err) {
      setReviewing(false);
      setError(err instanceof Error && err.message ? err.message : "Couldn’t save the correction. Nothing was changed.");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }} className="fade-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Correct order {order.order_number}</h1>
          <p className="t-body secondary">Corrections preserve history. The original stays visible, marked “Corrected”, and a replacement order is created.</p>
        </div>
        <div className="ph-a">
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>

      {dropped.length > 0 && (
        <div className="alert a-warning">
          <Icon name="alert" />
          <span>
            {dropped.map((d) => d.product_name_snapshot).join(", ")} {dropped.length === 1 ? "is" : "are"} no longer in your catalogue and can’t be added to the replacement.
          </span>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))", gap: 16, alignItems: "stretch" }}>
        <section className="card" aria-label="Original order" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12, background: "var(--surface-sunken)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <span className="t-over">1 · Original</span>
            <span className="badge b-neutral">Will be marked Corrected</span>
          </div>
          <div className="mono strong">{order.order_number}</div>
          <div className="t-caption">{customerName(order.customer_id ?? "")}</div>
          <ul className="t-body-sm" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {(order.items ?? []).map((it) => (
              <li key={it.id} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span>
                  {it.product_name_snapshot} × {it.quantity}
                </span>
                <Money amountMinor={it.line_total_minor} currency={it.currency_code} />
              </li>
            ))}
          </ul>
          <div className="divider" />
          <div style={{ display: "flex", justifyContent: "space-between" }} className="t-h4">
            <span>Total</span>
            <Money amountMinor={order.order_total_minor} currency={order.currency_code} />
          </div>
        </section>

        <section className="card" aria-label="Correction" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12, borderColor: "var(--warning-border)", boxShadow: "0 0 0 3px var(--warning-bg)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <span className="t-over" style={{ color: "var(--warning)" }}>
              2 · Correction
            </span>
            <span className="badge b-warning">
              {changeCount} {changeCount === 1 ? "change" : "changes"}
            </span>
          </div>
          <div className="field">
            <label className="label" htmlFor="cr-customer">
              Customer
            </label>
            <select id="cr-customer" className="input" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">{WALK_IN}</option>
              {order.customer_id && !customers?.items.some((c) => c.id === order.customer_id) && <option value={order.customer_id}>{customerName(order.customer_id)}</option>}
              {customers?.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <ul style={{ display: "flex", flexDirection: "column", gap: 10 }} aria-label="Replacement items">
            {lines.map((l) => (
              <li key={l.productId} style={{ display: "flex", flexDirection: "column", gap: 6, opacity: l.qty === 0 ? 0.6 : 1 }}>
                <span className={`t-body-sm${l.qty === 0 ? " struck" : ""}`} style={{ minWidth: 0 }}>
                  {l.name}
                  {l.qty === 0 && " · removed"}
                </span>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <QtyStepper compact line={l} onChange={(n) => edit((cur) => cur.map((x) => (x.productId === l.productId ? { ...x, qty: Math.max(0, Math.min(n, l.max)) } : x)))} />
                  <PriceInput line={l} onChange={(n) => edit((cur) => cur.map((x) => (x.productId === l.productId ? { ...x, priceMinor: n } : x)))} />
                </div>
              </li>
            ))}
          </ul>
          {addable.length > 0 && (
            <div style={{ display: "flex", gap: 8 }}>
              <select className="input" aria-label="Add a product" value={addId} onChange={(e) => setAddId(e.target.value)} style={{ flex: 1, minWidth: 0 }}>
                <option value="">Add a product…</option>
                {addable.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {p.code}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={!addId}
                onClick={() => {
                  const p = products.items.find((x) => x.id === addId);
                  if (!p) return;
                  edit((cur) => [...cur, { productId: p.id, name: p.name, code: p.code, unit: p.base_unit, qty: 1, priceMinor: p.default_price_minor, max: Infinity }]);
                  setAddId("");
                }}
              >
                <Icon name="plus" />
                Add
              </button>
            </div>
          )}
          <div className="field">
            <label className="label" htmlFor="cr-reason">
              Reason <span className="opt">· required, shown in history</span>
            </label>
            <input className="input" id="cr-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Customer took 1 tea, not 2" />
          </div>
        </section>

        <section className="card" aria-label="Replacement order" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12, borderColor: "var(--brand-border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <span className="t-over" style={{ color: "var(--brand-text)" }}>
              3 · Replacement
            </span>
            <span className="badge b-brand">New order</span>
          </div>
          <div className="t-caption">{customerName(customerId)}</div>
          {kept.length === 0 ? (
            <p className="t-body-sm muted">No items. A replacement needs at least one item — to cancel the sale entirely, void the order instead.</p>
          ) : (
            <ul className="t-body-sm" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {kept.map((l) => (
                <li key={l.productId} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <span>
                    {l.name} × {l.qty}
                  </span>
                  <Money amountMinor={l.qty * l.priceMinor} currency={order.currency_code} />
                </li>
              ))}
            </ul>
          )}
          <div className="divider" />
          <div style={{ display: "flex", justifyContent: "space-between" }} className="t-h4">
            <span>Total</span>
            <Money amountMinor={newTotal} currency={order.currency_code} />
          </div>
          <div className="t-caption" style={{ color: diff === 0 ? "var(--text-muted)" : diff < 0 ? "var(--warning)" : "var(--success)" }}>
            {diff === 0 ? (
              "Same total as the original"
            ) : (
              <>
                <Money amountMinor={Math.abs(diff)} currency={order.currency_code} /> {diff < 0 ? "less" : "more"} than the original
              </>
            )}
          </div>
        </section>
      </div>

      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <span>{error}</span>
        </div>
      )}

      <div className="card" style={{ padding: "14px 18px", display: "flex", gap: 16, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
        <div className="t-body-sm secondary" style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
          <span>
            Stock effect:{" "}
            <b style={{ color: "var(--text-primary)" }}>
              {stockDelta === 0 ? "no net change" : stockDelta > 0 ? `${stockDelta} more ${stockDelta === 1 ? "unit" : "units"} out` : `${-stockDelta} ${stockDelta === -1 ? "unit" : "units"} back in stock`}
            </b>
          </span>
          <span>Recorded payments stay recorded</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" disabled={changeCount === 0 || kept.length === 0} onClick={review}>
            Review correction
          </button>
        </div>
      </div>

      <Modal
        open={reviewing}
        tone="warning"
        title="Submit correction?"
        description={`${order.order_number} will be marked Corrected and stop counting toward sales. A replacement order for ${customerName(customerId)} will be created.`}
        onClose={() => setReviewing(false)}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setReviewing(false)} disabled={correctMutation.isPending}>
              Back to editing
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void submit()} disabled={correctMutation.isPending} aria-busy={correctMutation.isPending}>
              {correctMutation.isPending && <span className="spinner" />}
              Submit correction
            </button>
          </>
        }
      >
        <div className="t-body" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="secondary">Original total</span>
            <Money amountMinor={order.order_total_minor} currency={order.currency_code} className="struck" />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="secondary">Replacement total</span>
            <Money amountMinor={newTotal} currency={order.currency_code} className="strong" />
          </div>
          <div className="t-caption">Reason: “{reason.trim()}”</div>
        </div>
      </Modal>
    </div>
  );
}
