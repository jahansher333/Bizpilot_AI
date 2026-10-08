import { describe, expect, it } from "vitest";

import { contentSecurityPolicy, securityHeaders } from "@/security-headers";

function directives(csp: string): Map<string, string> {
  return new Map(
    csp.split(";").map((part) => {
      const [name, ...values] = part.trim().split(/\s+/);
      return [name, values.join(" ")] as [string, string];
    })
  );
}

describe("security headers (SEC-P1 F3)", () => {
  it("restricts every fetch target to this app and the API origin", () => {
    const csp = directives(contentSecurityPolicy({ apiUrl: "https://api.bizpilot.pk/some/path" }));
    expect(csp.get("connect-src")).toBe("'self' https://api.bizpilot.pk");
    expect(csp.get("default-src")).toBe("'self'");
    expect(csp.get("object-src")).toBe("'none'");
    expect(csp.get("frame-ancestors")).toBe("'none'");
    expect(csp.get("base-uri")).toBe("'self'");
    expect(csp.get("form-action")).toBe("'self'");
    expect(csp.has("upgrade-insecure-requests")).toBe(true);
  });

  it("never allows eval in production and no third-party script origins", () => {
    const script = directives(contentSecurityPolicy({ apiUrl: "https://api.bizpilot.pk" })).get("script-src");
    expect(script).toBe("'self' 'unsafe-inline'");
    expect(script).not.toContain("unsafe-eval");
    expect(script).not.toMatch(/https?:|\*/);
  });

  it("allows eval only for the development server", () => {
    expect(directives(contentSecurityPolicy({ isDev: true })).get("script-src")).toContain("'unsafe-eval'");
  });

  it("does not upgrade requests when the API is plain http (local runs)", () => {
    const csp = directives(contentSecurityPolicy({ apiUrl: "http://localhost:8000" }));
    expect(csp.get("connect-src")).toBe("'self' http://localhost:8000");
    expect(csp.has("upgrade-insecure-requests")).toBe(false);
  });

  it("falls back to same-origin only when the API URL is missing or invalid", () => {
    expect(directives(contentSecurityPolicy({})).get("connect-src")).toBe("'self'");
    expect(directives(contentSecurityPolicy({ apiUrl: "not a url" })).get("connect-src")).toBe("'self'");
  });

  it("sends the hardening headers alongside the CSP", () => {
    const headers = Object.fromEntries(securityHeaders({ apiUrl: "https://api.bizpilot.pk" }).map((h) => [h.key, h.value]));
    expect(headers["Referrer-Policy"]).toBe("no-referrer");
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Strict-Transport-Security"]).toMatch(/max-age=\d+/);
    expect(headers["Permissions-Policy"]).toContain("camera=()");
  });
});
