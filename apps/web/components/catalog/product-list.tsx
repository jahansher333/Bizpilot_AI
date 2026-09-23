"use client";

import { useState } from "react";
import { Product, formatPriceMinor } from "@/lib/schemas/catalog";
import { useProducts, useCategories, useArchiveProduct } from "@/hooks/use-catalog";
import { ProductModal } from "./product-modal";

export interface ProductListProps {
  organizationId: string;
  userRole: "owner" | "manager" | "staff";
  token?: string;
}

export function ProductList({ organizationId, userRole, token }: ProductListProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "archived">("active");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [archivingProduct, setArchivingProduct] = useState<Product | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const canMutate = userRole === "owner" || userRole === "manager";

  const {
    data: productsData,
    isLoading: isProductsLoading,
    isError: isProductsError,
    error: productsError,
    refetch: refetchProducts,
  } = useProducts(
    organizationId,
    {
      status: statusFilter,
      category_id: categoryFilter || undefined,
    },
    token
  );

  // Fetch categories for filtering and name lookup
  const { data: categoriesData } = useCategories(
    organizationId,
    { status: "all", limit: 200 },
    token
  );

  const archiveMutation = useArchiveProduct(organizationId, token);

  const categoryMap = new Map<string, string>();
  categoriesData?.items.forEach((cat) => {
    categoryMap.set(cat.id, cat.name);
  });

  const handleOpenCreate = () => {
    setSelectedProduct(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (product: Product) => {
    setSelectedProduct(product);
    setIsModalOpen(true);
  };

  const handleConfirmArchive = async () => {
    if (!archivingProduct) return;
    setArchiveError(null);
    try {
      await archiveMutation.mutateAsync(archivingProduct.id);
      setArchivingProduct(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setArchiveError(err.message);
      } else {
        setArchiveError("Failed to archive product");
      }
    }
  };

  const products = productsData?.items ?? [];

  return (
    <div className="space-y-4">
      {/* Header controls & filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2">
            <label htmlFor="product-status-filter" className="text-sm font-medium text-slate-700">
              Status:
            </label>
            <select
              id="product-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "archived")}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              <option value="active">Active</option>
              <option value="archived">Archived</option>
              <option value="all">All</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <label htmlFor="product-category-filter" className="text-sm font-medium text-slate-700">
              Category:
            </label>
            <select
              id="product-category-filter"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              <option value="">All Categories</option>
              {categoriesData?.items.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name} {cat.status === "archived" ? "(Archived)" : ""}
                </option>
              ))}
            </select>
          </div>
        </div>

        {canMutate && (
          <button
            type="button"
            onClick={handleOpenCreate}
            className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 focus:outline-none"
          >
            + New Product
          </button>
        )}
      </div>

      {/* Error state */}
      {isProductsError && (
        <div role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          <p className="font-medium">Failed to load products</p>
          <p className="mt-1 text-xs">
            {productsError instanceof Error ? productsError.message : "Network error"}
          </p>
          <button
            type="button"
            onClick={() => refetchProducts()}
            className="mt-2 text-xs font-semibold text-red-800 underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {isProductsLoading && (
        <div data-testid="product-loading" className="space-y-2 py-4">
          <div className="h-12 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-12 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-12 w-full animate-pulse rounded bg-slate-100" />
        </div>
      )}

      {/* Empty state */}
      {!isProductsLoading && !isProductsError && products.length === 0 && (
        <div data-testid="product-empty" className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
          <p className="text-sm font-medium text-slate-700">No products found</p>
          <p className="mt-1 text-xs text-slate-500">
            {categoryFilter || statusFilter !== "all"
              ? "No products match the selected filters."
              : "Add your first product to build your catalog."}
          </p>
          {canMutate && (
            <button
              type="button"
              onClick={handleOpenCreate}
              className="mt-3 inline-flex items-center rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Add Product
            </button>
          )}
        </div>
      )}

      {/* Product table (desktop) / cards (mobile) */}
      {!isProductsLoading && !isProductsError && products.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Code / SKU
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Product Name
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Category
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Base Unit
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Default Price
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Status
                  </th>
                  {canMutate && (
                    <th scope="col" className="px-4 py-3 text-right">
                      Actions
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {products.map((prod) => (
                  <tr key={prod.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-mono text-xs font-medium text-slate-900">
                      {prod.code}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-900">{prod.name}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {prod.category_id ? (
                        categoryMap.get(prod.category_id) || "Assigned"
                      ) : (
                        <span className="italic text-slate-400">Uncategorized</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">{prod.base_unit}</td>
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {formatPriceMinor(prod.default_price_minor, prod.currency_code)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          prod.status === "active"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {prod.status}
                      </span>
                    </td>
                    {canMutate && (
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center space-x-2">
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(prod)}
                            className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                            aria-label={`Edit ${prod.name}`}
                          >
                            Edit
                          </button>
                          {prod.status === "active" ? (
                            <button
                              type="button"
                              onClick={() => {
                                setArchiveError(null);
                                setArchivingProduct(prod);
                              }}
                              className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 hover:text-red-700"
                              aria-label={`Archive ${prod.name}`}
                            >
                              Archive
                            </button>
                          ) : (
                            <span className="px-2 py-1 text-xs text-slate-400">Archived</span>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Product Modal */}
      {isModalOpen && (
        <ProductModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          organizationId={organizationId}
          product={selectedProduct}
          token={token}
        />
      )}

      {/* Archive Confirmation Dialog */}
      {archivingProduct && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="archive-product-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
        >
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h3 id="archive-product-title" className="text-base font-semibold text-slate-900">
              Archive Product
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Are you sure you want to archive{" "}
              <strong>
                [{archivingProduct.code}] {archivingProduct.name}
              </strong>
              ?
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Its code can be reused by a new product once archived. Historical records referencing it remain unchanged.
            </p>

            {archiveError && (
              <div role="alert" className="mt-3 rounded bg-red-50 p-2 text-xs text-red-700">
                {archiveError}
              </div>
            )}

            <div className="mt-4 flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setArchivingProduct(null)}
                disabled={archiveMutation.isPending}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmArchive}
                disabled={archiveMutation.isPending}
                className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {archiveMutation.isPending ? "Archiving..." : "Archive"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
