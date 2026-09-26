"use client";

import { useState } from "react";
import Link from "next/link";
import { ProductList } from "./product-list";
import { CategoryList } from "./category-list";

export interface CatalogViewProps {
  organizationId: string;
  initialRole?: "owner" | "manager" | "staff";
  token?: string;
}

export function CatalogView({
  organizationId,
  initialRole = "owner",
  token,
}: CatalogViewProps) {
  const [activeTab, setActiveTab] = useState<"products" | "categories">("products");
  const [currentRole, setCurrentRole] = useState<"owner" | "manager" | "staff">(initialRole);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Top bar with Title & Role context */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
                BizPilot AI
              </span>
              <span className="text-slate-300">•</span>
              <span className="font-mono text-xs text-slate-500">Org: {organizationId}</span>
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              Catalog Management
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Manage inventory products, categories, base units, and standard prices in PKR.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={`/workspace/${organizationId}/inventory`}
              className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 shadow-xs hover:bg-slate-50"
            >
              Check Inventory Stock
            </Link>

            {/* Role badge and simulator for permission preview */}
            <div className="flex items-center space-x-3 rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
              <span className="text-xs font-medium text-slate-500">Active Role:</span>
              <select
                aria-label="Select role for preview"
                value={currentRole}
                onChange={(e) =>
                  setCurrentRole(e.target.value as "owner" | "manager" | "staff")
                }
                className="rounded border border-slate-300 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-800 focus:border-emerald-500 focus:outline-none"
              >
                <option value="owner">Owner (Full Access)</option>
                <option value="manager">Manager (Full Access)</option>
                <option value="staff">Staff (Read-Only)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="mb-6 border-b border-slate-200">
          <nav className="-mb-px flex space-x-8" aria-label="Catalog sections">
            <button
              type="button"
              onClick={() => setActiveTab("products")}
              className={`whitespace-nowrap border-b-2 py-3 px-1 text-sm font-medium transition-colors ${
                activeTab === "products"
                  ? "border-emerald-600 text-emerald-600"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              Products
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("categories")}
              className={`whitespace-nowrap border-b-2 py-3 px-1 text-sm font-medium transition-colors ${
                activeTab === "categories"
                  ? "border-emerald-600 text-emerald-600"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
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
              token={token}
            />
          ) : (
            <CategoryList
              organizationId={organizationId}
              userRole={currentRole}
              token={token}
            />
          )}
        </main>
      </div>
    </div>
  );
}
