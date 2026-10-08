/**
 * Shared authenticated HTTP client (FIX-005, SEC-P1 F3).
 *
 * The access token lives only in memory (this module). The refresh token is an HttpOnly cookie
 * that page scripts cannot read; the browser sends it to /api/auth/refresh and /api/auth/logout.
 * On a 401 the client refreshes once (single-flight within the tab, serialized across tabs) and
 * retries the request with the new token. When the refresh cookie is rejected, the session is
 * cleared and SESSION_EXPIRED_EVENT is dispatched so the AuthProvider can sign the user out.
 */

/** Non-secret flag: this browser probably holds a refresh cookie, so a page load should refresh. */
export const SESSION_HINT_KEY = "bizpilot_session";
export const ACTIVE_ORG_KEY = "bizpilot_active_org_id";
/** Where tokens lived before SEC-P1 F3; removed on sight so no token stays readable by scripts. */
const LEGACY_TOKEN_KEYS = ["bizpilot_access_token", "bizpilot_refresh_token"] as const;
const REFRESH_LOCK = "bizpilot-session-refresh";

export const SESSION_TOKENS_EVENT = "bizpilot:session-tokens";
export const SESSION_EXPIRED_EVENT = "bizpilot:session-expired";

export interface SessionTokensDetail {
  accessToken: string;
}

let accessToken: string | null = null;

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

export function getAccessToken(): string | null {
  return accessToken;
}

export function hasSessionHint(): boolean {
  return storage()?.getItem(SESSION_HINT_KEY) === "1";
}

/** Drop tokens an older version of the app kept in localStorage. */
export function purgeLegacyTokenStorage(): void {
  const store = storage();
  for (const key of LEGACY_TOKEN_KEYS) store?.removeItem(key);
}

export function storeSession(nextAccessToken: string): void {
  accessToken = nextAccessToken;
  storage()?.setItem(SESSION_HINT_KEY, "1");
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<SessionTokensDetail>(SESSION_TOKENS_EVENT, { detail: { accessToken: nextAccessToken } })
    );
  }
}

export function clearStoredSession(): void {
  accessToken = null;
  const store = storage();
  store?.removeItem(SESSION_HINT_KEY);
  store?.removeItem(ACTIVE_ORG_KEY);
  purgeLegacyTokenStorage();
}

export type RefreshOutcome =
  | { status: "ok"; accessToken: string }
  /** The API rejected the refresh cookie (401): the session has been cleared. */
  | { status: "rejected" }
  /** A network error, an aborted request, a rate limit or a server error: the session is kept. */
  | { status: "failed" };

let refreshInFlight: Promise<RefreshOutcome> | null = null;
const announcedRejections = new WeakSet<RefreshOutcome>();

/**
 * Run `fn` while holding a lock shared by every tab of this origin. The refresh cookie is shared
 * by all tabs and rotates on every use; two tabs refreshing at once would present the same
 * cookie twice, which the API treats as theft and answers by revoking the whole session.
 */
async function withCrossTabLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = typeof navigator !== "undefined" && "locks" in navigator ? navigator.locks : undefined;
  return locks ? await locks.request(REFRESH_LOCK, () => fn()) : fn();
}

/**
 * The one place the app rotates the refresh cookie. Single-flight: concurrent callers in a tab
 * (page-load session restore and any request that got a 401) share one /auth/refresh call.
 * Only an explicit 401 ends the session.
 */
export function refreshSession(): Promise<RefreshOutcome> {
  if (!refreshInFlight) {
    refreshInFlight = withCrossTabLock(async (): Promise<RefreshOutcome> => {
      try {
        const res = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (res.status === 401) {
          clearStoredSession();
          return { status: "rejected" };
        }
        if (!res.ok) return { status: "failed" };
        const data = (await res.json()) as { access_token: string };
        storeSession(data.access_token);
        return { status: "ok", accessToken: data.access_token };
      } catch {
        return { status: "failed" };
      }
    }).finally(() => {
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
  let usedToken = token || getAccessToken();
  if (!usedToken && hasSessionHint()) {
    // Right after a page load the access token is not in memory yet: wait for the session-restore
    // refresh (single-flight, so this joins it) instead of sending the request unauthenticated.
    usedToken = await refreshAccessToken();
  }
  const response = await fetch(input, withAuthorization(init, usedToken));
  if (response.status !== 401 || !usedToken) {
    return response;
  }

  // Another request may already have refreshed; reuse that token instead of rotating again.
  const latest = getAccessToken();
  const nextToken = latest && latest !== usedToken ? latest : await refreshAccessToken();
  if (!nextToken) {
    return response;
  }
  return fetch(input, withAuthorization(init, nextToken));
}
