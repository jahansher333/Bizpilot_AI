"use client";

import React, { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useOrgRole } from "@/hooks/use-org-role";
import { useDismiss } from "@/hooks/use-dismiss";
import { Icon } from "@/components/ui/icon";
import { Logo, initials } from "@/components/ui/logo";
import { buildNavGroups, routeInfo } from "@/components/shell/nav-config";

interface WorkspaceSidebarProps {
  orgId: string;
  onNavigate?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  className?: string;
}

const ROLE_LABEL = { owner: "Owner", manager: "Manager", staff: "Staff" } as const;

/** Design canvas "07 · Sidebar": grouped navigation, workspace switcher and account menu. */
export function WorkspaceSidebar({ orgId, onNavigate, collapsed = false, onToggleCollapse, className = "" }: WorkspaceSidebarProps) {
  const pathname = usePathname();
  const { user, organizations, logout } = useAuth();
  const role = useOrgRole(orgId);
  const org = organizations.find((o) => o.id === orgId);
  const activeKey = routeInfo(pathname, orgId).key;
  const groups = buildNavGroups(orgId, role);

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  useDismiss(menuOpen, menuRef, closeMenu, menuButtonRef);

  const displayName = user?.display_name || user?.email || "Signed in";

  return (
    <nav className={`sb ${collapsed ? "collapsed" : ""} ${className}`.trim()} aria-label="Primary">
      <div className="sb-head" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "4px 4px 12px 6px" }}>
        <Link href={`/workspace/${orgId}`} aria-label="BizPilot AI home" onClick={onNavigate} style={{ textDecoration: "none" }}>
          <Logo showText={!collapsed} />
        </Link>
        {onToggleCollapse && (
          <button
            type="button"
            className="btn btn-ghost btn-sm icon-btn"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={onToggleCollapse}
          >
            <Icon name="panel" />
          </button>
        )}
      </div>

      <Link
        href="/workspaces"
        className="ws"
        onClick={onNavigate}
        aria-label={`Switch workspace: ${org?.display_name ?? "Workspace"}, ${ROLE_LABEL[role]}`}
        style={{ textDecoration: "none" }}
      >
        <span className="ws-mark">{initials(org?.display_name)}</span>
        <span className="ws-meta" style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
          <span style={{ font: "600 13.5px/18px var(--font)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {org?.display_name ?? "Workspace"}
          </span>
          <span style={{ font: "400 12px/16px var(--font)", color: "var(--text-muted)" }}>{ROLE_LABEL[role]}</span>
        </span>
        <Icon name="updown" className="chev-ws" style={{ color: "var(--text-muted)" }} />
      </Link>

      {groups.map((group) => (
        <React.Fragment key={group.label}>
          <div className="grp">{group.label}</div>
          {group.items.map((item) => {
            const active = item.key === activeKey;
            return (
              <Link
                key={item.key}
                href={item.href}
                className={`nav-item${active ? " is-active" : ""}`}
                aria-current={active ? "page" : undefined}
                onClick={onNavigate}
                title={collapsed ? item.label : undefined}
              >
                <Icon name={item.icon} />
                <span className="lbl">{item.label}</span>
                {item.badge && (
                  <span className="trail lbl badge b-brand square" style={{ height: 18, padding: "0 5px", fontSize: 10.5 }}>
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </React.Fragment>
      ))}

      <div style={{ flex: 1, minHeight: 24 }} />

      <div ref={menuRef} style={{ position: "relative", marginTop: 6, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
        {menuOpen && (
          <div className="menu" role="menu" aria-label="Account" style={{ position: "absolute", left: 0, right: 0, bottom: "calc(100% + 6px)", minWidth: 0, zIndex: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px 10px" }}>
              <span className="av lg">{initials(displayName)}</span>
              <div style={{ minWidth: 0 }}>
                <div style={{ font: "600 13.5px/18px var(--font)" }}>{user?.display_name}</div>
                <div style={{ font: "400 12px/16px var(--font)", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.email}</div>
              </div>
            </div>
            <div className="menu-sep" />
            <Link className="menu-item" role="menuitem" href={`/workspace/${orgId}/settings`} onClick={onNavigate}>
              <Icon name="settings" />
              Settings
            </Link>
            <Link className="menu-item" role="menuitem" href="/workspaces" onClick={onNavigate}>
              <Icon name="updown" />
              Switch workspace
            </Link>
            <div className="menu-sep" />
            <button
              type="button"
              className="menu-item"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                void logout();
              }}
            >
              <Icon name="signOut" />
              Sign out
            </button>
          </div>
        )}
        <button
          ref={menuButtonRef}
          type="button"
          className="nav-item"
          style={{ height: 44 }}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label={`Account menu for ${displayName}`}
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span className="av">{initials(displayName)}</span>
          <span className="lbl" style={{ display: "flex", flexDirection: "column", minWidth: 0, lineHeight: "16px" }}>
            <span style={{ color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.display_name || "Account"}</span>
            <span style={{ fontSize: 12, fontWeight: 400, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.email}</span>
          </span>
          <Icon name="more" className="trail lbl" style={{ color: "var(--text-muted)" }} />
        </button>
      </div>
    </nav>
  );
}
