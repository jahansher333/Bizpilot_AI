import {
  DailyExpenseTotalResponse,
  Expense,
  ExpenseCategory,
  ExpenseCategoryCreateInput,
  ExpenseCategoryListResponse,
  ExpenseCorrectInput,
  ExpenseCreateInput,
  ExpenseListResponse,
  ExpenseVoidInput,
} from "@/lib/schemas/expenses";
import { authorizedFetch, getApiBaseUrl } from "@/lib/api/http";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  token?: string,
  idempotencyKey?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }

  const response = await authorizedFetch(
    `${getApiBaseUrl()}${endpoint}`,
    { ...options, headers },
    token
  );

  if (!response.ok) {
    let errorMessage = "An error occurred";
    try {
      const data = await response.json();
      errorMessage = data.detail || data.message || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

// Category API
export async function listExpenseCategories(
  orgId: string,
  params?: { status?: string; limit?: number; offset?: number },
  token?: string
): Promise<ExpenseCategoryListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.limit !== undefined) searchParams.set("limit", params.limit.toString());
  if (params?.offset !== undefined) searchParams.set("offset", params.offset.toString());

  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<ExpenseCategoryListResponse>(
    `/api/organizations/${orgId}/expense-categories${query}`,
    { method: "GET" },
    token
  );
}

export async function createExpenseCategory(
  orgId: string,
  payload: ExpenseCategoryCreateInput,
  token?: string
): Promise<ExpenseCategory> {
  return request<ExpenseCategory>(
    `/api/organizations/${orgId}/expense-categories`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

export async function updateExpenseCategory(
  orgId: string,
  categoryId: string,
  payload: ExpenseCategoryCreateInput,
  token?: string
): Promise<ExpenseCategory> {
  return request<ExpenseCategory>(
    `/api/organizations/${orgId}/expense-categories/${categoryId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    token
  );
}

export async function archiveExpenseCategory(
  orgId: string,
  categoryId: string,
  token?: string
): Promise<ExpenseCategory> {
  return request<ExpenseCategory>(
    `/api/organizations/${orgId}/expense-categories/${categoryId}/archive`,
    { method: "POST" },
    token
  );
}

// Expenses API
export async function listExpenses(
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
): Promise<ExpenseListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.categoryId) searchParams.set("category_id", params.categoryId);
  if (params?.startDate) searchParams.set("start_date", params.startDate);
  if (params?.endDate) searchParams.set("end_date", params.endDate);
  if (params?.limit !== undefined) searchParams.set("limit", params.limit.toString());
  if (params?.offset !== undefined) searchParams.set("offset", params.offset.toString());

  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<ExpenseListResponse>(
    `/api/organizations/${orgId}/expenses${query}`,
    { method: "GET" },
    token
  );
}

export async function getExpense(
  orgId: string,
  expenseId: string,
  token?: string
): Promise<Expense> {
  return request<Expense>(
    `/api/organizations/${orgId}/expenses/${expenseId}`,
    { method: "GET" },
    token
  );
}

export async function getDailyExpenseTotal(
  orgId: string,
  targetDate?: string,
  token?: string
): Promise<DailyExpenseTotalResponse> {
  const query = targetDate ? `?target_date=${encodeURIComponent(targetDate)}` : "";
  return request<DailyExpenseTotalResponse>(
    `/api/organizations/${orgId}/expenses/daily-total${query}`,
    { method: "GET" },
    token
  );
}

export async function createExpense(
  orgId: string,
  payload: ExpenseCreateInput,
  token?: string,
  idempotencyKey?: string
): Promise<Expense> {
  return request<Expense>(
    `/api/organizations/${orgId}/expenses`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}

export async function voidExpense(
  orgId: string,
  expenseId: string,
  payload: ExpenseVoidInput,
  token?: string,
  idempotencyKey?: string
): Promise<Expense> {
  return request<Expense>(
    `/api/organizations/${orgId}/expenses/${expenseId}/void`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}

export async function correctExpense(
  orgId: string,
  expenseId: string,
  payload: ExpenseCorrectInput,
  token?: string,
  idempotencyKey?: string
): Promise<Expense> {
  return request<Expense>(
    `/api/organizations/${orgId}/expenses/${expenseId}/correct`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}
