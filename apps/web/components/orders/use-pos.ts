"use client";

import { useMemo, useRef, useState } from "react";
import { useCreateOrder } from "@/hooks/use-orders";
import { useCategories } from "@/hooks/use-catalog";
import { useCustomers } from "@/hooks/use-customers";
import { Order } from "@/lib/schemas/orders";
import { newIdempotencyKey } from "@/lib/stock";
import { CartLine, SellableProduct, cartTotal, cartUnits, useSellableProducts } from "@/components/orders/order-cart";
import { WALK_IN } from "@/components/orders/order-meta";

/** Cart, customer and submit logic shared by the desktop POS and the 4-step phone flow. */
export function usePos(orgId: string, token?: string, initialCustomerId?: string) {
  const products = useSellableProducts(orgId, token);
  const { data: categories } = useCategories(orgId, { status: "active", limit: 100 }, token);
  const { data: customers } = useCustomers(orgId, { status: "active", limit: 100 }, token);
  const createMutation = useCreateOrder(orgId, token);

  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string>("all");
  const [customerId, setCustomerId] = useState(initialCustomerId ?? "");
  const [lines, setLines] = useState<CartLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Order | null>(null);
  // One key per cart: a retried submit of the same cart can never create a second order.
  const idemKey = useRef(newIdempotencyKey());

  const query = q.trim().toLowerCase();
  const visible = useMemo(
    () => products.items.filter((p) => (cat === "all" || p.category_id === cat) && (!query || `${p.name} ${p.code}`.toLowerCase().includes(query))),
    [products.items, cat, query]
  );
  const inCart = new Map(lines.map((l) => [l.productId, l.qty]));
  const customerName = customers?.items.find((c) => c.id === customerId)?.name ?? WALK_IN;

  function changed() {
    idemKey.current = newIdempotencyKey();
    setError(null);
  }

  function add(p: SellableProduct) {
    const qty = inCart.get(p.id) ?? 0;
    if (qty >= p.stock) return;
    changed();
    setLines((current) =>
      qty > 0
        ? current.map((l) => (l.productId === p.id ? { ...l, qty: l.qty + 1 } : l))
        : [...current, { productId: p.id, name: p.name, code: p.code, unit: p.base_unit, qty: 1, priceMinor: p.default_price_minor, max: p.stock }]
    );
  }

  function setQty(productId: string, qty: number) {
    changed();
    setLines((current) => (qty <= 0 ? current.filter((l) => l.productId !== productId) : current.map((l) => (l.productId === productId ? { ...l, qty: Math.min(qty, l.max) } : l))));
  }

  function setPrice(productId: string, priceMinor: number) {
    changed();
    setLines((current) => current.map((l) => (l.productId === productId ? { ...l, priceMinor } : l)));
  }

  function chooseCustomer(id: string) {
    changed();
    setCustomerId(id);
  }

  async function complete(): Promise<boolean> {
    if (lines.length === 0 || createMutation.isPending) return false;
    setError(null);
    try {
      const order = await createMutation.mutateAsync({
        payload: {
          customer_id: customerId || undefined,
          items: lines.map((l) => ({ product_id: l.productId, quantity: l.qty, unit_price_minor: l.priceMinor })),
          currency_code: "PKR",
        },
        idempotencyKey: idemKey.current,
      });
      setDone(order);
      return true;
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t complete the order. Nothing was saved.");
      return false;
    }
  }

  function reset() {
    setDone(null);
    setLines([]);
    setCustomerId("");
    setQ("");
    idemKey.current = newIdempotencyKey();
  }

  return {
    products,
    categories: categories?.items ?? [],
    customers: customers?.items ?? [],
    q,
    setQ,
    cat,
    setCat,
    query,
    visible,
    inCart,
    lines,
    total: cartTotal(lines),
    units: cartUnits(lines),
    customerId,
    chooseCustomer,
    customerName,
    add,
    setQty,
    setPrice,
    complete,
    reset,
    error,
    done,
    pending: createMutation.isPending,
  };
}

export type Pos = ReturnType<typeof usePos>;
