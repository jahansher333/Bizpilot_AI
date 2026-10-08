import "./zod-config";
import { z } from "zod";

export const dashboardPeriodEnum = z.enum([
  "today",
  "yesterday",
  "this_week",
  "this_month",
  "custom",
]);
export type DashboardPeriod = z.infer<typeof dashboardPeriodEnum>;

export const salesSummarySchema = z.object({
  order_count: z.number().int().min(0),
  total_sales_minor: z.number().int().min(0),
  currency_code: z.string().length(3),
});
export type SalesSummary = z.infer<typeof salesSummarySchema>;

export const paymentsSummarySchema = z.object({
  payment_count: z.number().int().min(0),
  total_collected_minor: z.number().int().min(0),
  currency_code: z.string().length(3),
});
export type PaymentsSummary = z.infer<typeof paymentsSummarySchema>;

export const expensesSummarySchema = z.object({
  expense_count: z.number().int().min(0),
  total_expenses_minor: z.number().int().min(0),
  currency_code: z.string().length(3),
});
export type ExpensesSummary = z.infer<typeof expensesSummarySchema>;

export const netCashSummarySchema = z.object({
  net_cash_minor: z.number().int(),
  currency_code: z.string().length(3),
  note: z.string().optional(),
});
export type NetCashSummary = z.infer<typeof netCashSummarySchema>;

export const lowStockItemSchema = z.object({
  product_id: z.string().uuid(),
  product_code: z.string(),
  product_name: z.string(),
  base_unit: z.string(),
  on_hand_quantity: z.number().int(),
  is_out_of_stock: z.boolean(),
});
export type LowStockItem = z.infer<typeof lowStockItemSchema>;

export const inventorySummarySchema = z.object({
  low_stock_count: z.number().int().min(0),
  low_stock_threshold: z.number().int().min(0),
  items: z.array(lowStockItemSchema),
});
export type InventorySummary = z.infer<typeof inventorySummarySchema>;

export const recentActivityItemSchema = z.object({
  id: z.string().uuid(),
  activity_type: z.enum(["order", "payment", "expense"]),
  reference_code: z.string(),
  amount_minor: z.number().int(),
  currency_code: z.string(),
  timestamp: z.string(),
  status: z.string(),
  description: z.string().nullable().optional(),
});
export type RecentActivityItem = z.infer<typeof recentActivityItemSchema>;

export const dashboardFreshnessSchema = z.object({
  generated_at: z.string(),
  period: z.string(),
  local_start_date: z.string(),
  local_end_date: z.string(),
  timezone: z.string(),
});
export type DashboardFreshness = z.infer<typeof dashboardFreshnessSchema>;

export const dashboardSummarySchema = z.object({
  sales: salesSummarySchema,
  payments: paymentsSummarySchema,
  expenses: expensesSummarySchema.nullable().optional(),
  net_cash: netCashSummarySchema.nullable().optional(),
  inventory: inventorySummarySchema,
  recent_activity: z.array(recentActivityItemSchema),
  freshness: dashboardFreshnessSchema,
});
export type DashboardSummary = z.infer<typeof dashboardSummarySchema>;

/**
 * Format minor currency units into human-readable currency representation.
 */
export function formatMoney(minorUnits: number, currencyCode: string = "PKR"): string {
  const major = (minorUnits / 100).toFixed(2);
  if (currencyCode === "PKR") {
    return `Rs. ${major}`;
  }
  return `${currencyCode} ${major}`;
}
