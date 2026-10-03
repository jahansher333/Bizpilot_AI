"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useCategories, useProduct } from "@/hooks/use-catalog";
import { useInventoryMovements, useProductBalance } from "@/hooks/use-inventory";
import { useOptionalAuth } from "@/hooks/use-auth";
import { InventoryMovement, MovementType } from "@/lib/schemas/inventory";
import { LOW_STOCK_THRESHOLD, STOCK_LABEL, StockStatus, productThumb, stockStatus } from "@/lib/stock";
import { Icon, IconName } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { StockChangeModal, StockChangeMode } from "@/components/inventory/stock-change-modal";
import { OpeningStockModal } from "@/components/inventory/opening-stock-modal";

const MOVEMENT: Record<MovementType, { label: string; dot: string; chip: string; icon: IconName }> = {
  opening: { label: "Opening stock", dot: "in", chip: "b-brand", icon: "products" },
  sale: { label: "Sale", dot: "out", chip: "b-neutral", icon: "orders" },
  adjustment: { label: "Adjustment", dot: "", chip: "b-info", icon: "inventory" },
  correction: { label: "Correction", dot: "", chip: "b-info", icon: "check" },
  void_reversal: { label: "Order void reversal", dot: "in", chip: "b-success", icon: "refresh" },
};

export function movementLabel(type: MovementType): string {
  return MOVEMENT[type]?.label ?? type;
}

export function StockBadge({ status }: { status: StockStatus }) {
  const cls = { healthy: "b-success", low: "b-warning", out: "b-danger", untracked: "b-neutral" }[status];
  const icon: IconName | null = status === "healthy" ? "check" : status === "low" ? "alert" : status === "out" ? "close" : null;
  return (
    <span className={`badge ${cls}`}>
      {icon && <Icon name={icon} />}
      {STOCK_LABEL[status]}
    </span>
  );
}

function formatWhen(iso: string) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

interface StockDetailProps {
  orgId: string;
  productId: string;
  userRole?: string;
  initialAction?: "adjust" | "correct" | "opening" | null;
  token?: string;
}

