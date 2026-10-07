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

/**
 * True when a JWT access token is still usable for at least `marginSeconds`. Only the `exp`
 * claim is read (no verification — the API verifies every request); anything unreadable counts
 * as expired, so the caller falls back to a refresh.
 */
export function isAccessTokenFresh(token: string | null, marginSeconds = 30, nowMs: number = Date.now()): boolean {
  if (!token) return false;
  try {
    const payload = token.split(".")[1];
    if (!payload) return false;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(payload.length / 4) * 4, "=");
    const exp = Number(JSON.parse(atob(base64)).exp);
    return Number.isFinite(exp) && exp * 1000 > nowMs + marginSeconds * 1000;
  } catch {
    return false;
  }
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

export type RefreshOutcome =
  | { status: "ok"; accessToken: string }
  /** The API rejected the refresh token (401): the stored session has been cleared. */
  | { status: "rejected" }
  /** No stored refresh token, a network error, an aborted request or a server error: the session is kept. */
  | { status: "failed" };

let refreshInFlight: Promise<RefreshOutcome> | null = null;
const announcedRejections = new WeakSet<RefreshOutcome>();

/**
 * The one place the app rotates its refresh token. Single-flight: concurrent callers (page-load
 * session restore and any request that got a 401) share one /auth/refresh call, so the same
 * refresh token is never sent twice — the backend treats a reused token as theft and revokes
 * every session in its family. Only an explicit 401 ends the stored session.
 */
export function refreshSession(): Promise<RefreshOutcome> {
  if (!refreshInFlight) {
    refreshInFlight = (async (): Promise<RefreshOutcome> => {
      const refreshToken = getStoredRefreshToken();
      if (!refreshToken) return { status: "failed" };
      try {
        const res = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (res.status === 401) {
          clearStoredSession();
          return { status: "rejected" };
        }
        if (!res.ok) return { status: "failed" };
        const data = (await res.json()) as { access_token: string; refresh_token: string };
        storeSessionTokens(data.access_token, data.refresh_token);
        return { status: "ok", accessToken: data.access_token };
      } catch {
        return { status: "failed" };
      }
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

/**
 * For API requests that got a 401: a new access token, or null. When the refresh token was
 * rejected, SESSION_EXPIRED_EVENT is dispatched once so the AuthProvider signs the user out.
 */
export async function refreshAccessToken(): Promise<string | null> {
  const outcome = await refreshSession();
  if (outcome.status === "rejected" && !announcedRejections.has(outcome)) {
    announcedRejections.add(outcome);
    if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
  return outcome.status === "ok" ? outcome.accessToken : null;
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
