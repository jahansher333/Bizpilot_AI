"use client";

import React, { useEffect, useRef, useState } from "react";
import { useCorrectExpense, useExpenseCategories } from "@/hooks/use-expenses";
import { EXPENSE_METHOD_LABEL, Expense, ExpensePaymentMethod, expenseCorrectSchema, expensePaymentMethodEnum } from "@/lib/schemas/expenses";
import { newIdempotencyKey } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { Money, formatMinor } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { ReviewRows, parseAmountMinor } from "@/components/finance/record-meta";

interface ExpenseCorrectModalProps {
  isOpen: boolean;
  onClose: () => void;
  expense: Expense | null;
  orgId: string;
  token?: string;
  onCorrected?: (replacement: Expense) => void;
}

/** The original stays in history (Corrected) and a linked replacement is recorded. Owner/Manager. */
export function ExpenseCorrectModal({ isOpen, onClose, expense, orgId, token, onCorrected }: ExpenseCorrectModalProps) {
  const [amount, setAmount] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [description, setDescription] = useState("");
  const [payee, setPayee] = useState("");
  const [method, setMethod] = useState<ExpensePaymentMethod>("cash");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"edit" | "review">("edit");
  const idemKey = useRef(newIdempotencyKey());

  const { data: categories } = useExpenseCategories(orgId, "active", token);
  const correctMutation = useCorrectExpense(orgId, token);
  const { notify } = useToast();

  useEffect(() => {
    if (!isOpen || !expense) return;
    setAmount(formatMinor(expense.amount_minor));
    setCategoryId(expense.expense_category_id ?? "");
    setDescription(expense.description ?? "");
    setPayee(expense.payee ?? "");
    setMethod(expense.payment_method);
    setReason("");
    setError(null);
    setStep("edit");
    idemKey.current = newIdempotencyKey();
  }, [isOpen, expense]);

  if (!expense) return null;
  const archivedCategory = expense.expense_category_id && !categories?.items.some((c) => c.id === expense.expense_category_id);

  const categoryLabel = (id: string) => (id ? (categories?.items.find((c) => c.id === id)?.name ?? "Archived category") : "Uncategorised");

  function payload() {
    if (!expense) return null;
    const amountMinor = parseAmountMinor(amount);
    if (amountMinor === null) {
      setError("Enter an amount greater than 0.");
      return null;
    }
    const parsed = expenseCorrectSchema.safeParse({
      reason,
      amount_minor: amountMinor,
      expense_category_id: categoryId || undefined,
      description: description.trim() || undefined,
      payee: payee.trim() || undefined,
      payment_method: method,
      currency_code: expense.currency_code,
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0].message);
      return null;
    }
    return parsed.data;
  }

  function review() {
    setError(null);
    if (payload()) setStep("review");
  }

  async function submit() {
    if (!expense) return;
    const data = payload();
    if (!data) return setStep("edit");
    try {
      const replacement = await correctMutation.mutateAsync({ expenseId: expense.id, payload: data, idempotencyKey: `web-correct-${idemKey.current}` });
      notify({ title: "Expense corrected", description: "The original is kept in history, marked Corrected." });
      onCorrected?.(replacement);
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t save the correction. Nothing was changed.");
      setStep("edit");
    }
  }

  const changes: [string, React.ReactNode, React.ReactNode][] = [];
  const newAmount = parseAmountMinor(amount);
  if (newAmount !== null && newAmount !== expense.amount_minor) changes.push(["Amount", formatMinor(expense.amount_minor), formatMinor(newAmount)]);
  if (categoryId !== (expense.expense_category_id ?? "")) changes.push(["Category", categoryLabel(expense.expense_category_id ?? ""), categoryLabel(categoryId)]);
  if (description.trim() !== (expense.description ?? "")) changes.push(["Description", expense.description || "—", description.trim() || "—"]);
  if (payee.trim() !== (expense.payee ?? "")) changes.push(["Paid to", expense.payee || "—", payee.trim() || "—"]);
  if (method !== expense.payment_method) changes.push(["Paid by", EXPENSE_METHOD_LABEL[expense.payment_method] ?? expense.payment_method, EXPENSE_METHOD_LABEL[method]]);

  if (step === "review") {
    return (
      <Modal
        open={isOpen}
        tone="warning"
        title="Correct this expense?"
        description="The original stays visible, marked “Corrected”. A new expense record replaces it in your totals."
        onClose={() => setStep("edit")}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setStep("edit")} disabled={correctMutation.isPending}>
              Back
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void submit()} disabled={correctMutation.isPending} aria-busy={correctMutation.isPending}>
              {correctMutation.isPending && <span className="spinner" />}
              Submit correction
            </button>
          </>
        }
      >
        <ReviewRows changes={changes} reason={reason} />
      </Modal>
    );
  }

  return (
    <Modal
      open={isOpen}
      wide
      title="Correct expense"
      description="The original stays in history, marked Corrected, and a replacement expense is recorded."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={review}>
            Review correction
          </button>
        </>
      }
    >
      <div className="well t-body-sm" style={{ padding: "10px 14px", display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span className="secondary">Original · {expense.description || expense.payee || "Expense"}</span>
        <Money amountMinor={expense.amount_minor} currency={expense.currency_code} className="struck" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))", gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="ec-amt">
            Correct amount
          </label>
          <div className="ig">
            <span className="pre">PKR</span>
            <input id="ec-amt" className="num" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.,]/g, ""))} />
          </div>
        </div>
        <div className="field">
          <label className="label" htmlFor="ec-cat">
            Category
          </label>
          <select id="ec-cat" className="input" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Uncategorised</option>
            {archivedCategory && (
              <option value={expense.expense_category_id!} disabled>
                Archived category
              </option>
            )}
            {categories?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="ec-desc">
            Description
          </label>
          <input id="ec-desc" className="input" value={description} maxLength={1000} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="ec-payee">
            Paid to
          </label>
          <input id="ec-payee" className="input" value={payee} maxLength={255} onChange={(e) => setPayee(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="ec-method">
            Paid by
          </label>
          <select id="ec-method" className="input" value={method} onChange={(e) => setMethod(e.target.value as ExpensePaymentMethod)}>
            {expensePaymentMethodEnum.options.map((m) => (
              <option key={m} value={m}>
                {EXPENSE_METHOD_LABEL[m]}
              </option>
            ))}
          </select>
        </div>
      </div>
      {archivedCategory && categoryId === expense.expense_category_id && <p className="t-caption">Its category is archived — pick an active one for the replacement.</p>}
      <div className="field">
        <label className="label" htmlFor="ec-reason">
          Reason <span className="opt">· required, shown in history</span>
        </label>
        <input id="ec-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Bill was 8,590, not 8,950" />
      </div>
      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <span>{error}</span>
        </div>
      )}
    </Modal>
  );
}
