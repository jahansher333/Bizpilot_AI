"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { WorkspaceSidebar } from "@/components/shell/workspace-sidebar";
import { WorkspaceHeader } from "@/components/shell/workspace-header";
import { Icon } from "@/components/ui/icon";

interface WorkspaceLayoutProps {
  orgId: string;
  children: React.ReactNode;
}

const COLLAPSE_KEY = "bizpilot_sidebar_collapsed";

/** Design canvas app shell: sticky sidebar (248 / 68 collapsed), top header, drawer under 760px. */
export function WorkspaceLayout({ orgId, children }: WorkspaceLayoutProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const { isLoading, user, organizations } = useAuth();
  const drawerCloseRef = useRef<HTMLButtonElement>(null);

  // Route guard: signed-out users go to login; workspaces without an active membership
  // go to onboarding. The backend still rejects every unauthorized request.
  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      router.replace("/login");
    } else if (!organizations.some((org) => org.id === orgId)) {
      router.replace("/onboarding");
    }
  }, [isLoading, user, organizations, orgId, router]);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      // Storage unavailable: keep the expanded default.
    }
  }, []);

  function toggleCollapse() {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // Preference is a convenience only.
      }
      return next;
    });
  }

  // Close the drawer on navigation.
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  // Close mobile drawer on Escape and move focus into it when it opens.
  useEffect(() => {
    if (!isMobileMenuOpen) return;
    drawerCloseRef.current?.focus();
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setIsMobileMenuOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMobileMenuOpen]);

  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      <WorkspaceSidebar orgId={orgId} collapsed={collapsed} onToggleCollapse={toggleCollapse} className="sb-sticky" />

      {isMobileMenuOpen && (
        <div
          className="drawer-wrap"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation drawer"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setIsMobileMenuOpen(false);
          }}
        >
          <WorkspaceSidebar orgId={orgId} onNavigate={() => setIsMobileMenuOpen(false)} />
          <div style={{ padding: 12 }}>
            <button
              ref={drawerCloseRef}
              type="button"
              className="btn btn-secondary icon-btn"
              onClick={() => setIsMobileMenuOpen(false)}
              aria-label="Close navigation menu"
            >
              <Icon name="close" />
            </button>
          </div>
        </div>
      )}

      <div className="shell-main">
        <WorkspaceHeader orgId={orgId} onOpenMobileMenu={() => setIsMobileMenuOpen(true)} />
        <main id="main-content" tabIndex={-1} style={{ flex: 1, minWidth: 0, outline: "none" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
