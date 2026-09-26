"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

interface WorkspaceSidebarProps {
  orgId: string;
  onNavigate?: () => void;
  className?: string;
}

interface NavItem {
  name: string;
  href: string;
  icon: (props: React.SVGProps<SVGSVGElement>) => React.ReactElement;
  ownerManagerOnly?: boolean;
}

interface NavGroup {
  groupName: string;
  items: NavItem[];
}

export function WorkspaceSidebar({ orgId, onNavigate, className = "" }: WorkspaceSidebarProps) {
  const pathname = usePathname();
  const { user, activeOrg, activeRole, logout } = useAuth();

  const isStaff = activeRole?.toLowerCase() === "staff";

  const navigationGroups: NavGroup[] = [
    {
      groupName: "Overview",
      items: [
        {
          name: "Dashboard",
          href: `/workspace/${orgId}`,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          ),
        },
      ],
    },
    {
      groupName: "Operations",
      items: [
        {
          name: "Orders",
          href: `/workspace/${orgId}/orders`,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
            </svg>
          ),
        },
        {
          name: "Products",
          href: `/workspace/${orgId}/catalog`,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          ),
        },
        {
          name: "Inventory",
          href: `/workspace/${orgId}/inventory`,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          ),
        },
        {
          name: "Customers",
          href: `/workspace/${orgId}/customers`,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          ),
        },
      ],
    },
    {
      groupName: "Finance",
      items: [
        {
          name: "Payments",
          href: `/workspace/${orgId}/payments`,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          ),
        },
        {
          name: "Expenses",
          href: `/workspace/${orgId}/expenses`,
          ownerManagerOnly: true,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ),
        },
      ],
    },
    {
      groupName: "AI Copilot",
      items: [
        {
          name: "BizPilot AI",
          href: `/workspace/${orgId}/assistant`,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          ),
        },
      ],
    },
    {
      groupName: "Management",
      items: [
        {
          name: "Workspaces",
          href: "/onboarding",
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          ),
        },
      ],
    },
  ];

  return (
    <aside
      className={`flex flex-col border-r border-slate-200 bg-white ${className}`}
      aria-label="Main sidebar navigation"
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
        <Link
          href={`/workspace/${orgId}`}
          className="flex items-center gap-2.5"
          onClick={onNavigate}
          aria-label="BizPilot workspace home"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-700 text-white font-bold text-sm shadow-sm">
            BP
          </div>
          <div>
            <span className="font-bold text-slate-900 tracking-tight text-base">BizPilot AI</span>
            <span className="ml-1.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
              P0
            </span>
          </div>
        </Link>
      </div>

      {/* Organization Badge Card */}
      <div className="border-b border-slate-100 bg-slate-50/60 px-5 py-3">
        <div className="flex items-center justify-between">
          <p className="truncate text-xs font-semibold text-slate-900">
            {activeOrg?.display_name || "Workspace"}
          </p>
          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold capitalize text-emerald-800">
            {activeRole || "owner"}
          </span>
        </div>
        <p className="mt-0.5 text-[11px] text-slate-500">
          PKR • {activeOrg?.timezone || "Asia/Karachi"}
        </p>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4" aria-label="Sidebar navigation">
        {navigationGroups.map((group) => {
          const visibleItems = group.items.filter((item) => {
            if (item.ownerManagerOnly && isStaff) return false;
            return true;
          });

          if (visibleItems.length === 0) return null;

          return (
            <div key={group.groupName} className="space-y-1">
              <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                {group.groupName}
              </p>
              <ul className="space-y-0.5">
                {visibleItems.map((item) => {
                  const isActive =
                    item.href === `/workspace/${orgId}`
                      ? pathname === `/workspace/${orgId}`
                      : pathname?.startsWith(item.href);

                  return (
                    <li key={item.name}>
                      <Link
                        href={item.href}
                        onClick={onNavigate}
                        aria-current={isActive ? "page" : undefined}
                        className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                          isActive
                            ? "bg-emerald-50 font-semibold text-emerald-800 shadow-xs"
                            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                        }`}
                      >
                        <item.icon
                          className={`h-4 w-4 shrink-0 ${
                            isActive ? "text-emerald-700" : "text-slate-400 group-hover:text-slate-600"
                          }`}
                        />
                        <span>{item.name}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* User Session Footer */}
      <div className="border-t border-slate-200 p-4">
        <div className="flex items-center justify-between">
          <div className="min-w-0 pr-2">
            <p className="truncate text-xs font-semibold text-slate-800">
              {user?.display_name || user?.email || "Authenticated User"}
            </p>
            <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
          </div>
          <button
            type="button"
            onClick={() => logout()}
            title="Sign out"
            aria-label="Sign out"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-rose-600"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}
