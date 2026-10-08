import "./zod-config";
import { z } from "zod";

/**
 * Normalizes phone numbers for client display or validation.
 */
export function normalizePhone(value: string | null | undefined): string | null {
  if (!value) return null;
  const val = value.trim();
  if (!val) return null;
  let cleaned = val.replace(/[\s\-\(\)\.]/g, "");
  if (!cleaned) return null;
  if (cleaned.startsWith("+92")) {
    cleaned = "0" + cleaned.slice(3);
  } else if (cleaned.startsWith("0092")) {
    cleaned = "0" + cleaned.slice(4);
  }
  return cleaned;
}

// ==============================================================================
// Customer Schemas
// ==============================================================================

export const customerSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  name: z.string().min(1, "Customer name is required").max(255),
  phone: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  status: z.enum(["active", "archived"]),
  created_by_user_id: z.string().uuid().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  archived_at: z.string().nullable().optional(),
});

export type Customer = z.infer<typeof customerSchema>;

export const customerListResponseSchema = z.object({
  items: z.array(customerSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});

export type CustomerListResponse = z.infer<typeof customerListResponseSchema>;

export const customerCreateSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Customer name must be at least 1 character")
    .max(255, "Customer name cannot exceed 255 characters"),
  phone: z
    .string()
    .trim()
    .max(32, "Phone number cannot exceed 32 characters")
    .optional()
    .transform((val) => normalizePhone(val) || undefined),
  email: z
    .string()
    .trim()
    .max(255, "Email cannot exceed 255 characters")
    .optional()
    .transform((val) => (val && val.length > 0 ? val : undefined)),
  notes: z
    .string()
    .trim()
    .max(2000, "Notes cannot exceed 2000 characters")
    .optional()
    .transform((val) => (val && val.length > 0 ? val : undefined)),
});

export type CustomerCreateInput = z.infer<typeof customerCreateSchema>;

export const customerUpdateSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Customer name must be at least 1 character")
    .max(255, "Customer name cannot exceed 255 characters")
    .optional(),
  phone: z
    .string()
    .trim()
    .max(32, "Phone number cannot exceed 32 characters")
    .optional()
    .transform((val) => (val ? normalizePhone(val) || undefined : undefined)),
  email: z
    .string()
    .trim()
    .max(255, "Email cannot exceed 255 characters")
    .optional()
    .transform((val) => (val && val.length > 0 ? val : undefined)),
  notes: z
    .string()
    .trim()
    .max(2000, "Notes cannot exceed 2000 characters")
    .optional()
    .transform((val) => (val && val.length > 0 ? val : undefined)),
});

export type CustomerUpdateInput = z.infer<typeof customerUpdateSchema>;

// ==============================================================================
// Customer balances (R5) — recorded active orders minus active payments
// ==============================================================================

export interface CustomerBalance {
  customer_id: string;
  order_count: number;
  voided_order_count: number;
  total_orders_minor: number;
  payment_count: number;
  total_payments_minor: number;
  balance_minor: number;
}

export interface CustomerBalancesResponse {
  currency_code: string;
  items: CustomerBalance[];
  customers_with_orders: number;
  customers_with_balance: number;
  outstanding_minor: number;
}