/** Design canvas "12 · Stock detail": movement audit trail, current stock and product details. */
export function StockDetail({ orgId, productId, userRole = "staff", initialAction = null, token }: StockDetailProps) {
  const canMutate = userRole === "owner" || userRole === "manager";
  const currentUserId = useOptionalAuth()?.user?.id;
  const product = useProduct(orgId, productId, token);
  const balance = useProductBalance(orgId, productId, token);
  const movements = useInventoryMovements(orgId, { productId, limit: 100 }, token);
  const { data: categories } = useCategories(orgId, { status: "all", limit: 100 }, token);
  const [typeFilter, setTypeFilter] = useState<MovementType | "all">("all");
  const [mode, setMode] = useState<StockChangeMode | null>(canMutate && (initialAction === "adjust" || initialAction === "correct") ? initialAction : null);
  const [openingOpen, setOpeningOpen] = useState(canMutate && initialAction === "opening");

  // A missing balance means no opening stock yet; any other failure is an error.
  const balanceMissing = !!balance.error && (balance.error as { status?: number }).status === 404;
  const qty = balance.data?.on_hand_quantity ?? null;
  const status = stockStatus(qty);

  // Running balance after each movement, newest first, derived from the current balance.
  const timeline = useMemo(() => {
    const items = [...(movements.data?.items ?? [])].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    let running = qty ?? 0;
    const withBalance = items.map((m) => {
      const after = running;
      running -= m.quantity_delta;
      return { m, after };
    });
    return withBalance;
  }, [movements.data, qty]);
  const visible = typeFilter === "all" ? timeline : timeline.filter((t) => t.m.movement_type === typeFilter);

  if (product.error) {
    return (
      <div className="main page-in">
        <BackLink orgId={orgId} />
        <ErrorState title="Couldn’t load this product" message="It may have been removed, or you may not have access." onRetry={() => void product.refetch()} />
      </div>
    );
  }

  if (!product.data) {
    return (
      <div className="main page-in" aria-busy="true" aria-label="Loading product">
        <BackLink orgId={orgId} />
        <Skeleton width={280} height={28} />
        <Skeleton height={200} />
      </div>
    );
  }

  const p = product.data;
  const categoryName = p.category_id ? (categories?.items ?? []).find((c) => c.id === p.category_id)?.name : null;
  const progress = qty === null ? 0 : Math.min(100, (qty / (LOW_STOCK_THRESHOLD * 4)) * 100);
  const latest = timeline[0]?.m;

  return (
    <div className="main page-in">
      <BackLink orgId={orgId} />
      <div className="ph">
        <div style={{ display: "flex", gap: 16, alignItems: "center", minWidth: 0 }}>
          <span className="thumb lg" style={{ width: 56, height: 56 }}>
            {productThumb(p.code, p.name)}
          </span>
          <div className="ph-t">
            <h1 className="t-h1">{p.name}</h1>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <span className="mono muted">{p.code}</span>
              {categoryName && (
                <>
                  <span className="muted">·</span>
                  <span className="t-body-sm secondary">{categoryName}</span>
                </>
              )}
              {p.status === "archived" ? <span className="badge b-neutral">Archived</span> : <StockBadge status={status} />}
            </div>
          </div>
        </div>
        {canMutate && (
          <div className="ph-a">
            {qty === null && balanceMissing ? (
              <button type="button" className="btn btn-primary" onClick={() => setOpeningOpen(true)}>
                <Icon name="plus" />
                Set opening stock
              </button>
            ) : (
              qty !== null && (
                <>
                  <button type="button" className="btn btn-secondary" onClick={() => setMode("correct")}>
                    <Icon name="check" />
                    Correct stock
                  </button>
                  <button type="button" className="btn btn-primary" onClick={() => setMode("adjust")}>
                    <Icon name="inventory" />
                    Adjust stock
                  </button>
                </>
              )
            )}
          </div>
        )}
      </div>

      {balance.error && !balanceMissing && <ErrorState title="Couldn’t load the current stock" onRetry={() => void balance.refetch()} />}

      <div className="split">
        <div className="l">
          <section className="card" aria-labelledby="mv-h">
            <div className="card-h">
              <div style={{ display: "flex", flexDirection: "column" }}>
                <h2 className="t-h3" id="mv-h">
                  Stock movements
                </h2>
                <span className="t-caption">Audit trail · every change is kept, nothing is overwritten</span>
              </div>
              <select className="input" style={{ width: 180, height: 32 }} aria-label="Filter movements by type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as MovementType | "all")}>
                <option value="all">All types</option>
                {(Object.keys(MOVEMENT) as MovementType[]).map((t) => (
                  <option key={t} value={t}>
                    {MOVEMENT[t].label}
                  </option>
                ))}
              </select>
            </div>
            <div className="card-b">
              {movements.error && <ErrorState title="Couldn’t load stock movements" onRetry={() => void movements.refetch()} />}
              {movements.isLoading && <Skeleton height={120} />}
              {movements.data && visible.length === 0 && (
                <EmptyState icon="inventory" title="No movements yet" description={qty === null ? "Set the opening stock to start this product’s timeline." : "Nothing matches this filter."} />
              )}
              {visible.length > 0 && (
                <ol className="tl stagger">
                  {visible.map(({ m, after }) => (
                    <MovementRow key={m.id} m={m} after={after} unit={p.base_unit} orgId={orgId} you={!!currentUserId && m.created_by_user_id === currentUserId} />
                  ))}
                </ol>
              )}
              {movements.data && movements.data.total > movements.data.items.length && (
                <p className="t-caption" style={{ marginTop: 12 }}>
                  Showing the latest {movements.data.items.length} of {movements.data.total} movements.
                </p>
              )}
            </div>
          </section>
        </div>

        <div className="r">
          <section className="card">
            <div className="card-b" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span className="metric-l">Current stock</span>
              {qty === null ? (
                <span className="t-body secondary">{balanceMissing ? "No stock recorded yet." : "—"}</span>
              ) : (
                <>
                  <span className="num" style={{ font: "600 40px/46px var(--font)", letterSpacing: "-0.03em" }}>
                    {qty}{" "}
                    <span style={{ fontSize: 16, fontWeight: 500, color: "var(--text-muted)", letterSpacing: 0 }}>{p.base_unit}</span>
                  </span>
                  {latest && (
                    <span className="fresh">
                      <span className="live" />
                      Last change: {movementLabel(latest.movement_type)} · {formatWhen(latest.created_at)}
                    </span>
                  )}
                  <div className="progress" style={{ marginTop: 10 }} role="img" aria-label={`${qty} ${p.base_unit}, low-stock level ${LOW_STOCK_THRESHOLD}`}>
                    <span style={{ width: `${progress}%`, background: status === "healthy" ? undefined : status === "low" ? "var(--warning)" : "var(--danger)" }} />
                  </div>
                  <div className="t-caption" style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Low-stock level {LOW_STOCK_THRESHOLD}</span>
                    <span>{STOCK_LABEL[status]}</span>
                  </div>
                </>
              )}
            </div>
          </section>
          <section className="card">
            <div className="card-h">
              <h2 className="t-h4">Product details</h2>
              {canMutate && (
                <Link className="link t-body-sm" href={`/workspace/${orgId}/catalog`}>
                  Edit in Products
                </Link>
              )}
            </div>
            <dl style={{ margin: 0, padding: "4px 18px 10px" }}>
              <DetailRow label="Selling price">
                <Money amountMinor={p.default_price_minor} currency={p.currency_code} className="strong" />
              </DetailRow>
              <DetailRow label="Category">{categoryName ?? "—"}</DetailRow>
              <DetailRow label="Unit">{p.base_unit}</DetailRow>
              <DetailRow label="Status" last>
                <span className={`badge ${p.status === "archived" ? "b-neutral" : "b-success"}`}>{p.status === "archived" ? "Archived" : "Active"}</span>
              </DetailRow>
            </dl>
          </section>
          <div className="alert a-neutral">
            <Icon name="info" />
            <span>
              <b>Adjust</b> adds or removes units with a reason (delivery, damage). <b>Correct</b> sets stock to what you physically counted.
            </span>
          </div>
        </div>
      </div>

      {qty !== null && (
        <StockChangeModal
          orgId={orgId}
          productId={p.id}
          productName={p.name}
          productCode={p.code}
          unit={p.base_unit}
          currentQuantity={qty}
          mode={mode}
          onClose={() => setMode(null)}
          token={token}
        />
      )}
      <OpeningStockModal orgId={orgId} productId={p.id} productName={p.name} unit={p.base_unit} isOpen={openingOpen && balanceMissing} onClose={() => setOpeningOpen(false)} token={token} />
    </div>
  );
}

