"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  correctPayment,
  createPayment,
  getDailyPaymentTotal,
  getPayment,
  listPayments,
  voidPayment,
} from "@/lib/api/payments";
import {
  PaymentCorrectInput,
  PaymentCreateInput,
  PaymentVoidInput,
} from "@/lib/schemas/payments";

/** Payments change today's collections and customer balances, so refresh those views too. */
function invalidatePaymentEffects(queryClient: ReturnType<typeof useQueryClient>, orgId: string) {
  queryClient.invalidateQueries({ queryKey: paymentQueryKeys.all(orgId) });
  queryClient.invalidateQueries({ queryKey: ["dashboard", orgId] });
  queryClient.invalidateQueries({ queryKey: ["customers", orgId, "balances"] });
}

export const paymentQueryKeys = {
  all: (orgId: string) => ["payments", orgId] as const,
  lists: (orgId: string) => [...paymentQueryKeys.all(orgId), "list"] as const,
  list: (
    orgId: string,
    filters?: {
      status?: string;
      customerId?: string;
      orderId?: string;
      channel?: string;
    }
  ) => [...paymentQueryKeys.lists(orgId), filters] as const,
  dailyTotal: (orgId: string, targetDate?: string) =>
    [...paymentQueryKeys.all(orgId), "daily-total", targetDate] as const,
  details: (orgId: string) => [...paymentQueryKeys.all(orgId), "detail"] as const,
  detail: (orgId: string, paymentId: string) =>
    [...paymentQueryKeys.details(orgId), paymentId] as const,
};

export function usePayments(
  orgId: string,
  params?: {
    status?: string;
    customerId?: string;
    orderId?: string;
    channel?: string;
    limit?: number;
    offset?: number;
  },
  token?: string
) {
  return useQuery({
    queryKey: paymentQueryKeys.list(orgId, {
      status: params?.status,
      customerId: params?.customerId,
      orderId: params?.orderId,
      channel: params?.channel,
    }),
    queryFn: () => listPayments(orgId, params, token),
    enabled: !!orgId,
  });
}

export function usePayment(orgId: string, paymentId: string, token?: string) {
  return useQuery({
    queryKey: paymentQueryKeys.detail(orgId, paymentId),
    queryFn: () => getPayment(orgId, paymentId, token),
    enabled: !!orgId && !!paymentId,
  });
}

export function useDailyPaymentTotal(
  orgId: string,
  targetDate?: string,
  token?: string
) {
  return useQuery({
    queryKey: paymentQueryKeys.dailyTotal(orgId, targetDate),
    queryFn: () => getDailyPaymentTotal(orgId, targetDate, token),
    enabled: !!orgId,
  });
}

export function useCreatePayment(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      payload,
      idempotencyKey,
    }: {
      payload: PaymentCreateInput;
      idempotencyKey?: string;
    }) => createPayment(orgId, payload, token, idempotencyKey),
    onSuccess: () => invalidatePaymentEffects(queryClient, orgId),
  });
}

export function useVoidPayment(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      paymentId,
      payload,
      idempotencyKey,
    }: {
      paymentId: string;
      payload: PaymentVoidInput;
      idempotencyKey?: string;
    }) => voidPayment(orgId, paymentId, payload, token, idempotencyKey),
    onSuccess: (_, variables) => {
      invalidatePaymentEffects(queryClient, orgId);
      queryClient.invalidateQueries({
        queryKey: paymentQueryKeys.detail(orgId, variables.paymentId),
      });
    },
  });
}

export function useCorrectPayment(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      paymentId,
      payload,
      idempotencyKey,
    }: {
      paymentId: string;
      payload: PaymentCorrectInput;
      idempotencyKey?: string;
    }) => correctPayment(orgId, paymentId, payload, token, idempotencyKey),
    onSuccess: (_, variables) => {
      invalidatePaymentEffects(queryClient, orgId);
      queryClient.invalidateQueries({
        queryKey: paymentQueryKeys.detail(orgId, variables.paymentId),
      });
    },
  });
}
