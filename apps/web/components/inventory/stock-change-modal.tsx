"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRecordAdjustment, useRecordCorrection } from "@/hooks/use-inventory";
import { newIdempotencyKey } from "@/lib/stock";
import { Modal } from "@/components/ui/modal";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

export type StockChangeMode = "adjust" | "correct";

interface StockChangeModalProps {
  orgId: string;
  productId: string;
  productName: string;
  productCode: string;
  unit: string;
  currentQuantity: number;
  mode: StockChangeMode | null;
  onClose: () => void;
  token?: string;
}

const REASONS = ["Restock delivery", "Damaged", "Expired", "Lost or stolen", "Other"] as const;

/**
 * Design "13 · Adjust / Correct stock". Adjust adds or removes units with a reason;
 * Correct records the difference between the counted and the current quantity.
 */
export function StockChangeModal({ orgId, productId, productName, productCode, unit, currentQuantity, mode, onClose, token }: StockChangeModalProps) {
  const adjustMutation = useRecordAdjustment(orgId, token);
  const correctMutation = useRecordCorrection(orgId, token);
  const { notify } = useToast();
  const idempotencyKey = useRef(newIdempotencyKey());

  const [direction, setDirection] = useState<"inc" | "dec">("inc");
  const [quantity, setQuantity] = useState("1");
  const [reason, setReason] = useState<(typeof REASONS)[number]>("Restock delivery");
  const [otherReason, setOtherReason] = useState("");
  const [note, setNote] = useState("Shelf count");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mode) return;
    idempotencyKey.current = newIdempotencyKey();
    setDirection("inc");
    setQuantity(mode === "correct" ? String(currentQuantity) : "1");
    setReason("Restock delivery");
    setOtherReason("");
    setNote("Shelf count");
    setError(null);
  }, [mode, currentQuantity]);

  const qty = Math.max(0, parseInt(quantity, 10) || 0);
  const isCorrect = mode === "correct";
  const delta = isCorrect ? qty - currentQuantity : direction === "inc" ? qty : -qty;
  const result = currentQuantity + delta;
  const belowZero = result < 0;
  const noChange = delta === 0;
  const reasonText = isCorrect ? note.trim() : reason === "Other" ? otherReason.trim() : reason;
  const reasonMissing = reasonText.length < 3;
  const isPending = adjustMutation.isPending || correctMutation.isPending;
  const blocked = belowZero || noChange || reasonMissing || isPending;

  async function submit() {
    if (blocked || !mode) return;
    setError(null);
    const input = { product_id: productId, quantity_delta: delta, reason: reasonText };
    try {
      if (isCorrect) {
        await correctMutation.mutateAsync({ input, idempotencyKey: idempotencyKey.current });
      } else {
        await adjustMutation.mutateAsync({ input, idempotencyKey: idempotencyKey.current });
      }
      notify({ title: isCorrect ? "Stock corrected" : "Stock adjusted", description: `${productName}: ${result} ${unit}` });
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t save this change. Please try again.");
    }
  }

  const sign = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "0");

  return (
    <Modal
      open={!!mode}
      title={isCorrect ? "Correct stock" : "Adjust stock"}
      description={`${productName} · ${productCode}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={blocked} aria-busy={isPending}>
            {isPending && <span className="spinner" />}
            {isCorrect ? "Confirm correction" : "Confirm adjustment"}
          </button>
        </>
      }
    >
      {!isCorrect && (
        <div className="field">
          <span className="label" id="adj-dir">
            Adjustment
          </span>
          <div className="seg" role="group" aria-labelledby="adj-dir" style={{ alignSelf: "flex-start" }}>
            <button type="button" aria-pressed={direction === "inc"} onClick={() => setDirection("inc")}>
              + Increase
            </button>
            <button type="button" aria-pressed={direction === "dec"} onClick={() => setDirection("dec")}>
              − Decrease
            </button>
          </div>
        </div>
      )}
      {isCorrect && (
        <div className="alert a-info">
          <Icon name="info" />
          <span>Enter the quantity you physically counted. We’ll record the difference as a correction.</span>
        </div>
      )}

      <div className="field">
        <label className="label" htmlFor="stock-qty">
          {isCorrect ? "Counted quantity" : "Quantity"}
        </label>
        <div className="ig" style={{ width: 200 }}>
          <button
            type="button"
            className="btn btn-ghost btn-sm icon-btn"
            style={{ height: "100%", borderRadius: 0, width: 40 }}
            aria-label="Decrease quantity"
            onClick={() => setQuantity(String(Math.max(0, qty - 1)))}
          >
            <svg className="i" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 12h14" />
            </svg>
          </button>
          <input id="stock-qty" className="num" inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value.replace(/[^0-9]/g, ""))} style={{ textAlign: "center" }} />
          <button type="button" className="btn btn-ghost btn-sm icon-btn" style={{ height: "100%", borderRadius: 0, width: 40 }} aria-label="Increase quantity" onClick={() => setQuantity(String(qty + 1))}>
            <Icon name="plus" />
          </button>
        </div>
      </div>

      {!isCorrect ? (
        <div className="field">
          <span className="label" id="adj-reason">
            Reason
          </span>
          <div role="group" aria-labelledby="adj-reason" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {REASONS.map((r) => (
              <button key={r} type="button" className="chip" aria-pressed={reason === r} onClick={() => setReason(r)}>
                {r}
              </button>
            ))}
          </div>
          {reason === "Other" && (
            <input className="input" aria-label="Describe the reason" placeholder="Describe the reason (at least 3 characters)" value={otherReason} onChange={(e) => setOtherReason(e.target.value)} style={{ marginTop: 8 }} />
          )}
        </div>
      ) : (
        <div className="field">
          <label className="label" htmlFor="cor-note">
            Note
          </label>
          <input className="input" id="cor-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      )}

      <div className="well" style={{ padding: "4px 16px" }} aria-live="polite">
        <div className="t-body" style={{ display: "flex", justifyContent: "space-between", padding: "9px 0", borderBottom: "1px solid var(--border)" }}>
          <span className="secondary">Current</span>
          <span className="num">{currentQuantity}</span>
        </div>
        <div className="t-body" style={{ display: "flex", justifyContent: "space-between", padding: "9px 0", borderBottom: "1px solid var(--border)" }}>
          <span className="secondary">{isCorrect ? "Difference" : "Adjustment"}</span>
          <span className="num strong" style={{ color: delta > 0 ? "var(--success)" : delta < 0 ? "var(--danger)" : "var(--text-muted)" }}>
            {sign(delta)}
          </span>
        </div>
        <div className="t-h3" style={{ display: "flex", justifyContent: "space-between", padding: "10px 0" }}>
          <span>Result</span>
          <span className="num" style={{ color: belowZero ? "var(--danger)" : "var(--text-primary)" }}>
            {belowZero ? `−${Math.abs(result)}` : result} {unit}
          </span>
        </div>
      </div>

      {belowZero && (
        <div className="alert a-danger shake" role="alert">
          <Icon name="alert" />
          <div>
            <div className="a-t">Stock can’t go below zero</div>
            You have {currentQuantity} {unit}. Decrease by {currentQuantity} or less, or use Correct stock after a count.
          </div>
        </div>
      )}
      {noChange && !belowZero && (
        <div className="alert a-neutral">
          <Icon name="info" />
          <span>No change to record yet.</span>
        </div>
      )}
      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <div>{error}</div>
        </div>
      )}
    </Modal>
  );
}
