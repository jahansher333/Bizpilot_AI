import { AssistantRequest, AssistantResponse } from "@/lib/schemas/assistant";
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

export async function sendAssistantQuery(
  orgId: string,
  payload: AssistantRequest,
  token?: string
): Promise<AssistantResponse> {
  return request<AssistantResponse>(
    `/api/organizations/${orgId}/ai/chat`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}
