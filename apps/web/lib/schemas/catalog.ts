import "./zod-config";
import { z } from "zod";

/**
 * Deterministically formats integer minor currency units to human-readable PKR string.
 * Example: 150000 -> "PKR 1,500.00", 0 -> "PKR 0.00".
 */
export function formatPriceMinor(minorUnits: number, currencyCode = "PKR"): string {
  if (!Number.isFinite(minorUnits) || minorUnits < 0) {
    return `${currencyCode} 0.00`;
  }
  const major = Math.floor(minorUnits / 100);
  const cents = Math.abs(minorUnits % 100);
  const formattedMajor = new Intl.NumberFormat("en-US").format(major);
  const formattedCents = cents.toString().padStart(2, "0");
  return `${currencyCode} ${formattedMajor}.${formattedCents}`;
}

/**
 * Deterministically converts human major-unit string input to integer minor units.
 * Avoids binary floating-point representation bugs by strictly parsing textual decimal parts.
 * Examples:
 *   "500" -> 50000
 *   "500.5" -> 50050
 *   "500.50" -> 50050
 *   "0.05" -> 5
 *   "0" -> 0
 * Rejects negative numbers, multiple decimal points, or more than 2 decimal places.
 */
export function parseMajorToMinor(majorStr: string): number {
  const trimmed = majorStr.trim();
  if (!trimmed) {
    throw new Error("Price is required");
  }

  // Regex strictly enforces positive/zero decimal number with up to 2 decimal places
  const match = trimmed.match(/^(\d+)(?:\.(\d{1,2}))?$/);
  if (!match) {
    throw new Error("Invalid price format. Must be a non-negative number with at most 2 decimal places");
  }

  const wholeStr = match[1];
  const decimalStr = match[2] || "";

  const whole = parseInt(wholeStr, 10);
  if (!Number.isSafeInteger(whole)) {
    throw new Error("Price value is too large");
  }

  const cents = decimalStr ? parseInt(decimalStr.padEnd(2, "0"), 10) : 0;
  return whole * 100 + cents;
}

// ==============================================================================
// Category Contracts
// ==============================================================================

export const categoryCreateSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Category name must be at least 2 characters")
    .max(100, "Category name must be at most 100 characters"),
});

export const categoryUpdateSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Category name must be at least 2 characters")
    .max(100, "Category name must be at most 100 characters"),
});

export type CategoryCreateInput = z.infer<typeof categoryCreateSchema>;
export type CategoryUpdateInput = z.infer<typeof categoryUpdateSchema>;

export interface Category {
  id: string;
  organization_id: string;
  name: string;
  status: "active" | "archived";
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface CategoryListResponse {
  items: Category[];
  total: number;
  limit: number;
  offset: number;
}

// ==============================================================================
// Product Contracts
// ==============================================================================

export const productCreateSchema = z.object({
  code: z
    .string()
    .trim()
    .min(1, "Product code must be at least 1 character")
    .max(64, "Product code must be at most 64 characters"),
  name: z
    .string()
    .trim()
    .min(2, "Product name must be at least 2 characters")
    .max(255, "Product name must be at most 255 characters"),
  base_unit: z
    .string()
    .trim()
    .min(1, "Base unit must be at least 1 character")
    .max(32, "Base unit must be at most 32 characters")
    .default("piece"),
  price_major: z
    .string()
    .trim()
    .min(1, "Default price is required")
    .refine(
      (val) => {
        try {
          parseMajorToMinor(val);
          return true;
        } catch {
          return false;
        }
      },
      { message: "Must be a valid positive price with at most 2 decimal places" }
    ),
  category_id: z.string().uuid("Invalid category ID").nullable().optional(),
});

export const productUpdateSchema = z.object({
  code: z
    .string()
    .trim()
    .min(1, "Product code must be at least 1 character")
    .max(64, "Product code must be at most 64 characters")
    .optional(),
  name: z
    .string()
    .trim()
    .min(2, "Product name must be at least 2 characters")
    .max(255, "Product name must be at most 255 characters")
    .optional(),
  base_unit: z
    .string()
    .trim()
    .min(1, "Base unit must be at least 1 character")
    .max(32, "Base unit must be at most 32 characters")
    .optional(),
  price_major: z
    .string()
    .trim()
    .refine(
      (val) => {
        if (!val) return true;
        try {
          parseMajorToMinor(val);
          return true;
        } catch {
          return false;
        }
      },
      { message: "Must be a valid positive price with at most 2 decimal places" }
    )
    .optional(),
  category_id: z.string().uuid("Invalid category ID").nullable().optional(),
});

export type ProductCreateFormInput = z.infer<typeof productCreateSchema>;
export type ProductUpdateFormInput = z.infer<typeof productUpdateSchema>;

export interface Product {
  id: string;
  organization_id: string;
  category_id: string | null;
  code: string;
  name: string;
  base_unit: string;
  default_price_minor: number;
  currency_code: string;
  status: "active" | "archived";
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}
