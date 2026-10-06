"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveExpenseCategory,
  correctExpense,
  createExpense,
  createExpenseCategory,
  getDailyExpenseTotal,
  getExpense,
  listExpenseCategories,
  listExpenses,
  updateExpenseCategory,
  voidExpense,
} from "@/lib/api/expenses";
import {
  ExpenseCategoryCreateInput,
  ExpenseCorrectInput,
  ExpenseCreateInput,
  ExpenseVoidInput,
} from "@/lib/schemas/expenses";

/** Expenses change the dashboard's expenses and net cash, so refresh it too. */
function invalidateExpenseEffects(queryClient: ReturnType<typeof useQueryClient>, orgId: string) {
  queryClient.invalidateQueries({ queryKey: expenseQueryKeys.all(orgId) });
  queryClient.invalidateQueries({ queryKey: ["dashboard", orgId] });
}

export const expenseCategoryQueryKeys = {
  all: (orgId: string) => ["expense-categories", orgId] as const,
  lists: (orgId: string) => [...expenseCategoryQueryKeys.all(orgId), "list"] as const,
  list: (orgId: string, status?: string) =>
    [...expenseCategoryQueryKeys.lists(orgId), status] as const,
};

export const expenseQueryKeys = {
  all: (orgId: string) => ["expenses", orgId] as const,
  lists: (orgId: string) => [...expenseQueryKeys.all(orgId), "list"] as const,
  list: (
    orgId: string,
    filters?: {
      status?: string;
      categoryId?: string;
      startDate?: string;
      endDate?: string;
    }
  ) => [...expenseQueryKeys.lists(orgId), filters] as const,
  dailyTotal: (orgId: string, targetDate?: string) =>
    [...expenseQueryKeys.all(orgId), "daily-total", targetDate] as const,
  details: (orgId: string) => [...expenseQueryKeys.all(orgId), "detail"] as const,
  detail: (orgId: string, expenseId: string) =>
    [...expenseQueryKeys.details(orgId), expenseId] as const,
};

export function useExpenseCategories(orgId: string, status?: string, token?: string) {
  return useQuery({
    queryKey: expenseCategoryQueryKeys.list(orgId, status),
    queryFn: () => listExpenseCategories(orgId, { status }, token),
    enabled: !!orgId,
  });
}

export function useCreateExpenseCategory(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExpenseCategoryCreateInput) =>
      createExpenseCategory(orgId, payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expenseCategoryQueryKeys.all(orgId) });
    },
  });
}

export function useUpdateExpenseCategory(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ categoryId, payload }: { categoryId: string; payload: ExpenseCategoryCreateInput }) =>
      updateExpenseCategory(orgId, categoryId, payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expenseCategoryQueryKeys.all(orgId) });
    },
  });
}

export function useArchiveExpenseCategory(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (categoryId: string) => archiveExpenseCategory(orgId, categoryId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expenseCategoryQueryKeys.all(orgId) });
    },
  });
}

export function useExpenses(
  orgId: string,
  params?: {
    status?: string;
    categoryId?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
    offset?: number;
  },
  token?: string
) {
  return useQuery({
    queryKey: expenseQueryKeys.list(orgId, {
      status: params?.status,
      categoryId: params?.categoryId,
      startDate: params?.startDate,
      endDate: params?.endDate,
    }),
    queryFn: () => listExpenses(orgId, params, token),
    enabled: !!orgId,
  });
}

export function useExpense(orgId: string, expenseId: string, token?: string) {
  return useQuery({
    queryKey: expenseQueryKeys.detail(orgId, expenseId),
    queryFn: () => getExpense(orgId, expenseId, token),
    enabled: !!orgId && !!expenseId,
  });
}

export function useDailyExpenseTotal(
  orgId: string,
  targetDate?: string,
  token?: string
) {
  return useQuery({
    queryKey: expenseQueryKeys.dailyTotal(orgId, targetDate),
    queryFn: () => getDailyExpenseTotal(orgId, targetDate, token),
    enabled: !!orgId,
  });
}

export function useCreateExpense(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      payload,
      idempotencyKey,
    }: {
      payload: ExpenseCreateInput;
      idempotencyKey?: string;
    }) => createExpense(orgId, payload, token, idempotencyKey),
    onSuccess: () => {
      invalidateExpenseEffects(queryClient, orgId);
    },
  });
}

export function useVoidExpense(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      expenseId,
      payload,
      idempotencyKey,
    }: {
      expenseId: string;
      payload: ExpenseVoidInput;
      idempotencyKey?: string;
    }) => voidExpense(orgId, expenseId, payload, token, idempotencyKey),
    onSuccess: (_, variables) => {
      invalidateExpenseEffects(queryClient, orgId);
      queryClient.invalidateQueries({
        queryKey: expenseQueryKeys.detail(orgId, variables.expenseId),
      });
    },
  });
}

export function useCorrectExpense(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      expenseId,
      payload,
      idempotencyKey,
    }: {
      expenseId: string;
      payload: ExpenseCorrectInput;
      idempotencyKey?: string;
    }) => correctExpense(orgId, expenseId, payload, token, idempotencyKey),
    onSuccess: (_, variables) => {
      invalidateExpenseEffects(queryClient, orgId);
      queryClient.invalidateQueries({
        queryKey: expenseQueryKeys.detail(orgId, variables.expenseId),
      });
    },
  });
}
