"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  correctOrder,
  createOrder,
  getOrder,
  listOrders,
  voidOrder,
} from "@/lib/api/orders";
import {
  OrderCorrectInput,
  OrderCreateInput,
  OrderVoidInput,
} from "@/lib/schemas/orders";

export const orderQueryKeys = {
  all: (orgId: string) => ["orders", orgId] as const,
  lists: (orgId: string) => [...orderQueryKeys.all(orgId), "list"] as const,
  list: (orgId: string, filters?: { status?: string; customerId?: string }) =>
    [...orderQueryKeys.lists(orgId), filters] as const,
  details: (orgId: string) => [...orderQueryKeys.all(orgId), "detail"] as const,
  detail: (orgId: string, orderId: string) =>
    [...orderQueryKeys.details(orgId), orderId] as const,
};

export function useOrders(
  orgId: string,
  params?: {
    status?: string;
    customerId?: string;
    limit?: number;
    offset?: number;
  },
  token?: string
) {
  return useQuery({
    queryKey: orderQueryKeys.list(orgId, {
      status: params?.status,
      customerId: params?.customerId,
    }),
    queryFn: () => listOrders(orgId, params, token),
    enabled: !!orgId,
  });
}

export function useOrder(orgId: string, orderId: string, token?: string) {
  return useQuery({
    queryKey: orderQueryKeys.detail(orgId, orderId),
    queryFn: () => getOrder(orgId, orderId, token),
    enabled: !!orgId && !!orderId,
  });
}

export function useCreateOrder(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      payload,
      idempotencyKey,
    }: {
      payload: OrderCreateInput;
      idempotencyKey?: string;
    }) => createOrder(orgId, payload, token, idempotencyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: orderQueryKeys.lists(orgId) });
      // Invalidate inventory balances as stock has changed
      queryClient.invalidateQueries({ queryKey: ["inventory", orgId] });
    },
  });
}

export function useVoidOrder(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      orderId,
      payload,
      idempotencyKey,
    }: {
      orderId: string;
      payload: OrderVoidInput;
      idempotencyKey?: string;
    }) => voidOrder(orgId, orderId, payload, token, idempotencyKey),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: orderQueryKeys.lists(orgId) });
      queryClient.invalidateQueries({
        queryKey: orderQueryKeys.detail(orgId, variables.orderId),
      });
      // Invalidate inventory balances as stock has been restored
      queryClient.invalidateQueries({ queryKey: ["inventory", orgId] });
    },
  });
}

export function useCorrectOrder(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      orderId,
      payload,
      idempotencyKey,
    }: {
      orderId: string;
      payload: OrderCorrectInput;
      idempotencyKey?: string;
    }) => correctOrder(orgId, orderId, payload, token, idempotencyKey),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: orderQueryKeys.lists(orgId) });
      queryClient.invalidateQueries({
        queryKey: orderQueryKeys.detail(orgId, variables.orderId),
      });
      // Invalidate inventory balances as stock has changed
      queryClient.invalidateQueries({ queryKey: ["inventory", orgId] });
    },
  });
}
