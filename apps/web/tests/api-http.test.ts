import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  SESSION_EXPIRED_EVENT,
  SESSION_TOKENS_EVENT,
  authorizedFetch,
} from "@/lib/api/http";
import { loginUser } from "@/lib/api/auth";

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

describe("authorizedFetch (FIX-005)", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the stored access token", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "access-1");
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const res = await authorizedFetch("http://api.test/api/thing", { method: "GET" });

    expect(res.status).toBe(200);
    expect(authHeader(fetchMock.mock.calls[0])).toBe("Bearer access-1");
  });

  it("refreshes once on 401, stores rotated tokens, notifies, and retries", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "expired");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-1");
    const tokensEvent = vi.fn();
    window.addEventListener(SESSION_TOKENS_EVENT, tokensEvent);

    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: "UNAUTHORIZED" } }))
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "access-2", refresh_token: "refresh-2", expires_in: 900 })
      )
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const res = await authorizedFetch("http://api.test/api/thing", {
      method: "POST",
      body: JSON.stringify({ a: 1 }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toContain("/api/auth/refresh");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ refresh_token: "refresh-1" });
    expect(authHeader(fetchMock.mock.calls[2])).toBe("Bearer access-2");
    expect(fetchMock.mock.calls[2][1].body).toBe(JSON.stringify({ a: 1 }));
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe("access-2");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-2");
    expect(tokensEvent).toHaveBeenCalledTimes(1);
    window.removeEventListener(SESSION_TOKENS_EVENT, tokensEvent);
  });

  it("shares a single refresh between concurrent 401 responses", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "expired");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-1");

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
    resolveRefresh(jsonResponse(200, { access_token: "access-2", refresh_token: "refresh-2" }));

    const [a, b] = await pending;
    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(fetchMock.mock.calls.filter((c) => String(c[0]).includes("/refresh"))).toHaveLength(1);
  });

  it("uses a token refreshed elsewhere instead of rotating again", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "already-new");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-2");
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const res = await authorizedFetch("http://api.test/api/thing", {}, "stale-from-react-state");

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(authHeader(fetchMock.mock.calls[0])).toBe("Bearer stale-from-react-state");
    expect(authHeader(fetchMock.mock.calls[1])).toBe("Bearer already-new");
  });

  it("clears the session and signals expiry when the refresh token is rejected", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "expired");
    localStorage.setItem(REFRESH_TOKEN_KEY, "revoked");
    const expired = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(401, {}));

    const res = await authorizedFetch("http://api.test/api/thing");

    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
    expect(expired).toHaveBeenCalledTimes(1);
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });

  it("keeps the session when the refresh endpoint is temporarily unavailable", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "expired");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-1");
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, {}))
      .mockResolvedValueOnce(jsonResponse(503, {}));

    const res = await authorizedFetch("http://api.test/api/thing");

    expect(res.status).toBe(401);
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("refresh-1");
  });

  it("does not refresh when a request had no token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(401, {}));

    const res = await authorizedFetch("http://api.test/api/thing");

    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(authHeader(fetchMock.mock.calls[0])).toBeNull();
  });

  it("does not refresh on a failed login", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "some-old-token");
    localStorage.setItem(REFRESH_TOKEN_KEY, "refresh-1");
    fetchMock.mockResolvedValueOnce(
      jsonResponse(401, { error: { message: "Invalid email or password" } })
    );

    await expect(loginUser({ email: "a@b.test", password: "wrong-password-1" })).rejects.toThrow(
      "Invalid email or password"
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(authHeader(fetchMock.mock.calls[0])).toBeNull();
  });
});
