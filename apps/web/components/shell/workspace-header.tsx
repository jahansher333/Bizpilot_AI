"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

interface WorkspaceHeaderProps {
  orgId: string;
  onOpenMobileMenu: () => void;
}

export function WorkspaceHeader({ orgId, onOpenMobileMenu }: WorkspaceHeaderProps) {
  const pathname = usePathname();
  const { activeOrg, activeRole, logout } = useAuth();

  // Generate breadcrumb info from current pathname
  const breadcrumbs = React.useMemo(() => {
    const defaultCrumb = { section: "Overview", page: "Dashboard" };
    if (!pathname) return defaultCrumb;

    if (pathname.includes("/orders")) {
      return { section: "Operations", page: "Orders" };
    }
    if (pathname.includes("/catalog")) {
      return { section: "Operations", page: "Products & Categories" };
    }
    if (pathname.includes("/inventory")) {
      return { section: "Operations", page: "Inventory" };
    }
    if (pathname.includes("/customers")) {
      return { section: "Operations", page: "Customers" };
    }
    if (pathname.includes("/payments")) {
      return { section: "Finance", page: "Payments" };
    }
    if (pathname.includes("/expenses")) {
      return { section: "Finance", page: "Expenses" };
    }
    if (pathname.includes("/assistant")) {
      return { section: "AI", page: "BizPilot Assistant" };
    }
    return defaultCrumb;
  }, [pathname]);

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur-xs sm:px-6">
      <div className="flex items-center gap-3">
        {/* Mobile Hamburger Toggle */}
        <button
          type="button"
          onClick={onOpenMobileMenu}
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 md:hidden"
          aria-label="Open navigation menu"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Semantic Breadcrumbs */}
        <nav aria-label="Breadcrumb" className="flex items-center text-sm">
          <ol className="flex items-center space-x-2">
            <li>
              <Link
                href={`/workspace/${orgId}`}
                className="text-slate-500 hover:text-slate-800 font-medium"
              >
                {activeOrg?.display_name || "Workspace"}
              </Link>
            </li>
            <li className="text-slate-400" aria-hidden="true">
              /
            </li>
            <li>
              <span className="text-slate-500">{breadcrumbs.section}</span>
            </li>
            <li className="text-slate-400" aria-hidden="true">
              /
            </li>
            <li>
              <span className="font-semibold text-slate-900" aria-current="page">
                {breadcrumbs.page}
              </span>
            </li>
          </ol>
        </nav>
      </div>

      {/* Right Header Actions */}
      <div className="flex items-center gap-3">
        {/* Role Pill */}
        <span className="hidden sm:inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800 capitalize border border-emerald-200">
          Role: {activeRole || "owner"}
        </span>

        {/* Switch Organization Link */}
        <Link
          href="/onboarding"
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-xs hover:bg-slate-50"
          title="Switch workspace"
        >
          Switch Org
        </Link>

        {/* Sign Out */}
        <button
          type="button"
          onClick={() => logout()}
          className="rounded-lg p-1.5 text-xs font-medium text-slate-500 hover:text-rose-600 sm:px-2.5 sm:py-1 sm:hover:bg-rose-50"
        >
          <span className="hidden sm:inline">Sign out</span>
          <svg
            className="h-4 w-4 sm:hidden"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
            />
          </svg>
        </button>
      </div>
    </header>
  );
}
