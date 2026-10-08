import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

import { AuthProvider } from "@/components/providers/auth-provider";
import { useAuth } from "@/hooks/use-auth";
import {
  SESSION_EXPIRED_EVENT,
  SESSION_HINT_KEY,
  authorizedFetch,
  clearStoredSession,
  getAccessToken,
  refreshAccessToken,
  refreshSession,
  storeSession,
} from "@/lib/api/http";

/**
 * Session restore on page load. The access token lives only in memory and the refresh token is an
 * HttpOnly cookie (SEC-P1 F3), so a page load exchanges the cookie for a new access token. Earlier
 * findings still hold (real-backend smoke test, 2026-10-07): navigating away while the profile
 * loads must not end the session, and a page-load refresh must never race a request's 401-refresh
 * (presenting the same rotating token twice makes the backend revoke the whole family).
 */
const fetchMock = vi.fn();

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const TOKENS = { access_token: "access-2", token_type: "bearer", expires_in: 900 };
const ME = { id: "u1", email: "owner@example.com", display_name: "Owner", status: "active" };
const ORGS = [{ id: "org-1", display_name: "Khan Traders", currency_code: "PKR", timezone: "Asia/Karachi", status: "active", created_at: "", role: "owner" }];

function refreshCalls() {
  return fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/auth/refresh"));
}

function Probe() {
  const { isLoading, user } = useAuth();
  return <div data-testid="state">{isLoading ? "loading" : user ? `signed-in:${user.email}` : "signed-out"}</div>;
}

beforeEach(() => {
  localStorage.clear();
  clearStoredSession();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  localStorage.setItem(SESSION_HINT_KEY, "1");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("single-flight refresh", () => {
  it("page-load restore and a request's 401 share ONE /auth/refresh call", async () => {
    let release!: (r: Response) => void;
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/refresh")) return new Promise<Response>((r) => (release = r));
      return Promise.resolve(json(200, {}));
    });

    const restore = refreshSession();
    const request = refreshAccessToken();
    await vi.waitFor(() => expect(refreshCalls()).toHaveLength(1));
    release(json(200, TOKENS));

    expect(await restore).toEqual({ status: "ok", accessToken: "access-2" });
    expect(await request).toBe("access-2");
    expect(refreshCalls()).toHaveLength(1);
    expect(refreshCalls()[0][1].credentials).toBe("include");
    expect(getAccessToken()).toBe("access-2");
  });

  it("serializes refreshes across tabs with a shared Web Lock", async () => {
    const order: string[] = [];
    const request = vi.fn(async (_name: string, fn: () => Promise<unknown>) => {
      order.push("lock");
      const result = await fn();
      order.push("unlock");
      return result;
    });
    vi.stubGlobal("navigator", { ...navigator, locks: { request } });
    fetchMock.mockImplementation(() => {
      order.push("refresh");
      return Promise.resolve(json(200, TOKENS));
    });

    expect(await refreshSession()).toEqual({ status: "ok", accessToken: "access-2" });
    expect(request).toHaveBeenCalledWith("bizpilot-session-refresh", expect.any(Function));
    expect(order).toEqual(["lock", "refresh", "unlock"]);
  });

  it("only a 401 from /auth/refresh ends the session", async () => {
    fetchMock.mockResolvedValueOnce(json(500, {}));
    expect(await refreshSession()).toEqual({ status: "failed" });
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBe("1");

    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    expect(await refreshSession()).toEqual({ status: "failed" });
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBe("1");

    fetchMock.mockResolvedValueOnce(json(401, {}));
    expect(await refreshSession()).toEqual({ status: "rejected" });
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBeNull();
  });

  it("announces an expired session once, even when several requests were rejected together", async () => {
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    // Every call is a 401: both requests fail, then the shared refresh is rejected.
    fetchMock.mockImplementation(() => Promise.resolve(json(401, {})));
    storeSession("expired");

    await Promise.all([authorizedFetch("http://api.test/a"), authorizedFetch("http://api.test/b")]);

    expect(refreshCalls()).toHaveLength(1);
    expect(expired).toHaveBeenCalledTimes(1);
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });
});

describe("AuthProvider session restore", () => {
  it("restores the session with one refresh, then loads the profile", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/refresh")) return Promise.resolve(json(200, TOKENS));
      if (url.endsWith("/api/auth/me")) return Promise.resolve(json(200, ME));
      if (url.endsWith("/api/organizations")) return Promise.resolve(json(200, ORGS));
      return Promise.resolve(json(404, {}));
    });
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-in:owner@example.com"));
    expect(refreshCalls()).toHaveLength(1);
    const me = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/auth/me"))!;
    expect(new Headers(me[1].headers).get("Authorization")).toBe("Bearer access-2");
  });

  it("does not call /auth/refresh for a browser that was never signed in", async () => {
    localStorage.removeItem(SESSION_HINT_KEY);
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("removes tokens an older version of the app left in localStorage", async () => {
    localStorage.setItem("bizpilot_access_token", "legacy-access");
    localStorage.setItem("bizpilot_refresh_token", "legacy-refresh");
    fetchMock.mockResolvedValue(json(401, {}));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(localStorage.getItem("bizpilot_access_token")).toBeNull();
    expect(localStorage.getItem("bizpilot_refresh_token")).toBeNull();
  });

  it("keeps the session when loading the profile is aborted by navigating away", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/refresh")) return Promise.resolve(json(200, TOKENS));
      return Promise.reject(new DOMException("The user aborted a request.", "AbortError"));
    });
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBe("1");
  });

  it("keeps the session when the network is down on page load", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBe("1");
  });

  it("clears the session when the API rejects the refresh cookie, without redirecting public pages", async () => {
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    fetchMock.mockResolvedValue(json(401, {}));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBeNull();
    expect(expired).not.toHaveBeenCalled();
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });
});
