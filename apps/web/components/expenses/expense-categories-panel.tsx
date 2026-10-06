"use client";

import React, { useState } from "react";
import { useArchiveExpenseCategory, useCreateExpenseCategory, useExpenseCategories, useUpdateExpenseCategory } from "@/hooks/use-expenses";
import { ExpenseCategory, expenseCategoryCreateSchema } from "@/lib/schemas/expenses";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";

interface ExpenseCategoriesPanelProps {
  orgId: string;
  token?: string;
}

/** Design "25 · Expense categories". Archived categories stay on past expenses (there is no restore). */
export function ExpenseCategoriesPanel({ orgId, token }: ExpenseCategoriesPanelProps) {
  const { data, isLoading } = useExpenseCategories(orgId, undefined, token);
  const createMutation = useCreateExpenseCategory(orgId, token);
  const updateMutation = useUpdateExpenseCategory(orgId, token);
  const archiveMutation = useArchiveExpenseCategory(orgId, token);
  const { notify } = useToast();

  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [archiving, setArchiving] = useState<ExpenseCategory | null>(null);
  const [error, setError] = useState<string | null>(null);

  const items = [...(data?.items ?? [])].sort((a, b) => (a.status === b.status ? a.name.localeCompare(b.name) : a.status === "active" ? -1 : 1));

  async function create() {
    setError(null);
    const parsed = expenseCategoryCreateSchema.safeParse({ name: newName });
    if (!parsed.success) return setError(parsed.error.issues[0].message);
    try {
      await createMutation.mutateAsync(parsed.data);
      notify({ title: `Category “${parsed.data.name}” added` });
      setNewName("");
      setAdding(false);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t add the category.");
    }
  }

  async function rename(c: ExpenseCategory) {
    setError(null);
    const parsed = expenseCategoryCreateSchema.safeParse({ name: editName });
    if (!parsed.success) return setError(parsed.error.issues[0].message);
    try {
      await updateMutation.mutateAsync({ categoryId: c.id, payload: parsed.data });
      setEditingId(null);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t rename the category.");
    }
  }

  async function archive() {
    if (!archiving) return;
    try {
      await archiveMutation.mutateAsync(archiving.id);
      notify({ title: `Category “${archiving.name}” archived` });
      setArchiving(null);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t archive the category.");
      setArchiving(null);
    }
  }

  return (
    <section className="card" aria-labelledby="ec-h">
      <div className="card-h">
        <h2 className="t-h4" id="ec-h">
          Expense categories
        </h2>
        {!adding && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAdding(true)}>
            <Icon name="plus" size="sm" />
            New
          </button>
        )}
      </div>
      {adding && (
        <form
          style={{ display: "flex", gap: 6, padding: "4px 16px 8px" }}
          onSubmit={(e) => {
            e.preventDefault();
            void create();
          }}
        >
          <input className="input" aria-label="New category name" value={newName} maxLength={100} autoFocus onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Rent" style={{ flex: 1, minWidth: 0 }} />
          <button type="submit" className="btn btn-primary btn-sm" disabled={createMutation.isPending}>
            Add
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setAdding(false);
              setNewName("");
              setError(null);
            }}
          >
            Cancel
          </button>
        </form>
      )}
      {error && (
        <div className="alert a-danger" role="alert" style={{ margin: "0 16px 8px" }}>
          {error}
        </div>
      )}
      {isLoading && (
        <div style={{ padding: "8px 16px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
          <Skeleton height={14} />
          <Skeleton height={14} />
        </div>
      )}
      {data && items.length === 0 && !adding && <p className="t-body-sm muted" style={{ padding: "4px 16px 12px" }}>No categories yet. Add a few — rent, utilities, transport — to see where money goes.</p>}
      <ul style={{ padding: "4px 8px 8px" }} aria-label="Expense categories">
        {items.map((c) =>
          editingId === c.id ? (
            <li key={c.id} style={{ padding: "4px 8px" }}>
              <form
                style={{ display: "flex", gap: 6 }}
                onSubmit={(e) => {
                  e.preventDefault();
                  void rename(c);
                }}
              >
                <input className="input" aria-label={`Rename ${c.name}`} value={editName} maxLength={100} autoFocus onChange={(e) => setEditName(e.target.value)} style={{ flex: 1, minWidth: 0, height: 32 }} />
                <button type="submit" className="btn btn-primary btn-sm" disabled={updateMutation.isPending}>
                  Save
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditingId(null)}>
                  Cancel
                </button>
              </form>
            </li>
          ) : (
            <li key={c.id} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 6 }}>
              <span style={{ flex: 1, minWidth: 0 }} className={`t-body-sm${c.status === "active" ? "" : " muted"}`}>
                {c.name}
              </span>
              {c.status === "active" ? (
                <>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    style={{ height: 26 }}
                    aria-label={`Rename ${c.name}`}
                    onClick={() => {
                      setEditingId(c.id);
                      setEditName(c.name);
                      setError(null);
                    }}
                  >
                    Rename
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" style={{ height: 26 }} aria-label={`Archive ${c.name}`} onClick={() => setArchiving(c)}>
                    Archive
                  </button>
                </>
              ) : (
                <span className="badge b-neutral">Archived</span>
              )}
            </li>
          )
        )}
      </ul>
      <div className="card-f t-caption">Archived categories stay on past expenses.</div>

      <Modal
        open={!!archiving}
        tone="warning"
        title={`Archive “${archiving?.name ?? ""}”?`}
        description="It won’t be offered for new expenses. Past expenses keep it. Archived categories can’t be restored yet."
        onClose={() => setArchiving(null)}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setArchiving(null)} disabled={archiveMutation.isPending}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void archive()} disabled={archiveMutation.isPending} aria-busy={archiveMutation.isPending}>
              {archiveMutation.isPending && <span className="spinner" />}
              Archive category
            </button>
          </>
        }
      />
    </section>
  );
}
