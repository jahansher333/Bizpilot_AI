"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { WorkspaceSidebar } from "@/components/shell/workspace-sidebar";
import { WorkspaceHeader } from "@/components/shell/workspace-header";

interface WorkspaceLayoutProps {
  orgId: string;
  children: React.ReactNode;
}

export function WorkspaceLayout({ orgId, children }: WorkspaceLayoutProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const router = useRouter();
  const { isLoading, user, organizations } = useAuth();

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

  // Close mobile menu on Escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isMobileMenuOpen) {
        setIsMobileMenuOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMobileMenuOpen]);

  return (
    <div className="flex min-h-screen bg-surface font-body-md text-on-surface antialiased">
      {/* Desktop Sidebar */}
      <WorkspaceSidebar
        orgId={orgId}
        className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 z-20"
      />

      {/* Mobile Drawer Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-50 flex md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation drawer"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={() => setIsMobileMenuOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer Content */}
          <div className="relative flex w-full max-w-xs flex-1 flex-col bg-surface-container-low shadow-xl">
            <div className="absolute right-0 top-0 -mr-12 pt-4">
              <button
                type="button"
                className="ml-1 flex h-10 w-10 items-center justify-center rounded-full text-white hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white"
                onClick={() => setIsMobileMenuOpen(false)}
                aria-label="Close navigation menu"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <WorkspaceSidebar
              orgId={orgId}
              onNavigate={() => setIsMobileMenuOpen(false)}
              className="h-full border-r-0"
            />
          </div>
        </div>
      )}

      {/* Main Workspace Column */}
      <div className="flex flex-1 flex-col md:pl-64">
        <WorkspaceHeader
          orgId={orgId}
          onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
        />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
