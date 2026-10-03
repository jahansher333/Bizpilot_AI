import React from "react";
import Link from "next/link";
import { Logo } from "@/components/ui/logo";

/** Centered card on the app background, used by password recovery screens (design 04–05). */
export function AuthCardShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", display: "flex", flexDirection: "column" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "20px 32px" }}>
        <Link href="/" aria-label="BizPilot AI home" style={{ textDecoration: "none" }}>
          <Logo />
        </Link>
        <Link className="btn btn-ghost btn-sm" href="/login">
          Sign in
        </Link>
      </header>
      <main style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "32px 16px 64px" }}>
        <div className="card page-in" style={{ width: "100%", maxWidth: 440, padding: 32, display: "flex", flexDirection: "column", gap: 20, boxShadow: "var(--shadow-sm)" }}>
          {children}
        </div>
      </main>
    </div>
  );
}