function BackLink({ orgId }: { orgId: string }) {
  return (
    <Link className="link t-body-sm" href={`/workspace/${orgId}/inventory`} style={{ display: "inline-flex", alignItems: "center", gap: 4, alignSelf: "flex-start" }}>
      <Icon name="chevronLeft" size="sm" />
      Inventory
    </Link>
  );
}

function DetailRow({ label, children, last }: { label: string; children: React.ReactNode; last?: boolean }) {
  return (
    <div className="t-body-sm" style={{ display: "flex", justifyContent: "space-between", padding: "9px 0", borderBottom: last ? 0 : "1px solid var(--border)" }}>
      <dt className="secondary">{label}</dt>
      <dd style={{ margin: 0 }}>{children}</dd>
    </div>
  );
}

function MovementRow({ m, after, unit, orgId, you }: { m: InventoryMovement; after: number; unit: string; orgId: string; you: boolean }) {
  const meta = MOVEMENT[m.movement_type];
  const delta = m.quantity_delta > 0 ? `+${m.quantity_delta}` : `−${Math.abs(m.quantity_delta)}`;
  const dot = m.movement_type === "adjustment" || m.movement_type === "correction" ? (m.quantity_delta > 0 ? "in" : "warn") : meta.dot;
  return (
    <li className="tl-row">
      <span className={`tl-dot ${dot}`} aria-hidden="true">
        <Icon name={meta.icon} />
      </span>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "4px 16px", paddingTop: 3 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span className="t-h4">{meta.label}</span>
          <span className={`badge square ${meta.chip}`} style={{ height: 20 }}>
            {delta}
          </span>
          {m.source_type === "order" && m.source_id && (
            <Link className="link t-body-sm" href={`/workspace/${orgId}/orders`}>
              View order
            </Link>
          )}
        </div>
        <div style={{ textAlign: "right" }}>
          <span className="t-body-sm secondary">Balance </span>
          <span className="num strong">
            {after} {unit}
          </span>
        </div>
        <span className="t-body-sm secondary">{m.reason || (m.movement_type === "sale" ? "Completed order" : "—")}</span>
        <span className="t-caption" style={{ textAlign: "right" }}>
          {formatWhen(m.created_at)}
          {you ? " · You" : ""}
        </span>
      </div>
    </li>
  );
}
