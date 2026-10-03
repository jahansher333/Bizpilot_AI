"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { Icon } from "@/components/ui/icon";
import { Logo, initials } from "@/components/ui/logo";
import { Skeleton } from "@/components/ui/states";
import { PendingInvitations } from "@/components/team/pending-invitations";

const ROLE_BADGE: Record<string, string> = { owner: "b-brand", manager: "b-info", staff: "b-neutral" };

/** Design canvas "07 · Workspace selector", plus pending invitations (FR-003). */
export function WorkspaceChooser() {
  const router = useRouter();
  const { user, organizations, isLoading, selectOrg, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) router.replace("/login");
  }, [isLoading, user, router]);

  const count = organizations.length;

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", display: "flex", flexDirection: "column" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 32px", gap: 16 }}>
        <Logo />
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {user && <span className="t-body-sm secondary hide-sm">{user.email}</span>}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              void logout().then(() => router.push("/login"));
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="page-in" style={{ flex: 1, width: "100%", maxWidth: 640, margin: "0 auto", padding: "48px 16px 64px", display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <h1 className="t-h1">Choose a workspace</h1>
          <p className="t-body secondary">
            {isLoading
              ? "Loading your workspaces…"
              : count === 0
                ? "You’re not part of a business workspace yet. Create one, or accept an invitation from your team."
                : `You have access to ${count} ${count === 1 ? "business" : "businesses"}. Your role decides what you can see and do in each.`}
          </p>
        </div>

        <PendingInvitations />

        {isLoading ? (
          <div className="card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12 }} aria-hidden="true">
            <Skeleton height={40} />
            <Skeleton height={40} />
          </div>
        ) : (
          count > 0 && (
            <ul className="card stagger" style={{ overflow: "hidden" }} aria-label="Your workspaces">
              {organizations.map((org, i) => (
                <li
                  key={org.id}
                  style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 18px", borderBottom: i < count - 1 ? "1px solid var(--border)" : 0, flexWrap: "wrap" }}
                >
                  <span
                    className="ws-mark"
                    style={
                      i === 0
                        ? { width: 40, height: 40, fontSize: 14 }
                        : { width: 40, height: 40, fontSize: 14, background: "var(--surface-sunken)", color: "var(--text-primary)", border: "1px solid var(--border)" }
                    }
                  >
                    {initials(org.display_name)}
                  </span>
                  <div style={{ flex: 1, minWidth: 180, display: "flex", flexDirection: "column", gap: 2 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      <span className="t-h4">{org.display_name}</span>
                      <span className={`badge square ${ROLE_BADGE[org.role] ?? "b-neutral"}`} style={{ textTransform: "capitalize" }}>
                        {org.role}
                      </span>
                    </div>
                    <span className="t-caption">
                      {org.currency_code} · {org.timezone}
                    </span>
                  </div>
                  <Link
                    className={`btn ${i === 0 ? "btn-primary" : "btn-secondary"}`}
                    href={`/workspace/${org.id}`}
                    onClick={() => selectOrg(org.id)}
                    aria-label={`Open workspace ${org.display_name}`}
                  >
                    Open workspace
                  </Link>
                </li>
              ))}
            </ul>
          )
        )}

        <Link
          className="card"
          href="/onboarding"
          style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 18px", borderStyle: "dashed", textDecoration: "none", color: "var(--text-primary)" }}
        >
          <span className="ws-mark" style={{ width: 40, height: 40, background: "var(--brand-tint)", color: "var(--brand-text)" }}>
            <Icon name="plus" size="lg" />
          </span>
          <span style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <span className="t-h4">Create new organization</span>
            <span className="t-caption">Start a separate workspace for another business</span>
          </span>
          <Icon name="chevronRight" style={{ color: "var(--text-muted)" }} />
        </Link>
      </main>
    </div>
  );
}
