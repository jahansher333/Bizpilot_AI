"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useProducts } from "@/hooks/use-catalog";
import { useInventoryBalances, useInventoryMovements } from "@/hooks/use-inventory";
import { LOW_STOCK_THRESHOLD, STOCK_LABEL, StockStatus, productThumb, stockStatus } from "@/lib/stock";
import { InventoryMovement } from "@/lib/schemas/inventory";
import { Icon } from "@/components/ui/icon";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { StockBadge, movementLabel } from "@/components/inventory/stock-detail";

interface InventoryViewProps {
  orgId: string;
  userRole?: string;
  token?: string;
}

type Filter = "all" | "healthy" | "low" | "out";
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "healthy", label: "In stock" },
  { key: "low", label: "Low stock" },
  { key: "out", label: "Out of stock" },
];

function formatWhen(iso: string) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

/** Design canvas "11 · Inventory". */
export function InventoryView({ orgId, userRole = "staff", token }: InventoryViewProps) {
  const canMutate = userRole === "owner" || userRole === "manager";
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const products = useProducts(orgId, { status: "active", limit: 100 }, token);
  const balances = useInventoryBalances(orgId, 100, 0, token);
  const movements = useInventoryMovements(orgId, { limit: 100 }, token);

  const onHand = useMemo(() => new Map((balances.data?.items ?? []).map((b) => [b.product_id, b.on_hand_quantity])), [balances.data]);
  const lastMovement = useMemo(() => {
    const map = new Map<string, InventoryMovement>();
    for (const m of movements.data?.items ?? []) {
      const prev = map.get(m.product_id);
      if (!prev || prev.created_at < m.created_at) map.set(m.product_id, m);
    }
    return map;
  }, [movements.data]);

  const rows = (products.data?.items ?? []).map((p) => {
    const qty = onHand.get(p.id);
    return { product: p, qty, status: stockStatus(qty) as StockStatus };
  });
  const counts = {
    healthy: rows.filter((r) => r.status === "healthy").length,
    low: rows.filter((r) => r.status === "low").length,
    out: rows.filter((r) => r.status === "out").length,
  };
  const q = query.trim().toLowerCase();
  const visible = rows.filter((r) => (filter === "all" || r.status === filter) && (!q || `${r.product.name} ${r.product.code}`.toLowerCase().includes(q)));
  const isLoading = products.isLoading || balances.isLoading;
  const error = products.error || balances.error;
  const filterLabel = FILTERS.find((f) => f.key === filter)?.label ?? "All";

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Inventory</h1>
          <p className="t-body secondary">Monitor and manage your current stock.</p>
        </div>
        <div className="ph-a">
          <span className="fresh">
            <span className="live" />
            Stock updates with every completed order
          </span>
          <Link className="btn btn-secondary btn-sm" href={`/workspace/${orgId}/catalog`}>
            Products
          </Link>
        </div>
      </div>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))", gap: 12 }} aria-label="Stock summary">
        <SummaryButton tone="healthy" count={counts.healthy} caption={`Above ${LOW_STOCK_THRESHOLD} on hand`} pressed={filter === "healthy"} onClick={() => setFilter(filter === "healthy" ? "all" : "healthy")} />
        <SummaryButton tone="low" count={counts.low} caption={`${LOW_STOCK_THRESHOLD} or fewer on hand`} pressed={filter === "low"} onClick={() => setFilter(filter === "low" ? "all" : "low")} />
        <SummaryButton tone="out" count={counts.out} caption="Can’t be added to orders" pressed={filter === "out"} onClick={() => setFilter(filter === "out" ? "all" : "out")} />
      </section>

      <div className="toolbar">
        <div className="seg" role="group" aria-label="Stock filter">
          {FILTERS.map((f) => (
            <button key={f.key} type="button" aria-pressed={filter === f.key} onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
        <div className="ig" style={{ width: 300, maxWidth: "100%", height: 36 }}>
          <span className="pre plain">
            <Icon name="search" />
          </span>
          <input placeholder="Search product or code" aria-label="Search inventory" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </div>

      {error && <ErrorState title="Couldn’t load inventory" message="Nothing was lost — check your connection, then try again." onRetry={() => void (products.refetch(), balances.refetch())} />}

      {isLoading && (
        <div className="tbl-wrap" aria-busy="true" aria-label="Loading inventory" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} height={14} />
          ))}
        </div>
      )}

      {!isLoading && products.data && rows.length === 0 && (
        <div className="card">
          <EmptyState
            icon="inventory"
            title="No products yet"
            description="Add products first, then record how many you have on hand."
            action={
              canMutate ? (
                <Link className="btn btn-primary" href={`/workspace/${orgId}/catalog`}>
                  Add products
                </Link>
              ) : undefined
            }
          />
        </div>
      )}

      {!isLoading && rows.length > 0 && visible.length === 0 && (
        <div className="card">
          <EmptyState icon="search" title="Nothing in this view" description={q ? "No products match your search." : "No products have this stock status right now."} />
        </div>
      )}

      {visible.length > 0 && (
        <div className="tbl-wrap fade-in" style={{ maxHeight: 640, overflow: "auto" }}>
          <table className="tbl">
            <caption className="sr-only">Inventory, filtered to {filterLabel}</caption>
            <thead>
              <tr>
                <th>Product</th>
                <th>Code</th>
                <th className="r">Available</th>
                <th>Stock status</th>
                <th>Last movement</th>
                <th className="r">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map(({ product, qty, status }) => {
                const mv = lastMovement.get(product.id);
                const detail = `/workspace/${orgId}/inventory/${product.id}`;
                return (
                  <tr key={product.id}>
                    <td>
                      <div className="cell-main">
                        <span className="thumb">{productThumb(product.code, product.name)}</span>
                        <Link className="t" href={detail}>
                          {product.name}
                        </Link>
                      </div>
                    </td>
                    <td className="mono muted">{product.code}</td>
                    <td className="r">
                      {qty === undefined ? (
                        <span className="muted">—</span>
                      ) : (
                        <>
                          <span className="num strong" style={{ fontSize: 14 }}>
                            {qty}
                          </span>{" "}
                          <span className="muted t-body-sm">{product.base_unit}</span>
                        </>
                      )}
                    </td>
                    <td>
                      <StockBadge status={status} />
                    </td>
                    <td>
                      {mv ? (
                        <div style={{ display: "flex", flexDirection: "column" }}>
                          <span className="t-body-sm">
                            {movementLabel(mv.movement_type)}{" "}
                            <span className="num" style={{ color: mv.quantity_delta > 0 ? "var(--success)" : "var(--text-secondary)", fontWeight: 500 }}>
                              {mv.quantity_delta > 0 ? `+${mv.quantity_delta}` : `−${Math.abs(mv.quantity_delta)}`}
                            </span>
                          </span>
                          <span className="t-caption">{formatWhen(mv.created_at)}</span>
                        </div>
                      ) : (
                        <span className="t-caption">—</span>
                      )}
                    </td>
                    <td className="r">
                      <span className="row-actions">
                        {canMutate && (
                          <Link className="btn btn-secondary btn-sm" href={`${detail}?action=${qty === undefined ? "opening" : "adjust"}`} aria-label={`${qty === undefined ? "Set opening stock for" : "Adjust stock for"} ${product.name}`}>
                            {qty === undefined ? "Set stock" : "Adjust"}
                          </Link>
                        )}
                        <Link className="btn btn-ghost btn-sm" href={detail} aria-label={`Stock history for ${product.name}`}>
                          History
                        </Link>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {products.data && products.data.total > products.data.items.length && (
        <p className="t-caption">Showing the first {products.data.items.length} of {products.data.total} active products.</p>
      )}
    </div>
  );
}

function SummaryButton({ tone, count, caption, pressed, onClick }: { tone: "healthy" | "low" | "out"; count: number; caption: string; pressed: boolean; onClick: () => void }) {
  const color = tone === "low" ? "var(--warning)" : tone === "out" ? "var(--danger)" : undefined;
  const border = tone === "low" ? "var(--warning-border)" : tone === "out" ? "var(--danger-border)" : undefined;
  return (
    <button
      type="button"
      className="card metric"
      aria-pressed={pressed}
      onClick={onClick}
      style={{ textAlign: "left", cursor: "pointer", font: "inherit", color: "inherit", borderColor: border, boxShadow: pressed ? "var(--focus)" : undefined }}
    >
      <span className="metric-l" style={{ color }}>
        {tone === "healthy" && <Icon name="check" size="sm" style={{ color: "var(--success)" }} />}
        {tone === "low" && <Icon name="alert" size="sm" />}
        {tone === "out" && <Icon name="close" size="sm" />}
        {STOCK_LABEL[tone]}
      </span>
      <span className="num" style={{ font: "600 26px/34px var(--font)" }}>
        {count}
      </span>
      <span className="metric-c">{caption}</span>
    </button>
  );
}
