import {
  DailyPaymentTotalResponse,
  Payment,
  PaymentCorrectInput,
  PaymentCreateInput,
  PaymentListResponse,
  PaymentVoidInput,
} from "@/lib/schemas/payments";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

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

export async function listPayments(
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
): Promise<PaymentListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.customerId) searchParams.set("customer_id", params.customerId);
  if (params?.orderId) searchParams.set("order_id", params.orderId);
  if (params?.channel) searchParams.set("channel", params.channel);
  if (params?.limit !== undefined) searchParams.set("limit", params.limit.toString());
  if (params?.offset !== undefined) searchParams.set("offset", params.offset.toString());

  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<PaymentListResponse>(
    `/api/organizations/${orgId}/payments${query}`,
    { method: "GET" },
    token
  );
}

export async function getPayment(
  orgId: string,
  paymentId: string,
  token?: string
): Promise<Payment> {
  return request<Payment>(
    `/api/organizations/${orgId}/payments/${paymentId}`,
    { method: "GET" },
    token
  );
}

export async function getDailyPaymentTotal(
  orgId: string,
  targetDate?: string,
  token?: string
): Promise<DailyPaymentTotalResponse> {
  const query = targetDate ? `?target_date=${encodeURIComponent(targetDate)}` : "";
  return request<DailyPaymentTotalResponse>(
    `/api/organizations/${orgId}/payments/daily-total${query}`,
    { method: "GET" },
    token
  );
}

export async function createPayment(
  orgId: string,
  payload: PaymentCreateInput,
  token?: string,
  idempotencyKey?: string
): Promise<Payment> {
  return request<Payment>(
    `/api/organizations/${orgId}/payments`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}

export async function voidPayment(
  orgId: string,
  paymentId: string,
  payload: PaymentVoidInput,
  token?: string,
  idempotencyKey?: string
): Promise<Payment> {
  return request<Payment>(
    `/api/organizations/${orgId}/payments/${paymentId}/void`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}

export async function correctPayment(
  orgId: string,
  paymentId: string,
  payload: PaymentCorrectInput,
  token?: string,
  idempotencyKey?: string
): Promise<Payment> {
  return request<Payment>(
    `/api/organizations/${orgId}/payments/${paymentId}/correct`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
    idempotencyKey
  );
}
