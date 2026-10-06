"use client";

import React, { useEffect, useRef, useState } from "react";
import { useVoidExpense } from "@/hooks/use-expenses";
import { Expense, expenseVoidSchema } from "@/lib/schemas/expenses";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

interface ExpenseVoidModalProps {
  isOpen: boolean;
  onClose: () => void;
  expense: Expense | null;
  orgId: string;
  token?: string;
}

/** Destructive: focus starts on the safe button. Owner-only (backend expenses:void). */
export function ExpenseVoidModal({ isOpen, onClose, expense, orgId, token }: ExpenseVoidModalProps) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const voidMutation = useVoidExpense(orgId, token);
  const { notify } = useToast();

  useEffect(() => {
    if (isOpen) {
      setReason("");
      setError(null);
    }
  }, [isOpen, expense?.id]);

  if (!expense) return null;

  async function confirm() {
    if (!expense) return;
    setError(null);
    const parsed = expenseVoidSchema.safeParse({ reason });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return;
    }
    try {
      await voidMutation.mutateAsync({ expenseId: expense.id, payload: parsed.data, idempotencyKey: `web-void-${expense.id}-${Date.now()}` });
      notify({ title: "Expense voided" });
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t void the expense.");
    }
  }

  return (
    <Modal
      open={isOpen}
      tone="danger"
      title="Void this expense?"
      description="It stays in your records, marked Voided, and stops counting toward expenses and net cash. This can’t be undone."
      onClose={onClose}
      initialFocusRef={keepRef}
      footer={
        <>
          <button ref={keepRef} type="button" className="btn btn-secondary" onClick={onClose} disabled={voidMutation.isPending}>
            Keep expense
          </button>
          <button type="button" className="btn btn-danger" onClick={() => void confirm()} disabled={voidMutation.isPending} aria-busy={voidMutation.isPending}>
            {voidMutation.isPending && <span className="spinner" />}
            Void expense
          </button>
        </>
      }
    >
      <div className="field">
        <label className="label" htmlFor="ev-reason">
          Reason <span className="opt">· required, shown in history</span>
        </label>
        <textarea
          id="ev-reason"
          className="input"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Entered twice"
          aria-invalid={!!error}
          aria-describedby={error ? "ev-error" : undefined}
          style={{ height: "auto", paddingTop: 8, paddingBottom: 8 }}
        />
      </div>
      {error && (
        <div className="alert a-danger" role="alert" id="ev-error">
          {error}
        </div>
      )}
    </Modal>
  );
}
