"use client";

import React from "react";
import { useExpense } from "@/hooks/use-expenses";
import { EXPENSE_METHOD_LABEL, Expense } from "@/lib/schemas/expenses";
import { Icon } from "@/components/ui/icon";
import { Money } from "@/components/ui/money";
import { Modal } from "@/components/ui/modal";
import { RecordStatusBadge } from "@/components/finance/record-meta";
import { orderWhen } from "@/components/orders/order-meta";

interface ExpenseDetailModalProps {
  expense: Expense | null;
  onClose: () => void;
  orgId: string;
  token?: string;
  categoryName: (id?: string | null) => string;
  canCorrect: boolean;
  canVoid: boolean;
  onCorrect: (e: Expense) => void;
  onVoid: (e: Expense) => void;
  onOpenExpense: (e: Expense) => void;
}

export function ExpenseDetailModal({ expense, onClose, orgId, token, categoryName, canCorrect, canVoid, onCorrect, onVoid, onOpenExpense }: ExpenseDetailModalProps) {
  const e = expense;
  const replacement = useExpense(orgId, e?.replaced_by_expense_id ?? "", token);
  const original = useExpense(orgId, e?.corrects_expense_id ?? "", token);
  if (!e) return null;
  const active = e.status === "active";

  const rows: [string, React.ReactNode][] = [
    ["Category", categoryName(e.expense_category_id)],
    ...(e.payee ? ([["Paid to", e.payee]] as [string, React.ReactNode][]) : []),
    ["Paid by", EXPENSE_METHOD_LABEL[e.payment_method] ?? e.payment_method],
    ["Date", orderWhen(e.occurred_at)],
  ];

  return (
    <Modal
      open={!!e}
      title={e.description || e.payee || "Expense"}
      onClose={onClose}
      footer={
        active && (canCorrect || canVoid) ? (
          <>
            {canVoid && (
              <button type="button" className="btn btn-danger-outline" onClick={() => onVoid(e)}>
                <Icon name="ban" />
                Void expense…
              </button>
            )}
            {canCorrect && (
              <button type="button" className="btn btn-secondary" onClick={() => onCorrect(e)}>
                <Icon name="edit" />
                Correct expense
              </button>
            )}
          </>
        ) : (
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        )
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <RecordStatusBadge status={e.status} />
        <Money amountMinor={e.amount_minor} currency={e.currency_code} className={active ? "" : "struck"} style={{ font: "600 32px/40px var(--font)", letterSpacing: "-0.02em" }} />
      </div>
      {e.status === "corrected" && (
        <div className="alert a-warning">
          <Icon name="edit" />
          <span style={{ flex: 1 }}>Corrected. It no longer counts; the replacement holds the right details.</span>
          {replacement.data && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenExpense(replacement.data!)}>
              Open replacement
            </button>
          )}
        </div>
      )}
      {e.status === "voided" && (
        <div className="alert a-danger">
          <Icon name="ban" />
          <span>Voided{e.voided_at ? ` ${orderWhen(e.voided_at).replace(/^(Today|Yesterday)/, (m) => m.toLowerCase())}` : ""}. Kept for your records; it doesn’t count toward expenses or net cash.</span>
        </div>
      )}
      {e.corrects_expense_id && (
        <div className="alert a-neutral">
          <Icon name="info" />
          <span style={{ flex: 1 }}>Replaces an earlier expense, which is kept and marked Corrected.</span>
          {original.data && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenExpense(original.data!)}>
              Open original
            </button>
          )}
        </div>
      )}
      <dl className="well" style={{ margin: 0, padding: "4px 16px" }}>
        {rows.map(([label, value], i) => (
          <div key={label} className="t-body-sm" style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "10px 0", borderBottom: i < rows.length - 1 ? "1px solid var(--border)" : undefined }}>
            <dt className="secondary">{label}</dt>
            <dd style={{ margin: 0, textAlign: "right" }}>{value}</dd>
          </div>
        ))}
      </dl>
      {active && !canCorrect && <p className="t-caption">Only Owners and Managers can correct expenses, and only Owners can void them.</p>}
    </Modal>
  );
}
