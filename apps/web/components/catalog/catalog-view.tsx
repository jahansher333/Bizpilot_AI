"use client";

import React, { useContext, useMemo, useState } from "react";
import { AuthContext } from "@/components/providers/auth-provider";
import { useCategories, useProducts } from "@/hooks/use-catalog";
import { Icon } from "@/components/ui/icon";
import { ProductList } from "./product-list";
import { CategoryList } from "./category-list";

export interface CatalogViewProps {
  organizationId: string;
  userRole?: "owner" | "manager" | "staff";
  token?: string;
}

/** Design canvas "09–10 · Products & Categories". */
export function CatalogView({ organizationId, userRole = "staff", token }: CatalogViewProps) {
  const auth = useContext(AuthContext);
  const effectiveToken = token || auth?.token || undefined;
  const [activeTab, setActiveTab] = useState<"products" | "categories">("products");
  const [addProductOpen, setAddProductOpen] = useState(false);
  const [newCategoryOpen, setNewCategoryOpen] = useState(false);
  const canMutate = userRole === "owner" || userRole === "manager";

  const { data: productCount } = useProducts(organizationId, { status: "all", limit: 100 }, effectiveToken);
  const { data: categoryCount } = useCategories(organizationId, { status: "all", limit: 100 }, effectiveToken);

  // Per-category counts are only shown when every product fits in one page, so they are never partial.
  const productCounts = useMemo(() => {
    if (!productCount || productCount.total > productCount.items.length) return null;
    const counts = new Map<string, number>();
    for (const p of productCount.items) {
      if (p.category_id) counts.set(p.category_id, (counts.get(p.category_id) ?? 0) + 1);
    }
    return counts;
  }, [productCount]);

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Products</h1>
          <p className="t-body secondary">Your catalog, prices and categories.</p>
        </div>
        {canMutate && (
          <div className="ph-a">
            {activeTab === "products" ? (
              <button type="button" className="btn btn-primary" onClick={() => setAddProductOpen(true)}>
                <Icon name="plus" />
                Add product
              </button>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => setNewCategoryOpen(true)}>
                <Icon name="plus" />
                New category
              </button>
            )}
          </div>
        )}
      </div>

      <div className="tabs" role="tablist" aria-label="Catalog">
        <button type="button" className="tab" role="tab" aria-selected={activeTab === "products"} onClick={() => setActiveTab("products")}>
          Products
          {productCount && <span className="count">{productCount.total}</span>}
        </button>
        <button type="button" className="tab" role="tab" aria-selected={activeTab === "categories"} onClick={() => setActiveTab("categories")}>
          Categories
          {categoryCount && <span className="count">{categoryCount.total}</span>}
        </button>
      </div>

      {activeTab === "products" ? (
        <ProductList
          organizationId={organizationId}
          userRole={userRole}
          token={effectiveToken}
          addOpen={addProductOpen}
          onAddOpenChange={setAddProductOpen}
          onShowCategories={() => setActiveTab("categories")}
        />
      ) : (
        <CategoryList
          organizationId={organizationId}
          userRole={userRole}
          token={effectiveToken}
          productCounts={productCounts}
          createOpen={newCategoryOpen}
          onCreateOpenChange={setNewCategoryOpen}
        />
      )}
    </div>
  );
}
