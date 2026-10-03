"use client";

import React, { useEffect, useState } from "react";
import { Category, categoryCreateSchema } from "@/lib/schemas/catalog";
import { useCreateCategory, useUpdateCategory } from "@/hooks/use-catalog";
import { Modal } from "@/components/ui/modal";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

export interface CategoryModalProps {
  organizationId: string;
  isOpen: boolean;
  onClose: () => void;
  category?: Category | null;
  token?: string;
}

/** Design "New category" modal; also used to rename an existing category. */
export function CategoryModal({ organizationId, isOpen, onClose, category, token }: CategoryModalProps) {
  const isEdit = !!category;
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const createMutation = useCreateCategory(organizationId, token);
  const updateMutation = useUpdateCategory(organizationId, token);
  const { notify } = useToast();
  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (isOpen) {
      setName(category?.name ?? "");
      setError(null);
    }
  }, [isOpen, category]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const parsed = categoryCreateSchema.safeParse({ name });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message || "Invalid name");
      return;
    }
    try {
      if (isEdit && category) {
        await updateMutation.mutateAsync({ categoryId: category.id, data: parsed.data });
        notify({ title: "Category renamed" });
      } else {
        await createMutation.mutateAsync(parsed.data);
        notify({ title: "Category created" });
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t save the category.");
    }
  }

  return (
    <Modal
      open={isOpen}
      title={isEdit ? "Rename category" : "New category"}
      description="Use names your staff will recognise at the counter."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </button>
          <button type="submit" form="category-form" className="btn btn-primary" disabled={isPending} aria-busy={isPending}>
            {isPending && <span className="spinner" />}
            {isEdit ? "Save name" : "Create category"}
          </button>
        </>
      }
    >
      <form id="category-form" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label className="label" htmlFor="category-name">
            Category name
          </label>
          <input
            className={`input${error ? " is-error" : ""}`}
            id="category-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={!!error}
            aria-describedby={error ? "category-name-err" : undefined}
            placeholder="e.g. Spices"
          />
          {error && (
            <span className="err" id="category-name-err" role="alert">
              <Icon name="alert" size="sm" />
              {error}
            </span>
          )}
        </div>
      </form>
    </Modal>
  );
}
