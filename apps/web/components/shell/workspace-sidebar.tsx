"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

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
  ownerOnly?: boolean;
}

interface NavGroup {
  groupName: string;
  items: NavItem[];
}

export function WorkspaceSidebar({ orgId, onNavigate, className = "" }: WorkspaceSidebarProps) {
  const pathname = usePathname();
  const { user, activeOrg, activeRole, logout } = useAuth();

  const isStaff = activeRole?.toLowerCase() === "staff";
  const isOwner = activeRole?.toLowerCase() === "owner";

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
          name: "Team",
          href: `/workspace/${orgId}/team`,
          ownerOnly: true,
          icon: (props) => (
            <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          ),
        },
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
      className={`flex flex-col border-r border-surface-container-high/60 bg-surface-container-low shadow-[0_1px_8px_rgba(0,0,0,0.04)] ${className}`}
      aria-label="Main sidebar navigation"
    >
      {/* Brand Header */}
      <div className="p-space-md border-b border-surface-container-high/60">
        <Link
          href={`/workspace/${orgId}`}
          className="flex items-center gap-space-sm mb-space-sm group"
          onClick={onNavigate}
          aria-label="BizPilot workspace home"
        >
          <BizPilotLogo className="w-8 h-8 rounded-lg shadow-sm" size={32} />
          <span className="font-headline-sm text-headline-sm tracking-tight text-on-surface font-semibold">
            BizPilot AI
          </span>
          <span className="ml-auto font-data-badge text-data-badge px-1.5 py-0.5 rounded bg-surface-container-highest text-primary font-medium">
            ERP
          </span>
        </Link>

        {/* Workspace Quick Switcher */}
        <Link
          href="/onboarding"
          onClick={onNavigate}
          className="w-full flex items-center justify-between px-space-sm py-space-xs rounded-lg bg-surface-container-lowest shadow-[0_1px_2px_rgba(15,23,42,0.04)] hover:bg-surface-container-high transition-colors text-left"
        >
          <div className="flex flex-col min-w-0 pr-space-xs">
            <span className="font-body-sm text-body-sm font-medium text-on-surface truncate">
              {activeOrg?.display_name || "Workspace"}
            </span>
            <span className="font-label-md text-label-md text-on-surface-variant truncate">
              {activeOrg?.timezone || "Asia/Karachi"} · PK
            </span>
          </div>
          <span className="rounded bg-surface-container-high px-1.5 py-0.5 font-data-badge text-[10px] font-semibold capitalize text-primary">
            {activeRole || "owner"}
          </span>
        </Link>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 space-y-5 overflow-y-auto px-space-sm py-space-md" aria-label="Sidebar navigation">
        {navigationGroups.map((group) => {
          const visibleItems = group.items.filter((item) => {
            if (item.ownerManagerOnly && isStaff) return false;
            if (item.ownerOnly && !isOwner) return false;
            return true;
          });

          if (visibleItems.length === 0) return null;

          return (
            <div key={group.groupName} className="space-y-1">
              <p className="px-space-sm pt-space-xs pb-space-xxs font-label-caps text-label-caps uppercase text-outline tracking-wider text-[11px]">
                {group.groupName}
              </p>
              <ul className="space-y-1">
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
                        className={`flex items-center justify-between px-space-sm py-space-xs rounded-lg text-sm font-medium transition-all ${
                          isActive
                            ? "bg-primary-container text-on-primary font-semibold shadow-sm"
                            : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
                        }`}
                      >
                        <div className="flex items-center gap-space-sm">
                          <item.icon
                            className={`h-4 w-4 shrink-0 ${
                              isActive ? "text-on-primary" : "text-outline group-hover:text-on-surface"
                            }`}
                          />
                          <span className="font-body-md text-body-md">{item.name}</span>
                        </div>
                        {item.name === "BizPilot AI" && (
                          <span
                            className={`font-data-badge text-[10px] px-1.5 py-0.5 rounded-full ${
                              isActive
                                ? "bg-white/20 text-white"
                                : "bg-secondary-fixed text-on-secondary-fixed font-semibold"
                            }`}
                          >
                            v2.4
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* Operational Status & User Session Footer */}
      <div className="p-space-sm flex flex-col gap-space-xs border-t border-surface-container-high/60 bg-surface-container-low">
        <div className="flex items-center justify-between px-space-sm py-space-xxs text-label-md font-label-md">
          <span className="text-on-surface-variant flex items-center gap-1">
            <span>Enterprise Sync</span>
          </span>
          <div className="flex items-center gap-1.5 text-tertiary font-semibold">
            <span className="w-2 h-2 rounded-full bg-tertiary-fixed-dim inline-block animate-pulse" />
            <span>Operational</span>
          </div>
        </div>

        <div className="flex items-center justify-between p-space-xs rounded-lg bg-surface-container-lowest shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
          <div className="min-w-0 pr-2 pl-1">
            <p className="truncate font-body-sm text-body-sm font-semibold text-on-surface">
              {user?.display_name || user?.email || "Authenticated Operator"}
            </p>
            <p className="truncate font-label-md text-label-md text-on-surface-variant">{user?.email}</p>
          </div>
          <button
            type="button"
            onClick={() => logout()}
            title="Sign out"
            aria-label="Sign out"
            className="rounded-lg p-1.5 text-outline hover:bg-surface-container-high hover:text-error transition-colors"
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
