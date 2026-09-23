"use client";

import { useState } from "react";
import { Category } from "@/lib/schemas/catalog";
import { useCategories, useArchiveCategory } from "@/hooks/use-catalog";
import { CategoryModal } from "./category-modal";

export interface CategoryListProps {
  organizationId: string;
  userRole: "owner" | "manager" | "staff";
  token?: string;
}

export function CategoryList({ organizationId, userRole, token }: CategoryListProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "archived">("active");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);
  const [archivingCategory, setArchivingCategory] = useState<Category | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const canMutate = userRole === "owner" || userRole === "manager";

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useCategories(organizationId, { status: statusFilter }, token);

  const archiveMutation = useArchiveCategory(organizationId, token);

  const handleOpenCreate = () => {
    setSelectedCategory(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (category: Category) => {
    setSelectedCategory(category);
    setIsModalOpen(true);
  };

  const handleConfirmArchive = async () => {
    if (!archivingCategory) return;
    setArchiveError(null);
    try {
      await archiveMutation.mutateAsync(archivingCategory.id);
      setArchivingCategory(null);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setArchiveError(err.message);
      } else {
        setArchiveError("Failed to archive category");
      }
    }
  };

  const categories = data?.items ?? [];

  return (
    <div className="space-y-4">
      {/* Header controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center space-x-2">
          <label htmlFor="category-status-filter" className="text-sm font-medium text-slate-700">
            Status:
          </label>
          <select
            id="category-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "archived")}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            <option value="active">Active</option>
            <option value="archived">Archived</option>
            <option value="all">All</option>
          </select>
        </div>

        {canMutate && (
          <button
            type="button"
            onClick={handleOpenCreate}
            className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 focus:outline-none"
          >
            + New Category
          </button>
        )}
      </div>

      {/* Error state */}
      {isError && (
        <div role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          <p className="font-medium">Failed to load categories</p>
          <p className="mt-1 text-xs">{error instanceof Error ? error.message : "Network error"}</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-2 text-xs font-semibold text-red-800 underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div data-testid="category-loading" className="space-y-2 py-4">
          <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-10 w-full animate-pulse rounded bg-slate-100" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && categories.length === 0 && (
        <div data-testid="category-empty" className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
          <p className="text-sm font-medium text-slate-700">No categories found</p>
          <p className="mt-1 text-xs text-slate-500">
            {statusFilter === "all"
              ? "Create your first category to organize your products."
              : `There are no ${statusFilter} categories.`}
          </p>
          {canMutate && (
            <button
              type="button"
              onClick={handleOpenCreate}
              className="mt-3 inline-flex items-center rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Add Category
            </button>
          )}
        </div>
      )}

      {/* Table / List */}
      {!isLoading && !isError && categories.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Name
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Created
                  </th>
                  {canMutate && (
                    <th scope="col" className="px-4 py-3 text-right">
                      Actions
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {categories.map((cat) => (
                  <tr key={cat.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-medium text-slate-900">{cat.name}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          cat.status === "active"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {cat.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {new Date(cat.created_at).toLocaleDateString()}
                    </td>
                    {canMutate && (
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center space-x-2">
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(cat)}
                            className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                            aria-label={`Edit ${cat.name}`}
                          >
                            Edit
                          </button>
                          {cat.status === "active" ? (
                            <button
                              type="button"
                              onClick={() => {
                                setArchiveError(null);
                                setArchivingCategory(cat);
                              }}
                              className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 hover:text-red-700"
                              aria-label={`Archive ${cat.name}`}
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

      {/* Category Create/Edit Modal */}
      {isModalOpen && (
        <CategoryModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          organizationId={organizationId}
          category={selectedCategory}
          token={token}
        />
      )}

      {/* Archive Confirmation Dialog */}
      {archivingCategory && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="archive-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
        >
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h3 id="archive-dialog-title" className="text-base font-semibold text-slate-900">
              Archive Category
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Are you sure you want to archive <strong>{archivingCategory.name}</strong>?
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Existing products referencing this category will remain intact, but new products cannot use it.
            </p>

            {archiveError && (
              <div role="alert" className="mt-3 rounded bg-red-50 p-2 text-xs text-red-700">
                {archiveError}
              </div>
            )}

            <div className="mt-4 flex justify-end space-x-2">
              <button
                type="button"
                onClick={() => setArchivingCategory(null)}
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
