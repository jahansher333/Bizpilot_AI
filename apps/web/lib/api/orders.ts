import {
  Order,
  OrderCorrectInput,
  OrderCreateInput,
  OrderListResponse,
  OrderVoidInput,
} from "@/lib/schemas/orders";
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

export async function listOrders(
  orgId: string,
  params?: {
    status?: string;
    customerId?: string;
    limit?: number;
    offset?: number;
  },
  token?: string
): Promise<OrderListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.customerId) searchParams.set("customer_id", params.customerId);
  if (params?.limit !== undefined) searchParams.set("limit", params.limit.toString());
  if (params?.offset !== undefined) searchParams.set("offset", params.offset.toString());

  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<OrderListResponse>(
    `/api/organizations/${orgId}/orders${query}`,
    { method: "GET" },
    token
  );
}

export async function getOrder(
  orgId: string,
  orderId: string,
  token?: string
): Promise<Order> {
  return request<Order>(
    `/api/organizations/${orgId}/orders/${orderId}`,
    { method: "GET" },
    token
  );
}

export async function createOrder(
  orgId: string,
  payload: OrderCreateInput,
  token?: string,
  idempotencyKey?: string
): Promise<Order> {
  return request<Order>(
    `/api/organizations/${orgId}/orders`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}

export async function voidOrder(
  orgId: string,
  orderId: string,
  payload: OrderVoidInput,
  token?: string,
  idempotencyKey?: string
): Promise<Order> {
  return request<Order>(
    `/api/organizations/${orgId}/orders/${orderId}/void`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}

export async function correctOrder(
  orgId: string,
  orderId: string,
  payload: OrderCorrectInput,
  token?: string,
  idempotencyKey?: string
): Promise<Order> {
  return request<Order>(
    `/api/organizations/${orgId}/orders/${orderId}/correct`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}
