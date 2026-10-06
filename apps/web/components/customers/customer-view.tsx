"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useCustomerBalances, useCustomers } from "@/hooks/use-customers";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";
import { Money } from "@/components/ui/money";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { CustomerModal } from "@/components/customers/customer-modal";

interface CustomerViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
}

type Filter = "all" | "balance" | "archived";
const PAGE_SIZE = 100;

/** Design canvas "14 · Customers". Balances are a financial view for Owners and Managers. */
export function CustomerView({ orgId, userRole = "staff", token }: CustomerViewProps) {
  const canSeeBalances = userRole === "owner" || userRole === "manager";
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(0);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setPage(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, error, refetch } = useCustomers(
    orgId,
    { status: filter === "archived" ? "archived" : "active", search: debounced || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
    token
  );
  const { data: activeTotal } = useCustomers(orgId, { status: "active", limit: 1, offset: 0 }, token);
  const balances = useCustomerBalances(orgId, undefined, canSeeBalances, token);
  const byId = useMemo(() => new Map((balances.data?.items ?? []).map((b) => [b.customer_id, b])), [balances.data]);
  const currency = balances.data?.currency_code ?? "PKR";

  const customers = (data?.items ?? []).filter((c) => filter !== "balance" || (byId.get(c.id)?.balance_minor ?? 0) > 0);
  const base = `/workspace/${orgId}`;

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Customers</h1>
          <p className="t-body secondary">
            {canSeeBalances ? "Everyone you sell to, with what they’ve bought and what they owe." : "Everyone you sell to. Orders can also be recorded as walk-in sales."}
          </p>
        </div>
        <div className="ph-a">
          <button type="button" className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
            <Icon name="plus" />
            Add customer
          </button>
        </div>
      </div>

      <section className="sum-grid" aria-label="Customer summary">
        <div className="card metric">
          <span className="metric-l">Total customers</span>
          <span className="num" style={{ font: "600 24px/32px var(--font)" }}>
            {activeTotal?.total ?? "—"}
          </span>
          <span className="metric-c">Active · walk-in sales not included</span>
        </div>
        {canSeeBalances && (
          <>
            <div className="card metric">
              <span className="metric-l">Customers with orders</span>
              <span className="num" style={{ font: "600 24px/32px var(--font)" }}>
                {balances.data?.customers_with_orders ?? "—"}
              </span>
              <span className="metric-c">At least one completed order</span>
            </div>
            <div className="card metric">
              <span className="metric-l">Outstanding balance</span>
              {balances.data ? (
                <Money amountMinor={balances.data.outstanding_minor} currency={currency} style={{ font: "600 24px/32px var(--font)" }} />
              ) : (
                <span className="num" style={{ font: "600 24px/32px var(--font)" }}>
                  —
                </span>
              )}
              <span className="metric-c">
                Completed orders − recorded payments
                {balances.data ? ` · ${balances.data.customers_with_balance} ${balances.data.customers_with_balance === 1 ? "customer" : "customers"}` : ""}
              </span>
            </div>
          </>
        )}
      </section>

      <div className="alert a-neutral">
        <Icon name="info" />
        <span>
          <b>Walk-in sales:</b> a customer profile is optional. Orders can be recorded without one.
        </span>
      </div>

      <div className="toolbar">
        <div className="ig" style={{ width: 340, maxWidth: "100%", height: 36 }}>
          <span className="pre plain">
            <Icon name="search" />
          </span>
          <input placeholder="Search by name or phone" aria-label="Search customers" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <button type="button" className="chip" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>
          All
        </button>
        {canSeeBalances && (
          <button type="button" className="chip" aria-pressed={filter === "balance"} onClick={() => setFilter("balance")}>
            Has balance
          </button>
        )}
        <button
          type="button"
          className="chip"
          aria-pressed={filter === "archived"}
          onClick={() => {
            setFilter("archived");
            setPage(0);
          }}
        >
          Archived
        </button>
      </div>

      {error && <ErrorState title="Couldn’t load customers" message="Nothing was lost — check your connection, then try again." onRetry={() => void refetch()} />}

      {isLoading && (
        <div className="tbl-wrap" aria-busy="true" aria-label="Loading customers" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <Skeleton width={28} height={28} radius={14} />
              <Skeleton width={180} height={12} />
            </div>
          ))}
        </div>
      )}

      {data && customers.length === 0 && (
        <div className="card">
          {debounced ? (
            <EmptyState icon="search" title={`No customers match “${debounced}”`} description="Check the spelling, or search by phone number." />
          ) : filter === "archived" ? (
            <EmptyState icon="customers" title="No archived customers" />
          ) : filter === "balance" ? (
            <EmptyState icon="customers" title="Nobody owes you right now" description="Customers appear here when their recorded orders are more than their recorded payments." />
          ) : (
            <EmptyState
              icon="customers"
              title="Add your first customer"
              description="Customers are optional — add the ones you sell to regularly to track their orders and payments."
              action={
                <button type="button" className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
                  Add customer
                </button>
              }
            />
          )}
        </div>
      )}

      {customers.length > 0 && (
        <>
          <div className="tbl-wrap desk-only">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Phone</th>
                  {canSeeBalances && <th className="r">Orders</th>}
                  {canSeeBalances && <th className="r">Balance</th>}
                  <th>Status</th>
                  <th className="r">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {customers.map((c) => {
                  const bal = byId.get(c.id);
                  const owes = (bal?.balance_minor ?? 0) > 0;
                  return (
                    <tr key={c.id} className={c.status === "archived" ? "is-void" : ""}>
                      <td>
                        <div className="cell-main">
                          <span className="av">{initials(c.name)}</span>
                          <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                            <Link className="t" href={`${base}/customers/${c.id}`}>
                              {c.name}
                            </Link>
                            {c.email && <span className="cell-sub">{c.email}</span>}
                          </div>
                        </div>
                      </td>
                      <td className="num secondary">{c.phone || "—"}</td>
                      {canSeeBalances && <td className="r">{bal?.order_count ?? 0}</td>}
                      {canSeeBalances && (
                        <td className="r">
                          <Money amountMinor={bal?.balance_minor ?? 0} currency={currency} className="strong" style={{ color: owes ? "var(--text-primary)" : "var(--text-muted)" }} />
                          {owes && <div className="t-caption">owes you</div>}
                        </td>
                      )}
                      <td>
                        <span className={`badge ${c.status === "active" ? "b-success" : "b-neutral"}`}>{c.status === "active" ? "Active" : "Archived"}</span>
                      </td>
                      <td className="r">
                        <span className="row-actions">
                          <Link className="btn btn-ghost btn-sm" href={`${base}/customers/${c.id}`} aria-label={`View ${c.name}`}>
                            View
                          </Link>
                          {c.status === "active" && (
                            <Link className="btn btn-secondary btn-sm" href={`${base}/orders?customerId=${c.id}`} aria-label={`New order for ${c.name}`}>
                              New order
                            </Link>
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

          <ul className="only-sm" style={{ flexDirection: "column", gap: 8 }} aria-label="Customers">
            {customers.map((c) => {
              const bal = byId.get(c.id);
              return (
                <li key={c.id} className="card" style={{ padding: "12px 14px", display: "flex", gap: 12, alignItems: "center" }}>
                  <span className="av lg">{initials(c.name)}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Link className="strong t-body-sm" href={`${base}/customers/${c.id}`} style={{ color: "var(--text-primary)", textDecoration: "none" }}>
                      {c.name}
                    </Link>
                    <div className="t-caption num">
                      {c.phone || "No phone"}
                      {canSeeBalances && bal ? ` · ${bal.order_count} orders` : ""}
                    </div>
                  </div>
                  {canSeeBalances && <Money amountMinor={bal?.balance_minor ?? 0} currency={currency} className="strong t-body-sm" />}
                </li>
              );
            })}
          </ul>
        </>
      )}

      <CustomerModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} orgId={orgId} token={token} />
    </div>
  );
}
