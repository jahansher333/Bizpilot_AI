import {
  InventoryBalance,
  InventoryBalanceListResponse,
  InventoryMovementListResponse,
  InventoryMutationResponse,
  OpeningStockInput,
  AdjustmentInput,
  CorrectionInput,
  VoidReversalInput,
} from "@/lib/schemas/inventory";
import { ApiError } from "@/lib/api/catalog";

const getApiBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "";
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
};

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `Request failed with status ${res.status}`;
    let errorCode: string | undefined;

    try {
      const data = await res.json();
      if (data.error && data.error.message) {
        errorMsg = data.error.message;
        errorCode = data.error.code;
      } else if (data.detail) {
        errorMsg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      errorMsg = res.statusText || errorMsg;
    }

    throw new ApiError(errorMsg, res.status, errorCode);
  }
  return (await res.json()) as T;
}

function getHeaders(token?: string, idempotencyKey?: string): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }
  return headers;
}

export async function fetchBalances(
  orgId: string,
  limit = 50,
  offset = 0,
  token?: string
): Promise<InventoryBalanceListResponse> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/organizations/${orgId}/inventory/balances?limit=${limit}&offset=${offset}`;
  const res = await fetch(url, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<InventoryBalanceListResponse>(res);
}

export async function fetchBalance(
  orgId: string,
  productId: string,
  token?: string
): Promise<InventoryBalance> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/organizations/${orgId}/inventory/balances/${productId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<InventoryBalance>(res);
}

export async function fetchMovements(
  orgId: string,
  params?: { productId?: string; movementType?: string; limit?: number; offset?: number },
  token?: string
): Promise<InventoryMovementListResponse> {
  const baseUrl = getApiBaseUrl();
  const query = new URLSearchParams();
  if (params?.productId) query.append("product_id", params.productId);
  if (params?.movementType) query.append("movement_type", params.movementType);
  if (params?.limit) query.append("limit", params.limit.toString());
  if (params?.offset) query.append("offset", params.offset.toString());

  const url = `${baseUrl}/api/organizations/${orgId}/inventory/movements?${query.toString()}`;
  const res = await fetch(url, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<InventoryMovementListResponse>(res);
}

export async function recordOpeningStock(
  orgId: string,
  input: OpeningStockInput,
  token?: string
): Promise<InventoryMutationResponse> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/organizations/${orgId}/inventory/opening-stock`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token),
    body: JSON.stringify(input),
  });
  return handleResponse<InventoryMutationResponse>(res);
}

export async function recordAdjustment(
  orgId: string,
  input: AdjustmentInput,
  token?: string,
  idempotencyKey?: string
): Promise<InventoryMutationResponse> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/organizations/${orgId}/inventory/adjustments`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token, idempotencyKey),
    body: JSON.stringify(input),
  });
  return handleResponse<InventoryMutationResponse>(res);
}

export async function recordCorrection(
  orgId: string,
  input: CorrectionInput,
  token?: string,
  idempotencyKey?: string
): Promise<InventoryMutationResponse> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/organizations/${orgId}/inventory/corrections`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token, idempotencyKey),
    body: JSON.stringify(input),
  });
  return handleResponse<InventoryMutationResponse>(res);
}

export async function recordVoidReversal(
  orgId: string,
  input: VoidReversalInput,
  token?: string,
  idempotencyKey?: string
): Promise<InventoryMutationResponse> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/organizations/${orgId}/inventory/void-reversals`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token, idempotencyKey),
    body: JSON.stringify(input),
  });
  return handleResponse<InventoryMutationResponse>(res);
}
