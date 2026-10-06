"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useProducts } from "@/hooks/use-catalog";
import { useInventoryBalances } from "@/hooks/use-inventory";
import { Product } from "@/lib/schemas/catalog";
import { Icon } from "@/components/ui/icon";
import { formatMinor } from "@/components/ui/money";

export interface SellableProduct extends Product {
  /** On-hand quantity; 0 when no stock has been recorded (the backend treats that as 0). */
  stock: number;
}

/** Active products with their on-hand stock, for the POS and order corrections. */
export function useSellableProducts(orgId: string, token?: string) {
  const products = useProducts(orgId, { status: "active", limit: 100 }, token);
  const balances = useInventoryBalances(orgId, 100, 0, token);
  const items = useMemo<SellableProduct[]>(() => {
    const onHand = new Map((balances.data?.items ?? []).map((b) => [b.product_id, b.on_hand_quantity]));
    return (products.data?.items ?? []).map((p) => ({ ...p, stock: Math.max(0, onHand.get(p.id) ?? 0) }));
  }, [products.data, balances.data]);
  return {
    items,
    isLoading: products.isLoading || balances.isLoading,
    error: products.error ?? balances.error,
    refetch: () => void Promise.all([products.refetch(), balances.refetch()]),
  };
}

export interface CartLine {
  productId: string;
  name: string;
  code: string;
  unit: string;
  qty: number;
  priceMinor: number;
  /** Most that can be sold; the backend rejects anything above on-hand stock. */
  max: number;
}

export function cartTotal(lines: CartLine[]): number {
  return lines.reduce((sum, l) => sum + l.qty * l.priceMinor, 0);
}

export function cartUnits(lines: CartLine[]): number {
  return lines.reduce((sum, l) => sum + l.qty, 0);
}

export function QtyStepper({ line, onChange, compact }: { line: CartLine; onChange: (qty: number) => void; compact?: boolean }) {
  const h = compact ? 30 : 32;
  return (
    <div className="ig" style={{ height: h, width: compact ? 104 : 116, flex: "none" }}>
      <button type="button" className="btn btn-ghost btn-sm icon-btn" style={{ height: "100%", borderRadius: 0, width: h + 2 }} aria-label={`Decrease ${line.name}`} onClick={() => onChange(line.qty - 1)}>
        <Icon name="minus" size="sm" />
      </button>
      <span className="num" style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 600 }} aria-label={`Quantity of ${line.name}`}>
        {line.qty}
      </span>
      <button
        type="button"
        className="btn btn-ghost btn-sm icon-btn"
        style={{ height: "100%", borderRadius: 0, width: h + 2 }}
        aria-label={`Increase ${line.name}`}
        onClick={() => onChange(line.qty + 1)}
        disabled={line.qty >= line.max}
      >
        <Icon name="plus" size="sm" />
      </button>
    </div>
  );
}

/** Unit price in rupees; keeps the typed text while editing and reports minor units. */
export function PriceInput({ line, onChange }: { line: CartLine; onChange: (priceMinor: number) => void }) {
  const [text, setText] = useState(formatMinor(line.priceMinor).replace(/,/g, ""));
  useEffect(() => {
    setText((current) => (Math.round(parseFloat(current) * 100) === line.priceMinor ? current : formatMinor(line.priceMinor).replace(/,/g, "")));
  }, [line.priceMinor]);
  return (
    <div className="ig" style={{ height: 30, width: 120 }}>
      <span className="pre">PKR</span>
      <input
        inputMode="decimal"
        aria-label={`Unit price of ${line.name}`}
        value={text}
        onChange={(e) => {
          const v = e.target.value.replace(/[^\d.]/g, "");
          setText(v);
          const n = parseFloat(v);
          if (!Number.isNaN(n) && n >= 0) onChange(Math.round(n * 100));
        }}
        style={{ textAlign: "right" }}
      />
    </div>
  );
}
