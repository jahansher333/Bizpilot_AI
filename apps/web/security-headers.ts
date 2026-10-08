/**
 * Security response headers for every page (SEC-P1 F3).
 *
 * The CSP follows the Next.js "without nonces" setup: 'unsafe-inline' scripts are still allowed
 * because Next inlines its RSC payload and the app inlines the pre-paint theme script. A nonce CSP
 * would force every page to render dynamically. The policy still blocks scripts from other origins,
 * plugins, framing, <base> hijacking, form posts elsewhere and, through connect-src, sending data to
 * any host except this app and the BizPilot API.
 */

export interface SecurityHeaderOptions {
  /** Browser-visible API base URL (NEXT_PUBLIC_API_URL). */
  apiUrl?: string;
  /** True for `next dev`, where React needs eval for its debugging overlays. */
  isDev?: boolean;
}

export interface HeaderEntry {
  key: string;
  value: string;
}

function apiOrigin(apiUrl: string | undefined): URL | null {
  if (!apiUrl) return null;
  try {
    return new URL(apiUrl);
  } catch {
    return null;
  }
}

export function contentSecurityPolicy({ apiUrl, isDev = false }: SecurityHeaderOptions): string {
  const api = apiOrigin(apiUrl);
  const connect = ["'self'", ...(api ? [api.origin] : [])];
  const directives = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    `connect-src ${connect.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  // Only when the API itself is https: on an http API (local development and e2e) the upgrade
  // would rewrite API calls to https and break them.
  if (api?.protocol === "https:") directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}

export function securityHeaders(options: SecurityHeaderOptions): HeaderEntry[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(options) },
    // Keeps the ?token= in password-reset links out of Referer headers.
    { key: "Referrer-Policy", value: "no-referrer" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    // Browsers ignore HSTS on plain http, so this is safe for local runs.
    { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  ];
}
