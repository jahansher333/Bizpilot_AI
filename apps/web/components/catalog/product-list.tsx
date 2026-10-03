"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { Product } from "@/lib/schemas/catalog";
import { useArchiveProduct, useCategories, useProducts } from "@/hooks/use-catalog";
import { useInventoryBalances } from "@/hooks/use-inventory";
import { LOW_STOCK_THRESHOLD, productThumb, stockStatus } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { ProductSheet } from "@/components/catalog/product-sheet";

export interface ProductListProps {
  organizationId: string;
  userRole: "owner" | "manager" | "staff";
  token?: string;
  addOpen?: boolean;
  onAddOpenChange?: (open: boolean) => void;
  onShowCategories?: () => void;
}

const PAGE_SIZE = 100;
const STOCK_COLOR = { healthy: "var(--text-primary)", low: "var(--warning)", out: "var(--danger)", untracked: "var(--text-muted)" } as const;

/** Design "09 · Products" tab. */
export function ProductList({ organizationId, userRole, token, addOpen = false, onAddOpenChange, onShowCategories }: ProductListProps) {
  const canMutate = userRole === "owner" || userRole === "manager";
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<Product | null>(null);
  const [archiving, setArchiving] = useState<Product | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [prefillName, setPrefillName] = useState("");
  const { notify } = useToast();

  const { data, isLoading, error, refetch } = useProducts(
    organizationId,
    { status: showArchived ? "all" : "active", category_id: categoryFilter || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
    token
  );
  const { data: allTotal } = useProducts(organizationId, { status: "all", limit: 1 }, token);
  const { data: activeTotal } = useProducts(organizationId, { status: "active", limit: 1 }, token);
  const { data: categories } = useCategories(organizationId, { status: "all", limit: 100 }, token);
  const { data: balances } = useInventoryBalances(organizationId, 100, 0, token);
  const archiveMutation = useArchiveProduct(organizationId, token);

  const categoryName = useMemo(() => new Map((categories?.items ?? []).map((c) => [c.id, c.name])), [categories]);
  const activeCategories = (categories?.items ?? []).filter((c) => c.status === "active");
  const onHand = useMemo(() => new Map((balances?.items ?? []).map((b) => [b.product_id, b.on_hand_quantity])), [balances]);

  const products = data?.items ?? [];
  const q = query.trim().toLowerCase();
  const rows = q ? products.filter((p) => `${p.name} ${p.code}`.toLowerCase().includes(q)) : products;

  const activeStatuses = products.filter((p) => p.status === "active").map((p) => stockStatus(onHand.get(p.id)));
  const lowCount = activeStatuses.filter((s) => s === "low").length;
  const outCount = activeStatuses.filter((s) => s === "out").length;

  async function confirmArchive() {
    if (!archiving) return;
    setArchiveError(null);
    try {
      await archiveMutation.mutateAsync(archiving.id);
      notify({ title: `“${archiving.name}” archived`, description: "It can’t be added to new orders. Past orders keep it." });
      setArchiving(null);
    } catch (err) {
      setArchiveError(err instanceof Error && err.message ? err.message : "Couldn’t archive the product.");
    }
  }

  function openAdd(name = "") {
    setPrefillName(name);
    onAddOpenChange?.(true);
  }

  const sheetOpen = addOpen || !!editing;
  const showEmpty = !!data && data.total === 0 && !categoryFilter && !showArchived;

  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <section className="sum-grid" aria-label="Catalog summary">
        <SummaryCard label="Total products" value={allTotal?.total} />
        <SummaryCard label="Active" value={activeTotal?.total} />
        <SummaryCard label="Low stock" value={balances ? lowCount : undefined} tone="low" />
        <SummaryCard label="Out of stock" value={balances ? outCount : undefined} tone="out" />
      </section>

      <div className="toolbar">
        <div className="ig" style={{ width: 320, maxWidth: "100%", height: 36 }}>
          <span className="pre plain">
            <Icon name="search" />
          </span>
          <input placeholder="Search by name or code" aria-label="Search products" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        {activeCategories.length > 0 && activeCategories.length <= 6 ? (
          <>
            <button type="button" className="chip" aria-pressed={categoryFilter === ""} onClick={() => setCategoryFilter("")}>
              All categories
            </button>
            {activeCategories.map((c) => (
              <button key={c.id} type="button" className="chip" aria-pressed={categoryFilter === c.id} onClick={() => setCategoryFilter(c.id)}>
                {c.name}
              </button>
            ))}
          </>
        ) : (
          activeCategories.length > 6 && (
            <select className="input" style={{ width: 200, height: 36 }} aria-label="Filter by category" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
              <option value="">All categories</option>
              {activeCategories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )
        )}
        <span style={{ flex: 1 }} />
        <label className="check">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={() => {
              setShowArchived((v) => !v);
              setPage(0);
            }}
          />
          Show archived
        </label>
      </div>

      {error && <ErrorState title="Couldn’t load your products" message="Nothing was lost — check your connection, then try again." onRetry={() => void refetch()} />}

      {isLoading && (
        <div className="tbl-wrap" aria-busy="true" aria-label="Loading products">
          <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
            {[180, 140, 200, 160, 120].map((w) => (
              <div key={w} style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <Skeleton width={34} height={34} radius={6} />
                <Skeleton width={w} height={12} />
              </div>
            ))}
          </div>
        </div>
      )}

      {showEmpty && (
        <div className="card">
          <EmptyState
            icon="products"
            title="Add your first product"
            description="Products power your orders, stock levels and AI answers. Start with the items you sell most — you can add the rest later."
            action={
              canMutate ? (
                <>
                  <button type="button" className="btn btn-primary" onClick={() => openAdd()}>
                    Add product
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={onShowCategories}>
                    Set up categories
                  </button>
                </>
              ) : undefined
            }
          />
        </div>
      )}

      {data && !showEmpty && rows.length === 0 && (
        <div className="card">
          <EmptyState
            icon="search"
            title={q ? `No products match “${query.trim()}”` : "No products in this view"}
            description={q ? "Check the spelling or search by product code." : "Try another category, or show archived products."}
            action={
              q ? (
                <>
                  <button type="button" className="btn btn-secondary" onClick={() => setQuery("")}>
                    Clear search
                  </button>
                  {canMutate && (
                    <button type="button" className="btn btn-primary" onClick={() => openAdd(query.trim())}>
                      Add “{query.trim()}” as product
                    </button>
                  )}
                </>
              ) : undefined
            }
          />
        </div>
      )}

      {rows.length > 0 && (
        <>
          <div className="tbl-wrap desk-only">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Code</th>
                  <th>Category</th>
                  <th className="r">Price</th>
                  <th className="r">Stock</th>
                  <th>Status</th>
                  {canMutate && (
                    <th className="r">
                      <span className="sr-only">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => {
                  const archived = p.status === "archived";
                  const qty = onHand.get(p.id);
                  const status = stockStatus(qty);
                  return (
                    <tr key={p.id} className={archived ? "is-void" : ""}>
                      <td>
                        <div className="cell-main">
                          <span className="thumb">{productThumb(p.code, p.name)}</span>
                          <Link className="t" href={`/workspace/${organizationId}/inventory/${p.id}`}>
                            {p.name}
                          </Link>
                        </div>
                      </td>
                      <td className="mono muted">{p.code}</td>
                      <td className="secondary">{p.category_id ? categoryName.get(p.category_id) ?? "—" : "—"}</td>
                      <td className="r">
                        <Money amountMinor={p.default_price_minor} currency={p.currency_code} className="strong" />
                      </td>
                      <td className="r">
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: archived ? "var(--text-muted)" : STOCK_COLOR[status], fontWeight: 500 }}>
                          {!archived && status === "low" && <Icon name="alert" size="sm" />}
                          {!archived && status === "out" && <Icon name="close" size="sm" />}
                          {qty ?? "—"}
                          <span className="sr-only">{status === "low" ? " — low stock" : status === "out" ? " — out of stock" : status === "untracked" ? " — no stock recorded" : ""}</span>
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${archived ? "b-neutral" : "b-success"}`}>{archived ? "Archived" : "Active"}</span>
                      </td>
                      {canMutate && (
                        <td className="r">
                          {!archived && (
                            <span className="row-actions">
                              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(p)} aria-label={`Edit ${p.name}`}>
                                Edit
                              </button>
                              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setArchiving(p)} aria-label={`Archive ${p.name}`}>
                                Archive
                              </button>
                            </span>
                          )}
                        </td>
                      )}
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

          <ul className="only-sm" style={{ flexDirection: "column", gap: 8 }} aria-label="Products">
            {rows.map((p) => {
              const qty = onHand.get(p.id);
              const status = stockStatus(qty);
              return (
                <li key={p.id} className="card" style={{ padding: "12px 14px", display: "flex", gap: 12, alignItems: "center" }}>
                  <span className="thumb lg">{productThumb(p.code, p.name)}</span>
                  <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                    <Link className="strong t-body-sm" href={`/workspace/${organizationId}/inventory/${p.id}`} style={{ color: "var(--text-primary)", textDecoration: "none" }}>
                      {p.name}
                    </Link>
                    <span className="mono muted" style={{ fontSize: 11.5 }}>
                      {p.code}
                      {p.category_id ? ` · ${categoryName.get(p.category_id) ?? ""}` : ""}
                    </span>
                    <span className="t-body-sm" style={{ color: STOCK_COLOR[status] }}>
                      {qty === undefined ? "No stock recorded" : `${qty} ${p.base_unit} in stock`}
                    </span>
                  </div>
                  <Money amountMinor={p.default_price_minor} currency={p.currency_code} className="strong t-body-sm" />
                </li>
              );
            })}
          </ul>
        </>
      )}

      <p className="t-caption">Low stock means {LOW_STOCK_THRESHOLD} or fewer on hand.</p>

      <ProductSheet
        organizationId={organizationId}
        token={token}
        open={sheetOpen}
        product={editing}
        initialName={prefillName}
        onClose={() => {
          setEditing(null);
          setPrefillName("");
          onAddOpenChange?.(false);
        }}
      />

      <Modal
        open={!!archiving}
        tone="warning"
        title={`Archive “${archiving?.name ?? ""}”?`}
        description="It can’t be added to new orders. Past orders and its stock history stay readable."
        onClose={() => {
          setArchiving(null);
          setArchiveError(null);
        }}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setArchiving(null)} disabled={archiveMutation.isPending}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" onClick={confirmArchive} disabled={archiveMutation.isPending} aria-busy={archiveMutation.isPending}>
              {archiveMutation.isPending && <span className="spinner" />}
              Archive product
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

function SummaryCard({ label, value, tone }: { label: string; value: number | undefined; tone?: "low" | "out" }) {
  const color = tone === "low" ? "var(--warning)" : tone === "out" ? "var(--danger)" : undefined;
  return (
    <div className="card metric" style={{ padding: "14px 16px" }}>
      <span className="metric-l" style={{ color }}>
        {tone === "low" && <Icon name="alert" size="sm" />}
        {tone === "out" && <Icon name="close" size="sm" />}
        {label}
      </span>
      <span className="num" style={{ font: "600 22px/30px var(--font)" }}>
        {value ?? "—"}
      </span>
    </div>
  );
}
