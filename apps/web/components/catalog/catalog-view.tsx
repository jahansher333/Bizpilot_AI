"use client";

import { useState, useContext } from "react";
import Link from "next/link";
import { AuthContext } from "@/components/providers/auth-provider";
import { ProductList } from "./product-list";
import { CategoryList } from "./category-list";

export interface CatalogViewProps {
  organizationId: string;
  userRole?: "owner" | "manager" | "staff";
  token?: string;
}

export function CatalogView({
  organizationId,
  userRole = "staff",
  token,
}: CatalogViewProps) {
  const auth = useContext(AuthContext);
  const effectiveToken = token || auth?.token || undefined;
  const [activeTab, setActiveTab] = useState<"products" | "categories">("products");
  const currentRole = userRole;

  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-6">
        {/* Top bar with Title & Role context (Stitch Header) */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-label-caps text-[11px] uppercase tracking-wider text-primary font-semibold">
                BizPilot AI
              </span>
              <span className="text-outline">•</span>
              <span className="font-mono text-xs text-outline">Org: {organizationId}</span>
            </div>
            <h1 className="mt-1 font-display-lg text-2xl sm:text-3xl font-bold tracking-tight text-on-surface">
              Catalog Management
            </h1>
            <p className="mt-1 font-body-md text-sm text-on-surface-variant">
              Manage inventory products, categories, base units, and standard prices in PKR.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={`/workspace/${organizationId}/inventory`}
              className="inline-flex items-center rounded-xl border border-outline-variant/60 bg-surface-container-lowest px-3.5 py-2 text-xs font-semibold text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
            >
              Check Inventory Stock
            </Link>

            {/* Role badge (read-only; role comes from the verified membership) */}
            <span className="rounded-xl border border-surface-container-high bg-surface-container-lowest px-3 py-2 text-xs font-semibold capitalize text-on-surface shadow-xs">
              Your role: {currentRole}
            </span>
          </div>
        </div>

        {/* Tab navigation (Stitch Segmented Style) */}
        <div className="border-b border-surface-container-high">
          <nav className="-mb-px flex space-x-6" aria-label="Catalog sections">
            <button
              type="button"
              onClick={() => setActiveTab("products")}
              className={`whitespace-nowrap border-b-2 py-3 px-2 text-sm font-semibold transition-colors ${
                activeTab === "products"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:border-outline hover:text-on-surface"
              }`}
            >
              Products
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("categories")}
              className={`whitespace-nowrap border-b-2 py-3 px-2 text-sm font-semibold transition-colors ${
                activeTab === "categories"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:border-outline hover:text-on-surface"
              }`}
            >
              Categories
            </button>
          </nav>
        </div>

        {/* Content area */}
        <main>
          {activeTab === "products" ? (
            <ProductList
              organizationId={organizationId}
              userRole={currentRole}
              token={effectiveToken}
            />
          ) : (
            <CategoryList
              organizationId={organizationId}
              userRole={currentRole}
              token={effectiveToken}
            />
          )}
        </main>
      </div>
    </div>
  );
}
