import type { NextConfig } from "next";

// Server-side proxy target for same-origin /api calls; set per environment.
const apiProxyTarget = (process.env.API_PROXY_TARGET || "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Self-contained server for the production Docker image (apps/web/Dockerfile).
  output: "standalone",
  // Trace from this app, not the repo root (which has its own package-lock.json), so server.js
  // sits at the top of .next/standalone both here and in the Docker build.
  outputFileTracingRoot: __dirname,
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
