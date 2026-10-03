"use client";

import React, { useState } from "react";
import { Category } from "@/lib/schemas/catalog";
import { useArchiveCategory, useCategories } from "@/hooks/use-catalog";
import { Modal } from "@/components/ui/modal";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { CategoryModal } from "@/components/catalog/category-modal";

export interface CategoryListProps {
  organizationId: string;
  userRole: "owner" | "manager" | "staff";
  token?: string;
  /** Product counts per category id, when every product is loaded; otherwise counts are hidden. */
  productCounts?: Map<string, number> | null;
  createOpen?: boolean;
  onCreateOpenChange?: (open: boolean) => void;
}

/** Design "10 · Categories" tab. */
export function CategoryList({ organizationId, userRole, token, productCounts = null, createOpen = false, onCreateOpenChange }: CategoryListProps) {
  const canMutate = userRole === "owner" || userRole === "manager";
  const { data, isLoading, error, refetch } = useCategories(organizationId, { status: "all", limit: 100 }, token);
  const archiveMutation = useArchiveCategory(organizationId, token);
  const { notify } = useToast();
  const [renaming, setRenaming] = useState<Category | null>(null);
  const [archiving, setArchiving] = useState<Category | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const categories = [...(data?.items ?? [])].sort((a, b) => (a.status === b.status ? a.name.localeCompare(b.name) : a.status === "active" ? -1 : 1));

  async function confirmArchive() {
    if (!archiving) return;
    setArchiveError(null);
    try {
      await archiveMutation.mutateAsync(archiving.id);
      notify({ title: `“${archiving.name}” archived`, description: "Products keep this category." });
      setArchiving(null);
    } catch (err) {
      setArchiveError(err instanceof Error && err.message ? err.message : "Couldn’t archive the category.");
    }
  }

  return (
    <div className="fade-in" style={{ maxWidth: 760, display: "flex", flexDirection: "column", gap: 12 }}>
      <p className="t-body-sm secondary">Group products to find them faster. Archiving a category hides it from new products; existing products keep it.</p>

      {error && <ErrorState title="Couldn’t load your categories" message="Nothing was lost — check your connection, then try again." onRetry={() => void refetch()} />}

      {isLoading && (
        <div className="card card-b" aria-busy="true" aria-label="Loading categories" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Skeleton height={14} />
          <Skeleton height={14} />
          <Skeleton height={14} />
        </div>
      )}

      {data && categories.length === 0 && (
        <div className="card">
          <EmptyState
            icon="products"
            title="No categories yet"
            description="Categories are optional. Create a few, like “Rice & Grains” or “Beverages”, to group your products."
            action={
              canMutate ? (
                <button type="button" className="btn btn-primary" onClick={() => onCreateOpenChange?.(true)}>
                  New category
                </button>
              ) : undefined
            }
          />
        </div>
      )}

      {categories.length > 0 && (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Category</th>
                {productCounts && <th className="r">Products</th>}
                <th>Status</th>
                {canMutate && (
                  <th className="r">
                    <span className="sr-only">Actions</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {categories.map((cat) => {
                const archived = cat.status === "archived";
                return (
                  <tr key={cat.id} className={archived ? "is-void" : ""}>
                    <td className={archived ? "" : "strong"}>{cat.name}</td>
                    {productCounts && <td className="r">{productCounts.get(cat.id) ?? 0}</td>}
                    <td>
                      <span className={`badge ${archived ? "b-neutral" : "b-success"}`}>{archived ? "Archived" : "Active"}</span>
                    </td>
                    {canMutate && (
                      <td className="r">
                        {!archived && (
                          <span className="row-actions">
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRenaming(cat)} aria-label={`Rename ${cat.name}`}>
                              Rename
                            </button>
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setArchiving(cat)} aria-label={`Archive ${cat.name}`}>
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
        </div>
      )}

      <CategoryModal
        organizationId={organizationId}
        token={token}
        isOpen={createOpen || !!renaming}
        category={renaming}
        onClose={() => {
          setRenaming(null);
          onCreateOpenChange?.(false);
        }}
      />

      <Modal
        open={!!archiving}
        tone="warning"
        title={`Archive “${archiving?.name ?? ""}”?`}
        description="It won’t be offered for new products. Products already in this category keep it, and nothing is deleted."
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
              Archive category
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
