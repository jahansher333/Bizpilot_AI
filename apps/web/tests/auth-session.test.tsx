import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

import { AuthProvider } from "@/components/providers/auth-provider";
import { useAuth } from "@/hooks/use-auth";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, SESSION_EXPIRED_EVENT, authorizedFetch, isAccessTokenFresh, refreshAccessToken, refreshSession } from "@/lib/api/http";

/**
 * Session restore on page load (found by the real-backend smoke test, 2026-10-07):
 * navigating away while the profile loaded wiped the stored session, and a page-load refresh
 * could race a request's 401-refresh with the same refresh token (the backend then revokes
 * every session in the family).
 */
const fetchMock = vi.fn();

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const TOKENS = { access_token: "access-2", refresh_token: "refresh-2", token_type: "bearer", expires_in: 900 };
const ME = { id: "u1", email: "owner@example.com", display_name: "Owner", status: "active" };
const ORGS = [{ id: "org-1", display_name: "Khan Traders", currency_code: "PKR", timezone: "Asia/Karachi", status: "active", created_at: "", role: "owner" }];

/** An unsigned JWT-shaped token; the client only reads `exp`. */
function jwt(expSecondsFromNow: number): string {
  const enc = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${enc({ alg: "HS256" })}.${enc({ sub: "u1", exp: Math.floor(Date.now() / 1000) + expSecondsFromNow })}.sig`;
}

function refreshCalls() {
  return fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/auth/refresh"));
}

function Probe() {
  const { isLoading, user } = useAuth();
  return <div data-testid="state">{isLoading ? "loading" : user ? `signed-in:${user.email}` : "signed-out"}</div>;
}

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  localStorage.setItem(ACCESS_TOKEN_KEY, "access-1");
  localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-1");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("single-flight refresh", () => {
  it("page-load restore and a request's 401 share ONE /auth/refresh call", async () => {
    let release!: (r: Response) => void;
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/refresh")) return new Promise<Response>((r) => (release = r));
      if (url.endsWith("/api/things")) return Promise.resolve(json(401, {}));
      return Promise.resolve(json(200, {}));
    });

    const restore = refreshSession();
    const request = refreshAccessToken();
    release(json(200, TOKENS));

    expect(await restore).toEqual({ status: "ok", accessToken: "access-2" });
    expect(await request).toBe("access-2");
    expect(refreshCalls()).toHaveLength(1);
    expect(JSON.parse(refreshCalls()[0][1].body)).toEqual({ refresh_token: "refresh-1" });
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-2");
  });

  it("only a 401 from /auth/refresh clears the stored session", async () => {
    fetchMock.mockResolvedValueOnce(json(500, {}));
    expect(await refreshSession()).toEqual({ status: "failed" });
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-1");

    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    expect(await refreshSession()).toEqual({ status: "failed" });
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-1");

    fetchMock.mockResolvedValueOnce(json(401, {}));
    expect(await refreshSession()).toEqual({ status: "rejected" });
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
  });

  it("announces an expired session once, even when several requests were rejected together", async () => {
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    fetchMock.mockImplementation((url: string) => Promise.resolve(url.endsWith("/api/auth/refresh") ? json(401, {}) : json(401, {})));

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
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-2");
  });

  it("keeps the stored session when loading the profile is aborted by navigating away", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/refresh")) return Promise.resolve(json(200, TOKENS));
      return Promise.reject(new DOMException("The user aborted a request.", "AbortError"));
    });
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe("access-2");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-2");
  });

  it("keeps the stored session when the network is down on page load", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-1");
  });

  it("clears the session when the API rejects the refresh token, without redirecting public pages", async () => {
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    fetchMock.mockResolvedValue(json(401, {}));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-out"));
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
    expect(expired).not.toHaveBeenCalled();
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });
});

describe("no refresh-token rotation while the access token is still valid", () => {
  it("reads only the exp claim, with a safety margin", () => {
    expect(isAccessTokenFresh(jwt(600))).toBe(true);
    expect(isAccessTokenFresh(jwt(10))).toBe(false);
    expect(isAccessTokenFresh(jwt(-60))).toBe(false);
    expect(isAccessTokenFresh("not-a-jwt")).toBe(false);
    expect(isAccessTokenFresh(null)).toBe(false);
  });

  it("restores the session on page load without calling /auth/refresh", async () => {
    const access = jwt(600);
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/me")) return Promise.resolve(json(200, ME));
      if (url.endsWith("/api/organizations")) return Promise.resolve(json(200, ORGS));
      return Promise.resolve(json(500, {}));
    });
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-in:owner@example.com"));
    expect(refreshCalls()).toHaveLength(0);
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization")).toBe(`Bearer ${access}`);
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-1");
  });

  it("refreshes once when the stored access token has expired", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, jwt(-60));
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/refresh")) return Promise.resolve(json(200, TOKENS));
      if (url.endsWith("/api/auth/me")) return Promise.resolve(json(200, ME));
      if (url.endsWith("/api/organizations")) return Promise.resolve(json(200, ORGS));
      return Promise.resolve(json(404, {}));
    });
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("signed-in"));
    expect(refreshCalls()).toHaveLength(1);
  });
});
