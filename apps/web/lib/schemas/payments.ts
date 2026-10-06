import { z } from "zod";

/** Must match the backend PaymentChannel enum; anything else is rejected with 422. */
export const paymentChannelEnum = z.enum(["cash", "bank_transfer", "digital", "other"]);
export type PaymentChannel = z.infer<typeof paymentChannelEnum>;

export const PAYMENT_CHANNEL_LABEL: Record<string, string> = {
  cash: "Cash",
  bank_transfer: "Bank transfer",
  digital: "Digital wallet",
  other: "Other",
};

export const paymentStatusEnum = z.enum(["active", "voided", "corrected"]);
export type PaymentStatus = z.infer<typeof paymentStatusEnum>;

export const paymentCreateSchema = z.object({
  amount_minor: z
    .number()
    .int("Amount must be a whole minor unit")
    .positive("Amount must be greater than zero"),
  channel: paymentChannelEnum,
  account_label: z.string().trim().max(100).optional().nullable(),
  customer_id: z
    .string()
    .uuid("Invalid customer ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  order_id: z
    .string()
    .uuid("Invalid order ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  external_reference: z.string().trim().max(100).optional().nullable(),
  received_at: z.string().optional(),
  currency_code: z.string().length(3).default("PKR"),
  notes: z.string().trim().max(500).optional().nullable(),
});

export type PaymentCreateInput = z.infer<typeof paymentCreateSchema>;

export const paymentVoidSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(3, "Reason must be at least 3 characters")
    .max(255, "Reason cannot exceed 255 characters"),
});

export type PaymentVoidInput = z.infer<typeof paymentVoidSchema>;

export const paymentCorrectSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(3, "Reason must be at least 3 characters")
    .max(255, "Reason cannot exceed 255 characters"),
  amount_minor: z
    .number()
    .int("Amount must be a whole minor unit")
    .positive("Amount must be greater than zero"),
  channel: paymentChannelEnum,
  account_label: z.string().trim().max(100).optional().nullable(),
  customer_id: z
    .string()
    .uuid("Invalid customer ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  order_id: z
    .string()
    .uuid("Invalid order ID")
    .nullable()
    .optional()
    .or(z.literal("").transform(() => undefined)),
  external_reference: z.string().trim().max(100).optional().nullable(),
  received_at: z.string().optional(),
  currency_code: z.string().length(3).default("PKR"),
  notes: z.string().trim().max(500).optional().nullable(),
});

export type PaymentCorrectInput = z.infer<typeof paymentCorrectSchema>;

export const paymentSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  payment_number: z.string(),
  amount_minor: z.number().int(),
  channel: paymentChannelEnum,
  account_label: z.string().nullable().optional(),
  customer_id: z.string().uuid().nullable().optional(),
  order_id: z.string().uuid().nullable().optional(),
  external_reference: z.string().nullable().optional(),
  received_at: z.string(),
  status: paymentStatusEnum,
  currency_code: z.string(),
  notes: z.string().nullable().optional(),
  created_by_user_id: z.string().uuid().nullable().optional(),
  corrects_payment_id: z.string().uuid().nullable().optional(),
  replaced_by_payment_id: z.string().uuid().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  voided_at: z.string().nullable().optional(),
});

export type Payment = z.infer<typeof paymentSchema>;

export const paymentListResponseSchema = z.object({
  items: z.array(paymentSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});

export type PaymentListResponse = z.infer<typeof paymentListResponseSchema>;

export const dailyPaymentTotalResponseSchema = z.object({
  date: z.string(),
  total_minor: z.number().int(),
  payment_count: z.number().int(),
  currency_code: z.string(),
});

export type DailyPaymentTotalResponse = z.infer<typeof dailyPaymentTotalResponseSchema>;

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
