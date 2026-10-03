/** Matches the backend default dashboard `low_stock_threshold` (10). */
export const LOW_STOCK_THRESHOLD = 10;

export type StockStatus = "healthy" | "low" | "out" | "untracked";

/** `null` quantity means no opening stock has been recorded for the product yet. */
export function stockStatus(quantity: number | null | undefined, threshold = LOW_STOCK_THRESHOLD): StockStatus {
  if (quantity === null || quantity === undefined) return "untracked";
  if (quantity <= 0) return "out";
  if (quantity <= threshold) return "low";
  return "healthy";
}

export const STOCK_LABEL: Record<StockStatus, string> = {
  healthy: "Healthy",
  low: "Low stock",
  out: "Out of stock",
  untracked: "No stock recorded",
};

export function productThumb(code: string, name: string): string {
  const letters = (name.replace(/[^A-Za-z]/g, "") || code.replace(/[^A-Za-z]/g, "")).slice(0, 3);
  return (letters || code.slice(0, 3) || "—").toUpperCase();
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
