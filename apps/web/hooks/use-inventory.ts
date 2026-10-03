import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchBalances,
  fetchBalance,
  fetchMovements,
  recordOpeningStock,
  recordAdjustment,
  recordCorrection,
  recordVoidReversal,
} from "@/lib/api/inventory";
import {
  OpeningStockInput,
  AdjustmentInput,
  CorrectionInput,
  VoidReversalInput,
} from "@/lib/schemas/inventory";

export const INVENTORY_KEYS = {
  all: ["inventory"] as const,
  balances: (orgId: string) => [...INVENTORY_KEYS.all, "balances", orgId] as const,
  balance: (orgId: string, productId: string) => [...INVENTORY_KEYS.balances(orgId), productId] as const,
  movements: (orgId: string, filters?: Record<string, unknown>) =>
    [...INVENTORY_KEYS.all, "movements", orgId, filters] as const,
};

export function useInventoryBalances(orgId: string, limit = 50, offset = 0, token?: string) {
  return useQuery({
    queryKey: [...INVENTORY_KEYS.balances(orgId), { limit, offset }],
    queryFn: () => fetchBalances(orgId, limit, offset, token),
    enabled: !!orgId,
  });
}

export function useProductBalance(orgId: string, productId: string, token?: string) {
  return useQuery({
    queryKey: INVENTORY_KEYS.balance(orgId, productId),
    queryFn: () => fetchBalance(orgId, productId, token),
    enabled: !!orgId && !!productId,
  });
}

export function useInventoryMovements(
  orgId: string,
  params?: { productId?: string; movementType?: string; limit?: number; offset?: number },
  token?: string
) {
  return useQuery({
    queryKey: INVENTORY_KEYS.movements(orgId, params),
    queryFn: () => fetchMovements(orgId, params, token),
    enabled: !!orgId,
  });
}

export function useRecordOpeningStock(orgId: string, token?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: OpeningStockInput) => recordOpeningStock(orgId, input, token),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balances(orgId) });
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balance(orgId, variables.product_id) });
      queryClient.invalidateQueries({ queryKey: [...INVENTORY_KEYS.all, "movements", orgId] });
    },
  });
}

export function useRecordAdjustment(orgId: string, token?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: AdjustmentInput; idempotencyKey?: string }) =>
      recordAdjustment(orgId, input, token, idempotencyKey),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balances(orgId) });
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balance(orgId, variables.input.product_id) });
      queryClient.invalidateQueries({ queryKey: [...INVENTORY_KEYS.all, "movements", orgId] });
    },
  });
}

export function useRecordCorrection(orgId: string, token?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: CorrectionInput; idempotencyKey?: string }) =>
      recordCorrection(orgId, input, token, idempotencyKey),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balances(orgId) });
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balance(orgId, variables.input.product_id) });
      queryClient.invalidateQueries({ queryKey: [...INVENTORY_KEYS.all, "movements", orgId] });
    },
  });
}

export function useRecordVoidReversal(orgId: string, token?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: VoidReversalInput; idempotencyKey?: string }) =>
      recordVoidReversal(orgId, input, token, idempotencyKey),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balances(orgId) });
      queryClient.invalidateQueries({ queryKey: INVENTORY_KEYS.balance(orgId, variables.input.product_id) });
      queryClient.invalidateQueries({ queryKey: [...INVENTORY_KEYS.all, "movements", orgId] });
    },
  });
}
