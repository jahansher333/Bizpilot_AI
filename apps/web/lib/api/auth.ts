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
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = "An error occurred";
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

export async function loginUser(payload: LoginInput): Promise<AuthTokens> {
  return request<AuthTokens>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function registerUser(payload: RegisterInput): Promise<RegisterResponse> {
  return request<RegisterResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function refreshSessionToken(refreshToken: string): Promise<AuthTokens> {
  return request<AuthTokens>("/api/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function logoutUser(
  refreshToken: string,
  token?: string
): Promise<AuthMessageResponse> {
  return request<AuthMessageResponse>(
    "/api/auth/logout",
    {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    },
    token
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
  return request<AuthMessageResponse>("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function resetPasswordSubmit(
  payload: ResetPasswordInput
): Promise<AuthMessageResponse> {
  return request<AuthMessageResponse>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentUser(token: string): Promise<UserMe> {
  return request<UserMe>("/api/auth/me", { method: "GET" }, token);
}
