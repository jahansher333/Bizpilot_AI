import { z } from "zod";

// ==============================================================================
// Inventory Balance & Movement Schemas
// ==============================================================================

export const inventoryBalanceSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  product_id: z.string().uuid(),
  on_hand_quantity: z.number().int(),
  version: z.number().int(),
  updated_at: z.string(),
});

export type InventoryBalance = z.infer<typeof inventoryBalanceSchema>;

export const inventoryBalanceListResponseSchema = z.object({
  items: z.array(inventoryBalanceSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});

export type InventoryBalanceListResponse = z.infer<typeof inventoryBalanceListResponseSchema>;

export const movementTypeSchema = z.enum([
  "opening",
  "sale",
  "adjustment",
  "correction",
  "void_reversal",
]);

export type MovementType = z.infer<typeof movementTypeSchema>;

export const inventoryMovementSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  product_id: z.string().uuid(),
  movement_type: movementTypeSchema,
  quantity_delta: z.number().int(),
  source_type: z.string(),
  source_id: z.string().uuid().nullable().optional(),
  reason: z.string().nullable().optional(),
  created_by_user_id: z.string().uuid().nullable().optional(),
  created_at: z.string(),
});

export type InventoryMovement = z.infer<typeof inventoryMovementSchema>;

export const inventoryMovementListResponseSchema = z.object({
  items: z.array(inventoryMovementSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});

export type InventoryMovementListResponse = z.infer<typeof inventoryMovementListResponseSchema>;

// ==============================================================================
// Mutation Input Schemas
// ==============================================================================

export const openingStockSchema = z.object({
  product_id: z.string().uuid("Product ID is required"),
  quantity: z
    .number()
    .int("Quantity must be an integer")
    .gt(0, "Opening stock quantity must be greater than zero"),
  reason: z.string().max(255).optional(),
});

export type OpeningStockInput = z.infer<typeof openingStockSchema>;

export const adjustmentSchema = z.object({
  product_id: z.string().uuid("Product ID is required"),
  quantity_delta: z
    .number()
    .int("Quantity delta must be an integer")
    .refine((v) => v !== 0, "Quantity delta cannot be zero"),
  reason: z
    .string()
    .trim()
    .min(3, "Reason is required (minimum 3 characters)")
    .max(255, "Reason cannot exceed 255 characters"),
});

export type AdjustmentInput = z.infer<typeof adjustmentSchema>;

export const correctionSchema = z.object({
  product_id: z.string().uuid("Product ID is required"),
  quantity_delta: z
    .number()
    .int("Quantity delta must be an integer")
    .refine((v) => v !== 0, "Correction delta cannot be zero"),
  reason: z
    .string()
    .trim()
    .min(3, "Reason is required (minimum 3 characters)")
    .max(255, "Reason cannot exceed 255 characters"),
});

export type CorrectionInput = z.infer<typeof correctionSchema>;

export const voidReversalSchema = z.object({
  product_id: z.string().uuid("Product ID is required"),
  quantity_delta: z
    .number()
    .int("Quantity delta must be an integer")
    .refine((v) => v !== 0, "Reversal delta cannot be zero"),
  source_id: z.string().uuid().optional(),
  reason: z.string().max(255).optional(),
});

export type VoidReversalInput = z.infer<typeof voidReversalSchema>;

export const inventoryMutationResponseSchema = z.object({
  balance: inventoryBalanceSchema,
  movement: inventoryMovementSchema,
});

export type InventoryMutationResponse = z.infer<typeof inventoryMutationResponseSchema>;
