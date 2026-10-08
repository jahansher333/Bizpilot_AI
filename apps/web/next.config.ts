import type { NextConfig } from "next";

import { securityHeaders } from "./security-headers";

// Server-side proxy target for same-origin /api calls; set per environment.
const apiProxyTarget = (process.env.API_PROXY_TARGET || "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Self-contained server for the production Docker image (apps/web/Dockerfile).
  output: "standalone",
  // Trace from this app, not the repo root (which has its own package-lock.json), so server.js
  // sits at the top of .next/standalone both here and in the Docker build.
  outputFileTracingRoot: __dirname,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders({
          apiUrl: process.env.NEXT_PUBLIC_API_URL,
          isDev: process.env.NODE_ENV === "development",
        }),
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
