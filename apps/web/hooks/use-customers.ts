"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveCustomer,
  createCustomer,
  getCustomer,
  getCustomerBalances,
  listCustomers,
  updateCustomer,
} from "@/lib/api/customers";
import {
  CustomerCreateInput,
  CustomerUpdateInput,
} from "@/lib/schemas/customers";

export const customerQueryKeys = {
  all: (orgId: string) => ["customers", orgId] as const,
  lists: (orgId: string) => [...customerQueryKeys.all(orgId), "list"] as const,
  list: (orgId: string, filters?: { status?: string; search?: string }) =>
    [...customerQueryKeys.lists(orgId), filters] as const,
  details: (orgId: string) => [...customerQueryKeys.all(orgId), "detail"] as const,
  detail: (orgId: string, customerId: string) =>
    [...customerQueryKeys.details(orgId), customerId] as const,
  balances: (orgId: string, customerId?: string) =>
    [...customerQueryKeys.all(orgId), "balances", customerId ?? "all"] as const,
};

export function useCustomers(
  orgId: string,
  params?: {
    status?: string;
    search?: string;
    limit?: number;
    offset?: number;
  },
  token?: string
) {
  return useQuery({
    queryKey: customerQueryKeys.list(orgId, {
      status: params?.status,
      search: params?.search,
    }),
    queryFn: () => listCustomers(orgId, params, token),
    enabled: !!orgId,
  });
}

export function useCustomer(orgId: string, customerId: string, token?: string) {
  return useQuery({
    queryKey: customerQueryKeys.detail(orgId, customerId),
    queryFn: () => getCustomer(orgId, customerId, token),
    enabled: !!orgId && !!customerId,
  });
}

export function useCreateCustomer(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CustomerCreateInput) =>
      createCustomer(orgId, payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customerQueryKeys.lists(orgId) });
    },
  });
}

export function useUpdateCustomer(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      customerId,
      payload,
    }: {
      customerId: string;
      payload: CustomerUpdateInput;
    }) => updateCustomer(orgId, customerId, payload, token),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: customerQueryKeys.lists(orgId) });
      queryClient.invalidateQueries({
        queryKey: customerQueryKeys.detail(orgId, variables.customerId),
      });
    },
  });
}

export function useArchiveCustomer(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (customerId: string) => archiveCustomer(orgId, customerId, token),
    onSuccess: (_, customerId) => {
      queryClient.invalidateQueries({ queryKey: customerQueryKeys.lists(orgId) });
      queryClient.invalidateQueries({
        queryKey: customerQueryKeys.detail(orgId, customerId),
      });
    },
  });
}

/** Balances are a financial view: enable only for Owners and Managers. */
export function useCustomerBalances(orgId: string, customerId?: string, enabled = true, token?: string) {
  return useQuery({
    queryKey: customerQueryKeys.balances(orgId, customerId),
    queryFn: () => getCustomerBalances(orgId, customerId, token),
    enabled: !!orgId && enabled,
  });
}