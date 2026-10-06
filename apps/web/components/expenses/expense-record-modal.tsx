"use client";

import React, { useEffect, useRef, useState } from "react";
import { useCreateExpense, useExpenseCategories } from "@/hooks/use-expenses";
import { EXPENSE_METHOD_LABEL, ExpensePaymentMethod, expenseCreateSchema, expensePaymentMethodEnum } from "@/lib/schemas/expenses";
import { newIdempotencyKey } from "@/lib/stock";
import { Icon } from "@/components/ui/icon";
import { Money, formatMinor } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { parseAmountMinor, pickedDateToIso, todayInput } from "@/components/finance/record-meta";

interface ExpenseRecordModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  token?: string;
}

/** Design "23 · Record expense": fill in, then confirm what will be recorded. Owner/Manager. */
export function ExpenseRecordModal({ isOpen, onClose, orgId, token }: ExpenseRecordModalProps) {
  const [step, setStep] = useState<"edit" | "confirm">("edit");
  const [categoryId, setCategoryId] = useState("");
  const [description, setDescription] = useState("");
  const [payee, setPayee] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayInput());
  const [method, setMethod] = useState<ExpensePaymentMethod>("cash");
  const [error, setError] = useState<string | null>(null);
  const idemKey = useRef(newIdempotencyKey());

  const { data: categories } = useExpenseCategories(orgId, "active", token);
  const createMutation = useCreateExpense(orgId, token);
  const { notify } = useToast();

  useEffect(() => {
    if (!isOpen) return;
    setStep("edit");
    setCategoryId("");
    setDescription("");
    setPayee("");
    setAmount("");
    setDate(todayInput());
    setMethod("cash");
    setError(null);
    idemKey.current = newIdempotencyKey();
  }, [isOpen]);

  const amountMinor = parseAmountMinor(amount);
  const categoryName = categories?.items.find((c) => c.id === categoryId)?.name ?? "Uncategorised";
  const label = description.trim() || payee.trim();
  const invalid = amountMinor === null || !label;
  const when = date === todayInput() ? "Today" : new Date(`${date}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

  function edit<T>(setter: (v: T) => void) {
    return (v: T) => {
      idemKey.current = newIdempotencyKey();
      setError(null);
      setter(v);
    };
  }

  async function save() {
    if (amountMinor === null) return;
    const parsed = expenseCreateSchema.safeParse({
      amount_minor: amountMinor,
      expense_category_id: categoryId || undefined,
      description: description.trim() || undefined,
      payee: payee.trim() || undefined,
      payment_method: method,
      occurred_at: pickedDateToIso(date),
      currency_code: "PKR",
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check the expense details.");
      setStep("edit");
      return;
    }
    try {
      await createMutation.mutateAsync({ payload: parsed.data, idempotencyKey: idemKey.current });
      notify({ title: "Expense recorded", description: `PKR ${formatMinor(amountMinor)} · ${label}` });
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t record the expense. Nothing was saved.");
      setStep("edit");
    }
  }

  return (
    <Modal
      open={isOpen}
      title="Record expense"
      onClose={onClose}
      footer={
        step === "confirm" ? (
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setStep("edit")} disabled={createMutation.isPending}>
              Edit
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={createMutation.isPending} aria-busy={createMutation.isPending}>
              {createMutation.isPending && <span className="spinner" />}
              Confirm &amp; record
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" onClick={() => setStep("confirm")} disabled={invalid}>
              Review expense
            </button>
          </>
        )
      }
    >
      {step === "confirm" && amountMinor !== null ? (
        <>
          <div className="well" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 6, textAlign: "center" }}>
            <span className="t-body-sm secondary">You’re recording</span>
            <Money amountMinor={amountMinor} style={{ font: "600 30px/36px var(--font)" }} />
            <span className="t-body-sm">
              {label} · {categoryName} · {EXPENSE_METHOD_LABEL[method]} · {when}
            </span>
          </div>
          <p className="t-body-sm secondary">It will count toward this month’s expenses and net cash flow. You can correct or void it later; the original stays in history.</p>
        </>
      ) : (
        <>
          <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="label">
              Expense category <span className="opt">· optional</span>
            </legend>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button type="button" className="chip" aria-pressed={categoryId === ""} onClick={() => edit(setCategoryId)("")}>
                None
              </button>
              {categories?.items.map((c) => (
                <button key={c.id} type="button" className="chip" aria-pressed={categoryId === c.id} onClick={() => edit(setCategoryId)(c.id)}>
                  {c.name}
                </button>
              ))}
            </div>
          </fieldset>
          <div className="field">
            <label className="label" htmlFor="re-desc">
              Description
            </label>
            <input id="re-desc" className="input" value={description} maxLength={1000} onChange={(e) => edit(setDescription)(e.target.value)} placeholder="e.g. Electricity bill — September" />
          </div>
          <div className="field">
            <label className="label" htmlFor="re-payee">
              Paid to <span className="opt">· optional</span>
            </label>
            <input id="re-payee" className="input" value={payee} maxLength={255} onChange={(e) => edit(setPayee)(e.target.value)} placeholder="e.g. K-Electric" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(160px, 100%), 1fr))", gap: 12 }}>
            <div className="field">
              <label className="label" htmlFor="re-amt">
                Amount
              </label>
              <div className="ig">
                <span className="pre">PKR</span>
                <input id="re-amt" className="num" inputMode="decimal" value={amount} onChange={(e) => edit(setAmount)(e.target.value.replace(/[^\d.,]/g, ""))} aria-invalid={amount !== "" && amountMinor === null} />
              </div>
            </div>
            <div className="field">
              <label className="label" htmlFor="re-date">
                Date
              </label>
              <input id="re-date" className="input" type="date" value={date} max={todayInput()} onChange={(e) => edit(setDate)(e.target.value)} />
            </div>
            <div className="field">
              <label className="label" htmlFor="re-method">
                Paid by
              </label>
              <select id="re-method" className="input" value={method} onChange={(e) => edit(setMethod)(e.target.value as ExpensePaymentMethod)}>
                {expensePaymentMethodEnum.options.map((m) => (
                  <option key={m} value={m}>
                    {EXPENSE_METHOD_LABEL[m]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {amount !== "" && amountMinor === null && <span className="err">Enter an amount greater than 0</span>}
        </>
      )}
      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <span>{error}</span>
        </div>
      )}
    </Modal>
  );
}
