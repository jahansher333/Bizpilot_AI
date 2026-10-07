import { DashboardSummary } from "@/lib/schemas/dashboard";
import { authorizedFetch, getApiBaseUrl } from "@/lib/api/http";

import { ApiError } from "./errors";

export { ApiError };

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
      const errorData = await response.json();
      errorMessage =
        errorData.error?.message || errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

export async function getDashboard(
  orgId: string,
  params?: {
    period?: string;
    startDate?: string;
    endDate?: string;
    lowStockThreshold?: number;
  },
  token?: string
): Promise<DashboardSummary> {
  const searchParams = new URLSearchParams();
  if (params?.period) searchParams.set("period", params.period);
  if (params?.startDate) searchParams.set("start_date", params.startDate);
  if (params?.endDate) searchParams.set("end_date", params.endDate);
  if (params?.lowStockThreshold !== undefined) {
    searchParams.set("low_stock_threshold", params.lowStockThreshold.toString());
  }

  const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<DashboardSummary>(
    `/api/organizations/${orgId}/dashboard${query}`,
    { method: "GET" },
    token
  );
}
