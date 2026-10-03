"use client";

import React, { useEffect, useState } from "react";
import { useRecordOpeningStock } from "@/hooks/use-inventory";
import { Modal } from "@/components/ui/modal";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

interface OpeningStockModalProps {
  orgId: string;
  productId: string;
  productName: string;
  unit: string;
  isOpen: boolean;
  onClose: () => void;
  token?: string;
}

/** Records the first stock entry for a product that has none yet. */
export function OpeningStockModal({ orgId, productId, productName, unit, isOpen, onClose, token }: OpeningStockModalProps) {
  const mutation = useRecordOpeningStock(orgId, token);
  const { notify } = useToast();
  const [quantity, setQuantity] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setQuantity("");
      setError(null);
    }
  }, [isOpen]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const qty = Number(quantity);
    if (!Number.isInteger(qty) || qty <= 0) {
      setError("Opening stock quantity must be greater than zero");
      return;
    }
    setError(null);
    try {
      await mutation.mutateAsync({ product_id: productId, quantity: qty, reason: "Opening stock" });
      notify({ title: "Opening stock recorded", description: `${productName}: ${qty} ${unit}` });
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t record opening stock.");
    }
  }

  return (
    <Modal
      open={isOpen}
      title="Set opening stock"
      description={`${productName} · the quantity you have on hand right now`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </button>
          <button type="submit" form="opening-form" className="btn btn-primary" disabled={mutation.isPending} aria-busy={mutation.isPending}>
            {mutation.isPending && <span className="spinner" />}
            Record opening stock
          </button>
        </>
      }
    >
      <form id="opening-form" onSubmit={submit} noValidate>
        <div className="field">
          <label className="label" htmlFor="opening-qty">
            Quantity on hand
          </label>
          <div className={`ig${error ? " is-error" : ""}`} style={{ width: 220 }}>
            <input id="opening-qty" className="num" inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value.replace(/[^0-9]/g, ""))} aria-invalid={!!error} aria-describedby={error ? "opening-err" : "opening-hint"} />
            <span className="post">{unit}</span>
          </div>
          {error ? (
            <span className="err" id="opening-err" role="alert">
              <Icon name="alert" size="sm" />
              {error}
            </span>
          ) : (
            <span className="hint" id="opening-hint">
              Recorded once as the first entry in the stock timeline.
            </span>
          )}
        </div>
      </form>
    </Modal>
  );
}
