import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider, useAuth } from "@/components/providers/auth-provider";
import { WorkspaceSidebar } from "@/components/shell/workspace-sidebar";
import { WorkspaceHeader } from "@/components/shell/workspace-header";
import { WorkspaceLayout } from "@/components/shell/workspace-layout";

import * as authHooks from "@/hooks/use-auth";

// Mock next/navigation
let currentPathname = "/workspace/org-123/orders";
const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => currentPathname,
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
  }),
}));

describe("Shared Application Shell & Navigation (UX-002)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    currentPathname = "/workspace/org-123/orders";
  });

  describe("WorkspaceSidebar", () => {
    function mockAuth(role: "owner" | "manager" | "staff") {
      vi.spyOn(authHooks, "useAuth").mockReturnValue({
        user: { id: "u-1", email: "asad@khantraders.pk", display_name: "Asad Khan", status: "active" },
        organizations: [
          { id: "org-123", display_name: "Khan Traders", currency_code: "PKR", timezone: "Asia/Karachi", status: "active", created_at: "", role },
        ],
        activeOrg: null,
        activeOrgId: "org-123",
        activeRole: role,
        token: "t",
        isLoading: false,
        isAuthenticated: true,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        createOrg: vi.fn(),
        selectOrg: vi.fn(),
        refetchOrganizations: vi.fn(),
      });
    }

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it("renders the design navigation groups and links for an Owner (R1)", () => {
      mockAuth("owner");
      render(<WorkspaceSidebar orgId="org-123" />);

      for (const group of ["Overview", "Operations", "Finance", "Intelligence", "Management"]) {
        expect(screen.getByText(group)).toBeInTheDocument();
      }
      for (const name of [/dashboard/i, /^orders/i, /^products/i, /^inventory/i, /^customers/i, /^payments/i, /^expenses/i, /^bizpilot ai\s*read-only/i, /^team/i]) {
        expect(screen.getByRole("link", { name })).toBeInTheDocument();
      }
      expect(screen.getByRole("link", { name: /switch workspace: khan traders, owner/i })).toHaveAttribute("href", "/workspaces");
      expect(screen.getByText("Read-only")).toBeInTheDocument();
    });

    it("marks the active route with aria-current='page'", () => {
      mockAuth("owner");
      currentPathname = "/workspace/org-123/orders";
      render(<WorkspaceSidebar orgId="org-123" />);

      expect(screen.getByRole("link", { name: /^orders/i })).toHaveAttribute("aria-current", "page");
      expect(screen.getByRole("link", { name: /^products/i })).not.toHaveAttribute("aria-current");
    });

    it("hides Expenses and Team for Staff, and Team for Managers, but shows Settings", () => {
      mockAuth("staff");
      const { unmount } = render(<WorkspaceSidebar orgId="org-123" />);
      expect(screen.getByRole("link", { name: /^payments/i })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /^expenses/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /^team/i })).not.toBeInTheDocument();
      // Settings (security, your account) is for every role; Team is Owner-only (R9).
      expect(screen.getByRole("link", { name: /^settings/i })).toHaveAttribute("href", "/workspace/org-123/settings");
      unmount();

      vi.restoreAllMocks();
      mockAuth("manager");
      render(<WorkspaceSidebar orgId="org-123" />);
      expect(screen.getByRole("link", { name: /^expenses/i })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /^team/i })).not.toBeInTheDocument();
    });

    it("opens the account menu, closes it on Escape, and signs out", () => {
      mockAuth("owner");
      const logout = vi.fn().mockResolvedValue(undefined);
      vi.mocked(authHooks.useAuth).mockReturnValue({ ...authHooks.useAuth(), logout });
      render(<WorkspaceSidebar orgId="org-123" />);

      const trigger = screen.getByRole("button", { name: /account menu for asad khan/i });
      fireEvent.click(trigger);
      expect(screen.getByRole("menu", { name: "Account" })).toBeInTheDocument();
      fireEvent.keyDown(document, { key: "Escape" });
      expect(screen.queryByRole("menu", { name: "Account" })).not.toBeInTheDocument();

      fireEvent.click(trigger);
      fireEvent.click(screen.getByRole("menuitem", { name: /sign out/i }));
      expect(logout).toHaveBeenCalledTimes(1);
    });

    it("collapses via the toggle button", () => {
      mockAuth("owner");
      const onToggle = vi.fn();
      render(<WorkspaceSidebar orgId="org-123" collapsed onToggleCollapse={onToggle} />);
      fireEvent.click(screen.getByRole("button", { name: /expand sidebar/i }));
      expect(onToggle).toHaveBeenCalledTimes(1);
      expect(screen.getByRole("navigation", { name: "Primary" })).toHaveClass("collapsed");
    });
  });

  describe("WorkspaceHeader", () => {
    it("renders semantic breadcrumbs reflecting current pathname", () => {
      currentPathname = "/workspace/org-123/inventory";

      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceHeader orgId="org-123" onOpenMobileMenu={vi.fn()} />
          </AuthProvider>
        </QueryProvider>
      );

      const breadcrumbNav = screen.getByRole("navigation", { name: "Breadcrumb" });
      expect(breadcrumbNav).toBeInTheDocument();
      expect(screen.getByText("Operations")).toBeInTheDocument();
      expect(screen.getByText("Inventory")).toBeInTheDocument();
    });

    it("triggers mobile menu toggle when hamburger button is clicked", () => {
      const mockToggle = vi.fn();

      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceHeader orgId="org-123" onOpenMobileMenu={mockToggle} />
          </AuthProvider>
        </QueryProvider>
      );

      const hamburgerBtn = screen.getByRole("button", { name: /open navigation menu/i });
      fireEvent.click(hamburgerBtn);

      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it("offers role-appropriate quick-create actions", () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceHeader orgId="org-123" onOpenMobileMenu={vi.fn()} />
          </AuthProvider>
        </QueryProvider>
      );
      fireEvent.click(screen.getByRole("button", { name: /quick create menu/i }));
      const menu = screen.getByRole("menu", { name: "Quick create" });
      expect(menu).toBeInTheDocument();
      // No session in this render: least-privileged (staff) actions only.
      expect(screen.getByRole("menuitem", { name: /new order/i })).toHaveAttribute("href", "/workspace/org-123/orders");
      expect(screen.queryByRole("menuitem", { name: /record expense/i })).not.toBeInTheDocument();
      fireEvent.keyDown(document, { key: "Escape" });
      expect(screen.queryByRole("menu", { name: "Quick create" })).not.toBeInTheDocument();
    });
  });

  describe("WorkspaceLayout", () => {
    it("renders desktop layout and manages mobile drawer state", () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceLayout orgId="org-123">
              <div data-testid="test-content">Page Content</div>
            </WorkspaceLayout>
          </AuthProvider>
        </QueryProvider>
      );

      expect(screen.getByTestId("test-content")).toBeInTheDocument();

      // Drawer is initially closed
      expect(screen.queryByRole("dialog", { name: /navigation drawer/i })).not.toBeInTheDocument();

      // Open drawer via mobile menu toggle
      const hamburger = screen.getByRole("button", { name: /open navigation menu/i });
      fireEvent.click(hamburger);

      // Drawer is now open
      expect(screen.getByRole("dialog", { name: /navigation drawer/i })).toBeInTheDocument();

      // Close drawer via close button
      const closeBtn = screen.getByRole("button", { name: /close navigation menu/i });
      fireEvent.click(closeBtn);

      expect(screen.queryByRole("dialog", { name: /navigation drawer/i })).not.toBeInTheDocument();
    });

    it("closes mobile drawer on Escape key", () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceLayout orgId="org-123">
              <div>Page Content</div>
            </WorkspaceLayout>
          </AuthProvider>
        </QueryProvider>
      );

      // Open drawer
      fireEvent.click(screen.getByRole("button", { name: /open navigation menu/i }));
      expect(screen.getByRole("dialog", { name: /navigation drawer/i })).toBeInTheDocument();

      // Press Escape
      fireEvent.keyDown(window, { key: "Escape" });
      expect(screen.queryByRole("dialog", { name: /navigation drawer/i })).not.toBeInTheDocument();
    });

    it("redirects signed-out users to login once the session check finishes (FIX-008)", async () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceLayout orgId="org-123">
              <div>Page Content</div>
            </WorkspaceLayout>
          </AuthProvider>
        </QueryProvider>
      );

      await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    });

    it("redirects members away from workspaces they do not belong to (FIX-008)", async () => {
      vi.spyOn(authHooks, "useAuth").mockReturnValue({
        isLoading: false,
        user: { id: "u-1", email: "a@b.pk", display_name: "A", status: "active" },
        organizations: [{ id: "org-mine", role: "owner" }],
        activeOrg: null,
        activeRole: "owner",
        logout: vi.fn(),
      } as unknown as ReturnType<typeof authHooks.useAuth>);

      render(
        <QueryProvider>
          <WorkspaceLayout orgId="org-someone-else">
            <div>Page Content</div>
          </WorkspaceLayout>
        </QueryProvider>
      );

      await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/workspaces"));
      vi.restoreAllMocks();
    });
  });
});
