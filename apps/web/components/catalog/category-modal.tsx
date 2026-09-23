"use client";

import { useEffect, useState } from "react";
import { categoryCreateSchema, Category } from "@/lib/schemas/catalog";
import { useCreateCategory, useUpdateCategory } from "@/hooks/use-catalog";

interface CategoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  organizationId: string;
  category?: Category | null;
  token?: string;
}

export function CategoryModal({
  isOpen,
  onClose,
  organizationId,
  category,
  token,
}: CategoryModalProps) {
  const [name, setName] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const isEditing = Boolean(category);

  const createMutation = useCreateCategory(organizationId, token);
  const updateMutation = useUpdateCategory(organizationId, token);
  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (category) {
      setName(category.name);
    } else {
      setName("");
    }
    setClientError(null);
    setApiError(null);
  }, [category, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setClientError(null);
    setApiError(null);

    const validation = categoryCreateSchema.safeParse({ name });
    if (!validation.success) {
      setClientError(validation.error.issues[0]?.message || "Validation failed");
      return;
    }

    try {
      if (isEditing && category) {
        await updateMutation.mutateAsync({
          categoryId: category.id,
          data: { name: validation.data.name },
        });
      } else {
        await createMutation.mutateAsync({
          name: validation.data.name,
        });
      }
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setApiError(err.message);
      } else {
        setApiError("Failed to save category");
      }
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="category-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
    >
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h2 id="category-modal-title" className="text-lg font-semibold text-slate-900">
            {isEditing ? "Edit Category" : "New Category"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 focus:outline-none"
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="category-name" className="block text-sm font-medium text-slate-700">
              Category Name <span className="text-red-500">*</span>
            </label>
            <input
              id="category-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Beverages, Snacks"
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              autoFocus
              disabled={isPending}
            />
            {clientError && <p className="mt-1 text-xs text-red-600">{clientError}</p>}
          </div>

          {apiError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-xs text-red-700">
              {apiError}
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 focus:outline-none disabled:opacity-50"
            >
              {isPending ? "Saving..." : isEditing ? "Save Changes" : "Create Category"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
