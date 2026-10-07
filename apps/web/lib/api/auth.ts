import {
  AuthMessageResponse,
  AuthTokens,
  ForgotPasswordInput,
  LoginInput,
  RegisterInput,
  RegisterResponse,
  ResetPasswordInput,
  UserMe,
} from "@/lib/schemas/auth";

import { authorizedFetch, getApiBaseUrl } from "@/lib/api/http";

export { ACCESS_TOKEN_KEY, getStoredAccessToken } from "@/lib/api/http";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Public auth endpoints (login, register, refresh, recovery) pass `authenticated: false`
 * so a credential 401 never triggers a session refresh.
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  token?: string,
  authenticated = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const url = `${getApiBaseUrl()}${endpoint}`;
  const init = { ...options, headers };
  const response = authenticated ? await authorizedFetch(url, init, token) : await fetch(url, init);

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

export async function loginUser(payload: LoginInput): Promise<AuthTokens> {
  return request<AuthTokens>(
    "/api/auth/login",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    undefined,
    false
  );
}

export async function registerUser(payload: RegisterInput): Promise<RegisterResponse> {
  return request<RegisterResponse>(
    "/api/auth/register",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    undefined,
    false
  );
}

export async function logoutUser(
  refreshToken: string,
  token?: string
): Promise<AuthMessageResponse> {
  // The endpoint is authorized by the refresh token in the body, never by refreshing first.
  return request<AuthMessageResponse>(
    "/api/auth/logout",
    {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    },
    token,
    false
  );
}

export async function logoutAllSessions(token: string): Promise<AuthMessageResponse> {
  return request<AuthMessageResponse>(
    "/api/auth/logout-all",
    {
      method: "POST",
    },
    token
  );
}

export async function forgotPasswordRequest(
  payload: ForgotPasswordInput
): Promise<AuthMessageResponse> {
  return request<AuthMessageResponse>(
    "/api/auth/forgot-password",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    undefined,
    false
  );
}

export async function resetPasswordSubmit(
  payload: ResetPasswordInput
): Promise<AuthMessageResponse> {
  return request<AuthMessageResponse>(
    "/api/auth/reset-password",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    undefined,
    false
  );
}

export async function getCurrentUser(token: string): Promise<UserMe> {
  return request<UserMe>("/api/auth/me", { method: "GET" }, token);
}
