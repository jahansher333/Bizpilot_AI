import {
  Customer,
  CustomerCreateInput,
  CustomerBalancesResponse,
  CustomerListResponse,
  CustomerUpdateInput,
} from "@/lib/schemas/customers";
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
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

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

export async function listCustomers(
  orgId: string,
  params?: {
    status?: string;
    search?: string;
    limit?: number;
    offset?: number;
  },
  token?: string
): Promise<CustomerListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.append("status", params.status);
  if (params?.search) searchParams.append("search", params.search);
  if (params?.limit) searchParams.append("limit", params.limit.toString());
  if (params?.offset) searchParams.append("offset", params.offset.toString());

  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<CustomerListResponse>(
    `/api/organizations/${orgId}/customers${query}`,
    { method: "GET" },
    token
  );
}

export async function getCustomer(
  orgId: string,
  customerId: string,
  token?: string
): Promise<Customer> {
  return request<Customer>(
    `/api/organizations/${orgId}/customers/${customerId}`,
    { method: "GET" },
    token
  );
}

export async function createCustomer(
  orgId: string,
  payload: CustomerCreateInput,
  token?: string
): Promise<Customer> {
  return request<Customer>(
    `/api/organizations/${orgId}/customers`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

export async function updateCustomer(
  orgId: string,
  customerId: string,
  payload: CustomerUpdateInput,
  token?: string
): Promise<Customer> {
  return request<Customer>(
    `/api/organizations/${orgId}/customers/${customerId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    token
  );
}

export async function archiveCustomer(
  orgId: string,
  customerId: string,
  token?: string
): Promise<Customer> {
  return request<Customer>(
    `/api/organizations/${orgId}/customers/${customerId}/archive`,
    { method: "POST" },
    token
  );
}

/** Owner/Manager only: recorded order and payment totals per customer (R5). */
export async function getCustomerBalances(
  orgId: string,
  customerId?: string,
  token?: string
): Promise<CustomerBalancesResponse> {
  const qs = customerId ? `?customer_id=${encodeURIComponent(customerId)}` : "";
  return request<CustomerBalancesResponse>(
    `/api/organizations/${orgId}/customers/balances${qs}`,
    { method: "GET" },
    token
  );
}