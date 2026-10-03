/**
 * Shared authenticated HTTP client (FIX-005).
 *
 * Attaches the access token, and on a 401 refreshes the session once (single-flight,
 * shared by concurrent requests) and retries the request with the new token.
 * When the refresh token itself is rejected, the stored session is cleared and
 * SESSION_EXPIRED_EVENT is dispatched so the AuthProvider can sign the user out.
 */

export const ACCESS_TOKEN_KEY = "bizpilot_access_token";
export const REFRESH_TOKEN_KEY = "bizpilot_refresh_token";
export const ACTIVE_ORG_KEY = "bizpilot_active_org_id";

export const SESSION_TOKENS_EVENT = "bizpilot:session-tokens";
export const SESSION_EXPIRED_EVENT = "bizpilot:session-expired";

export interface SessionTokensDetail {
  accessToken: string;
  refreshToken: string;
}

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function getStoredAccessToken(): string | null {
  return storage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
}

export function getStoredRefreshToken(): string | null {
  return storage()?.getItem(REFRESH_TOKEN_KEY) ?? null;
}

export function storeSessionTokens(accessToken: string, refreshToken: string): void {
  const store = storage();
  store?.setItem(ACCESS_TOKEN_KEY, accessToken);
  store?.setItem(REFRESH_TOKEN_KEY, refreshToken);
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<SessionTokensDetail>(SESSION_TOKENS_EVENT, {
        detail: { accessToken, refreshToken },
      })
    );
  }
}

export function clearStoredSession(): void {
  const store = storage();
  store?.removeItem(ACCESS_TOKEN_KEY);
  store?.removeItem(REFRESH_TOKEN_KEY);
  store?.removeItem(ACTIVE_ORG_KEY);
}

let refreshInFlight: Promise<string | null> | null = null;

/**
 * Exchange the stored refresh token for a new access token.
 * Returns null when no new token could be obtained. Only a rejected refresh token
 * (401) ends the session; network or server errors leave it intact.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refreshToken = getStoredRefreshToken();
      if (!refreshToken) return null;
      try {
        const res = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (res.status === 401) {
          clearStoredSession();
          if (typeof window !== "undefined") {
            window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
          }
          return null;
        }
        if (!res.ok) return null;
        const data = (await res.json()) as { access_token: string; refresh_token: string };
        storeSessionTokens(data.access_token, data.refresh_token);
        return data.access_token;
      } catch {
        return null;
      }
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

function withAuthorization(init: RequestInit, token: string | null): RequestInit {
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    headers.delete("Authorization");
  }
  return { ...init, headers };
}

/**
 * fetch() with the access token attached and one transparent refresh-and-retry on 401.
 * An explicit token (from React state) may be stale; the stored token wins on retry.
 */
export async function authorizedFetch(
  input: string,
  init: RequestInit = {},
  token?: string | null
): Promise<Response> {
  const usedToken = token || getStoredAccessToken();
  const response = await fetch(input, withAuthorization(init, usedToken));
  if (response.status !== 401 || !usedToken) {
    return response;
  }

  // Another request may already have refreshed; reuse that token instead of rotating again.
  const latest = getStoredAccessToken();
  const nextToken = latest && latest !== usedToken ? latest : await refreshAccessToken();
  if (!nextToken) {
    return response;
  }
  return fetch(input, withAuthorization(init, nextToken));
}
