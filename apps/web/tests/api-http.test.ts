import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  SESSION_EXPIRED_EVENT,
  SESSION_HINT_KEY,
  SESSION_TOKENS_EVENT,
  authorizedFetch,
  clearStoredSession,
  getAccessToken,
  storeSession,
} from "@/lib/api/http";
import { loginUser, logoutUser } from "@/lib/api/auth";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function authHeader(call: unknown[]): string | null {
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers).get("Authorization");
}

describe("authorizedFetch (FIX-005, SEC-P1 F3)", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    clearStoredSession();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the in-memory access token", async () => {
    storeSession("access-1");
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const res = await authorizedFetch("http://api.test/api/thing", { method: "GET" });

    expect(res.status).toBe(200);
    expect(authHeader(fetchMock.mock.calls[0])).toBe("Bearer access-1");
  });

  it("refreshes once on 401 with the cookie, keeps the new token in memory, notifies, and retries", async () => {
    storeSession("expired");
    const tokensEvent = vi.fn();
    window.addEventListener(SESSION_TOKENS_EVENT, tokensEvent);

    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "UNAUTHORIZED" } }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "access-2", token_type: "bearer", expires_in: 900 }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const res = await authorizedFetch("http://api.test/api/thing", {
      method: "POST",
      body: JSON.stringify({ a: 1 }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toContain("/api/auth/refresh");
    // The refresh token is the HttpOnly cookie: no body, credentials included.
    expect(fetchMock.mock.calls[1][1].body).toBeUndefined();
    expect(fetchMock.mock.calls[1][1].credentials).toBe("include");
    expect(authHeader(fetchMock.mock.calls[2])).toBe("Bearer access-2");
    expect(fetchMock.mock.calls[2][1].body).toBe(JSON.stringify({ a: 1 }));
    expect(getAccessToken()).toBe("access-2");
    expect(tokensEvent).toHaveBeenCalledTimes(1);
    window.removeEventListener(SESSION_TOKENS_EVENT, tokensEvent);
  });

  it("never writes a token to browser storage", async () => {
    storeSession("expired");
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "access-2" }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await authorizedFetch("http://api.test/api/thing");

    const stored = [...Array(localStorage.length).keys()].map((i) => localStorage.getItem(localStorage.key(i)!));
    expect(stored.join(" ")).not.toMatch(/access-|expired/);
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBe("1");
  });

  it("shares a single refresh between concurrent 401 responses", async () => {
    storeSession("expired");

    let resolveRefresh: (value: Response) => void = () => {};
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes("/api/auth/refresh")) {
        return new Promise<Response>((resolve) => {
          resolveRefresh = resolve;
        });
      }
      const auth = new Headers(init?.headers).get("Authorization");
      return Promise.resolve(
        auth === "Bearer access-2" ? jsonResponse(200, { ok: true }) : jsonResponse(401, {})
      );
    });

    const pending = Promise.all([
      authorizedFetch("http://api.test/api/a"),
      authorizedFetch("http://api.test/api/b"),
    ]);
    await vi.waitFor(() => {
      expect(fetchMock.mock.calls.filter((c) => String(c[0]).includes("/refresh"))).toHaveLength(1);
    });
    resolveRefresh(jsonResponse(200, { access_token: "access-2" }));

    const [a, b] = await pending;
    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(fetchMock.mock.calls.filter((c) => String(c[0]).includes("/refresh"))).toHaveLength(1);
  });

  it("uses a token refreshed elsewhere instead of rotating again", async () => {
    storeSession("already-new");
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const res = await authorizedFetch("http://api.test/api/thing", {}, "stale-from-react-state");

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(authHeader(fetchMock.mock.calls[0])).toBe("Bearer stale-from-react-state");
    expect(authHeader(fetchMock.mock.calls[1])).toBe("Bearer already-new");
  });

  it("clears the session and signals expiry when the refresh cookie is rejected", async () => {
    storeSession("expired");
    localStorage.setItem("bizpilot_active_org_id", "org-1");
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(401, {}));

    const res = await authorizedFetch("http://api.test/api/thing");

    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(getAccessToken()).toBeNull();
    expect(localStorage.getItem(SESSION_HINT_KEY)).toBeNull();
    expect(localStorage.getItem("bizpilot_active_org_id")).toBeNull();
    expect(expired).toHaveBeenCalledTimes(1);
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });

  it("keeps the session when the refresh endpoint is temporarily unavailable or rate limited", async () => {
    for (const status of [503, 429]) {
      storeSession("expired");
      fetchMock
        .mockResolvedValueOnce(jsonResponse(401, {}))
        .mockResolvedValueOnce(jsonResponse(status, {}));

      const res = await authorizedFetch("http://api.test/api/thing");

      expect(res.status).toBe(401);
      expect(localStorage.getItem(SESSION_HINT_KEY)).toBe("1");
    }
  });

  it("does not refresh when a request had no token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(401, {}));

    const res = await authorizedFetch("http://api.test/api/thing");

    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(authHeader(fetchMock.mock.calls[0])).toBeNull();
  });

  it("does not refresh on a failed login, and login sends credentials so the cookie is stored", async () => {
    storeSession("some-old-token");
    fetchMock.mockResolvedValueOnce(
      jsonResponse(401, { error: { message: "Invalid email or password" } })
    );

    await expect(loginUser({ email: "a@b.test", password: "wrong-password-1" })).rejects.toThrow(
      "Invalid email or password"
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(authHeader(fetchMock.mock.calls[0])).toBeNull();
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
  });

  it("logs out with the cookie only: no token in the body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { status: "success", message: "Logged out successfully" }));

    await logoutUser();

    expect(fetchMock.mock.calls[0][0]).toContain("/api/auth/logout");
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
    expect(fetchMock.mock.calls[0][1].body).toBeUndefined();
  });
});
