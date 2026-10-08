import "./zod-config";
import { z } from "zod";

export const expenseCategoryStatusEnum = z.enum(["active", "archived"]);
export type ExpenseCategoryStatus = z.infer<typeof expenseCategoryStatusEnum>;

export const expenseStatusEnum = z.enum(["active", "voided", "corrected"]);
export type ExpenseStatus = z.infer<typeof expenseStatusEnum>;

export const expensePaymentMethodEnum = z.enum([
  "cash",
  "bank_transfer",
  "cheque",
  "mobile_wallet",
  "digital",
  "other",
]);
export type ExpensePaymentMethod = z.infer<typeof expensePaymentMethodEnum>;

export const EXPENSE_METHOD_LABEL: Record<string, string> = {
  cash: "Cash",
  bank_transfer: "Bank transfer",
  cheque: "Cheque",
  mobile_wallet: "Mobile wallet",
  digital: "Card / online",
  other: "Other",
};

export const expenseCategoryCreateSchema = z.object({
  name: z.string().trim().min(1, "Category name is required").max(100, "Category name cannot exceed 100 characters"),
});
export type ExpenseCategoryCreateInput = z.infer<typeof expenseCategoryCreateSchema>;

export const expenseCategorySchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  name: z.string(),
  status: expenseCategoryStatusEnum,
  created_at: z.string(),
  updated_at: z.string(),
});
export type ExpenseCategory = z.infer<typeof expenseCategorySchema>;

export const expenseCategoryListResponseSchema = z.object({
  items: z.array(expenseCategorySchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});
export type ExpenseCategoryListResponse = z.infer<typeof expenseCategoryListResponseSchema>;

export const expenseCreateSchema = z.object({
  amount_minor: z
    .number()
    .int("Amount must be a whole minor unit")
    .positive("Amount must be greater than zero"),
  expense_category_id: z
    .string()
    .uuid("Invalid category ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  occurred_at: z.string().optional(),
  payment_method: expensePaymentMethodEnum.default("cash"),
  payee: z.string().trim().max(255).optional().nullable(),
  description: z.string().trim().max(1000).optional().nullable(),
  currency_code: z.string().length(3).default("PKR"),
});
export type ExpenseCreateInput = z.infer<typeof expenseCreateSchema>;

export const expenseVoidSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(3, "Reason must be at least 3 characters")
    .max(255, "Reason cannot exceed 255 characters"),
});
export type ExpenseVoidInput = z.infer<typeof expenseVoidSchema>;

export const expenseCorrectSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(3, "Reason must be at least 3 characters")
    .max(255, "Reason cannot exceed 255 characters"),
  amount_minor: z
    .number()
    .int("Amount must be a whole minor unit")
    .positive("Amount must be greater than zero"),
  expense_category_id: z
    .string()
    .uuid("Invalid category ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  occurred_at: z.string().optional(),
  payment_method: expensePaymentMethodEnum.default("cash"),
  payee: z.string().trim().max(255).optional().nullable(),
  description: z.string().trim().max(1000).optional().nullable(),
  currency_code: z.string().length(3).default("PKR"),
});
export type ExpenseCorrectInput = z.infer<typeof expenseCorrectSchema>;

export const expenseSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  expense_category_id: z.string().uuid().nullable().optional(),
  amount_minor: z.number().int(),
  currency_code: z.string(),
  occurred_at: z.string(),
  payment_method: expensePaymentMethodEnum,
  payee: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  status: expenseStatusEnum,
  created_by_user_id: z.string().uuid().nullable().optional(),
  corrects_expense_id: z.string().uuid().nullable().optional(),
  replaced_by_expense_id: z.string().uuid().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  voided_at: z.string().nullable().optional(),
});
export type Expense = z.infer<typeof expenseSchema>;

export const expenseListResponseSchema = z.object({
  items: z.array(expenseSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});
export type ExpenseListResponse = z.infer<typeof expenseListResponseSchema>;

export const dailyExpenseTotalResponseSchema = z.object({
  date: z.string(),
  total_minor: z.number().int(),
  expense_count: z.number().int(),
  currency_code: z.string(),
});
export type DailyExpenseTotalResponse = z.infer<typeof dailyExpenseTotalResponseSchema>;

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

/**
 * Convert human-readable major units (e.g. 150.50) into integer minor units (15050).
 */
export function toMinorUnits(majorUnits: number): number {
  return Math.round(majorUnits * 100);
}
