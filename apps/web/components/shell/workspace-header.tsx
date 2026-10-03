"use client";

import React, { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useOrgRole } from "@/hooks/use-org-role";
import { useDismiss } from "@/hooks/use-dismiss";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";
import { routeInfo } from "@/components/shell/nav-config";

interface WorkspaceHeaderProps {
  orgId: string;
  onOpenMobileMenu: () => void;
}

/** Design canvas "07 · Top header": breadcrumb, quick-create menu and account avatar. */
export function WorkspaceHeader({ orgId, onOpenMobileMenu }: WorkspaceHeaderProps) {
  const pathname = usePathname();
  const { user, organizations } = useAuth();
  const role = useOrgRole(orgId);
  const org = organizations.find((o) => o.id === orgId);
  const { section, page } = routeInfo(pathname, orgId);
  const ownerOrManager = role === "owner" || role === "manager";
  const base = `/workspace/${orgId}`;

  const [createOpen, setCreateOpen] = useState(false);
  const createRef = useRef<HTMLDivElement>(null);
  const createButtonRef = useRef<HTMLButtonElement>(null);
  const closeCreate = useCallback(() => setCreateOpen(false), []);
  useDismiss(createOpen, createRef, closeCreate, createButtonRef);

  const quickCreate = [
    { label: "New order", href: `${base}/orders`, icon: "orders" as const, show: true },
    { label: "Add product", href: `${base}/catalog`, icon: "products" as const, show: ownerOrManager },
    { label: "Add customer", href: `${base}/customers`, icon: "userPlus" as const, show: true },
    { label: "Record payment", href: `${base}/payments`, icon: "payments" as const, show: true },
    { label: "Record expense", href: `${base}/expenses`, icon: "expenses" as const, show: ownerOrManager },
  ].filter((item) => item.show);

  return (
    <header className="tb">
      <button type="button" className="btn btn-ghost icon-btn tb-menu" aria-label="Open navigation menu" onClick={onOpenMobileMenu}>
        <Icon name="menu" size="lg" />
      </button>

      <nav className="crumb" aria-label="Breadcrumb" style={{ flex: 1 }}>
        <Link href={base} className="hide-sm">
          {org?.display_name ?? "Workspace"}
        </Link>
        <Icon name="chevronRight" size="sm" className="hide-sm" />
        <span className="hide-sm">{section}</span>
        <Icon name="chevronRight" size="sm" className="hide-sm" />
        <span className="here" aria-current="page">
          {page}
        </span>
      </nav>

      <div ref={createRef} style={{ position: "relative" }}>
        <button
          ref={createButtonRef}
          type="button"
          className="btn btn-primary btn-sm"
          aria-haspopup="menu"
          aria-expanded={createOpen}
          onClick={() => setCreateOpen((v) => !v)}
        >
          <Icon name="plus" />
          <span className="hide-sm">Create</span>
          <Icon name="chevronDown" size="sm" className="hide-sm" style={{ opacity: 0.8 }} />
          <span className="sr-only">Quick create menu</span>
        </button>
        {createOpen && (
          <div className="menu" role="menu" aria-label="Quick create" style={{ position: "absolute", right: 0, top: "calc(100% + 8px)", zIndex: 30 }}>
            <div className="menu-label">Quick create</div>
            {quickCreate.map((item) => (
              <Link key={item.label} className="menu-item" role="menuitem" href={item.href} onClick={closeCreate}>
                <Icon name={item.icon} />
                {item.label}
              </Link>
            ))}
          </div>
        )}
      </div>

      <span className="av" title={user?.display_name ?? undefined} aria-hidden="true">
        {initials(user?.display_name || user?.email)}
      </span>
    </header>
  );
}
