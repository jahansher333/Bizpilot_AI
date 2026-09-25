"use client";

import React, { useState } from "react";
import {
  useArchiveExpenseCategory,
  useCreateExpenseCategory,
  useExpenseCategories,
} from "@/hooks/use-expenses";
import { expenseCategoryCreateSchema } from "@/lib/schemas/expenses";

interface CategoryManageModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  token?: string;
}

export function CategoryManageModal({
  isOpen,
  onClose,
  orgId,
  token,
}: CategoryManageModalProps) {
  const [newCategoryName, setNewCategoryName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data, isLoading } = useExpenseCategories(orgId, undefined, token);
  const createMutation = useCreateExpenseCategory(orgId, token);
  const archiveMutation = useArchiveExpenseCategory(orgId, token);

  if (!isOpen) return null;

  const categories = data?.items || [];

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const parseResult = expenseCategoryCreateSchema.safeParse({ name: newCategoryName });
    if (!parseResult.success) {
      setFormError(parseResult.error.issues[0]?.message || "Invalid category name");
      return;
    }

    try {
      await createMutation.mutateAsync(parseResult.data);
      setNewCategoryName("");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to create expense category");
      }
    }
  };

  const handleArchive = async (categoryId: string) => {
    try {
      await archiveMutation.mutateAsync(categoryId);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to archive category");
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="category-modal-title"
    >
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <h2 id="category-modal-title" className="text-lg font-semibold text-gray-900">
            Expense Categories
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500 focus:outline-none"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {formError && (
          <div
            role="alert"
            className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200"
          >
            {formError}
          </div>
        )}

        {/* Add Category Form */}
        <form onSubmit={handleCreate} className="mt-4 flex gap-2">
          <input
            type="text"
            value={newCategoryName}
            onChange={(e) => setNewCategoryName(e.target.value)}
            placeholder="e.g. Utilities, Logistics, Rent"
            maxLength={100}
            className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={createMutation.isPending || !newCategoryName.trim()}
            className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none disabled:bg-gray-400"
          >
            {createMutation.isPending ? "Adding..." : "Add"}
          </button>
        </form>

        {/* Category List */}
        <div className="mt-6 border-t pt-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Existing Categories
          </h3>
          {isLoading ? (
            <p className="text-xs text-gray-500">Loading categories...</p>
          ) : categories.length === 0 ? (
            <p className="text-xs text-gray-500">No categories found. Create one above.</p>
          ) : (
            <div className="divide-y divide-gray-100 max-h-60 overflow-y-auto">
              {categories.map((cat) => (
                <div key={cat.id} className="flex items-center justify-between py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{cat.name}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full capitalize font-medium ${
                        cat.status === "active"
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {cat.status}
                    </span>
                  </div>
                  {cat.status === "active" && (
                    <button
                      onClick={() => handleArchive(cat.id)}
                      disabled={archiveMutation.isPending}
                      className="text-xs text-red-600 hover:text-red-800 font-medium"
                    >
                      Archive
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end border-t pt-4">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
