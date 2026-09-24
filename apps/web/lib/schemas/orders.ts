import { z } from "zod";

export const orderStatusEnum = z.enum(["active", "voided", "corrected"]);
export type OrderStatus = z.infer<typeof orderStatusEnum>;

export const orderItemCreateSchema = z.object({
  product_id: z.string().uuid("Please select a valid product"),
  quantity: z
    .number()
    .int("Quantity must be a whole number")
    .positive("Quantity must be greater than zero"),
  unit_price_minor: z
    .number()
    .int("Price must be an integer minor value")
    .nonnegative("Price cannot be negative"),
});

export type OrderItemCreateInput = z.infer<typeof orderItemCreateSchema>;

export const orderCreateSchema = z.object({
  customer_id: z
    .string()
    .uuid("Invalid customer ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  items: z
    .array(orderItemCreateSchema)
    .min(1, "Order must contain at least one line item"),
  currency_code: z.string().length(3).default("PKR"),
  ordered_at: z.string().optional(),
});

export type OrderCreateInput = z.infer<typeof orderCreateSchema>;

export const orderVoidSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(3, "Reason must be at least 3 characters")
    .max(255, "Reason cannot exceed 255 characters"),
});

export type OrderVoidInput = z.infer<typeof orderVoidSchema>;

export const orderCorrectSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(3, "Reason must be at least 3 characters")
    .max(255, "Reason cannot exceed 255 characters"),
  customer_id: z
    .string()
    .uuid("Invalid customer ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  items: z
    .array(orderItemCreateSchema)
    .min(1, "Replacement order must contain at least one line item"),
  currency_code: z.string().length(3).default("PKR"),
  ordered_at: z.string().optional(),
});

export type OrderCorrectInput = z.infer<typeof orderCorrectSchema>;

export const orderItemSchema = z.object({
  id: z.string().uuid(),
  order_id: z.string().uuid(),
  product_id: z.string().uuid().nullable().optional(),
  product_name_snapshot: z.string(),
  product_code_snapshot: z.string(),
  unit_snapshot: z.string(),
  quantity: z.number().int(),
  unit_price_minor: z.number().int(),
  line_total_minor: z.number().int(),
  currency_code: z.string(),
  created_at: z.string(),
});

export type OrderItem = z.infer<typeof orderItemSchema>;

export const orderSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  order_number: z.string(),
  customer_id: z.string().uuid().nullable().optional(),
  ordered_at: z.string(),
  status: orderStatusEnum,
  order_total_minor: z.number().int(),
  currency_code: z.string(),
  created_by_user_id: z.string().uuid().nullable().optional(),
  corrects_order_id: z.string().uuid().nullable().optional(),
  replaced_by_order_id: z.string().uuid().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  voided_at: z.string().nullable().optional(),
  items: z.array(orderItemSchema).default([]),
});

export type Order = z.infer<typeof orderSchema>;

export const orderListResponseSchema = z.object({
  items: z.array(orderSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});

export type OrderListResponse = z.infer<typeof orderListResponseSchema>;

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
