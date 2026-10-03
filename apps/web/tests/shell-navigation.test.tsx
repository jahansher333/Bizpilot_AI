import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
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
    it("renders all navigation groups and links for Owner", () => {
      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceSidebar orgId="org-123" />
          </AuthProvider>
        </QueryProvider>
      );

      // Groups
      expect(screen.getByText("Overview")).toBeInTheDocument();
      expect(screen.getByText("Operations")).toBeInTheDocument();
      expect(screen.getByText("Finance")).toBeInTheDocument();
      expect(screen.getByText("AI Copilot")).toBeInTheDocument();
      expect(screen.getByText("Management")).toBeInTheDocument();

      // Navigation Items
      expect(screen.getByRole("link", { name: /dashboard/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /^orders/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /products/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /inventory/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /customers/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /payments/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /expenses/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /bizpilot ai/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /workspaces/i })).toBeInTheDocument();
    });

    it("marks the active route with aria-current='page'", () => {
      currentPathname = "/workspace/org-123/orders";

      render(
        <QueryProvider>
          <AuthProvider>
            <WorkspaceSidebar orgId="org-123" />
          </AuthProvider>
        </QueryProvider>
      );

      const ordersLink = screen.getByRole("link", { name: /^orders/i });
      expect(ordersLink).toHaveAttribute("aria-current", "page");

      const productsLink = screen.getByRole("link", { name: /products/i });
      expect(productsLink).not.toHaveAttribute("aria-current");
    });

    it("omits Expenses link when active user role is Staff", () => {
      vi.spyOn(authHooks, "useAuth").mockReturnValue({
        user: { id: "u-staff", email: "staff@example.com", display_name: "Staff Member", status: "active" },
        activeOrg: { id: "org-123", display_name: "Test Org", currency_code: "PKR", timezone: "Asia/Karachi", status: "active", created_at: "", role: "staff" },
        activeOrgId: "org-123",
        activeRole: "staff",
        token: "staff-token",
        organizations: [],
        isLoading: false,
        isAuthenticated: true,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        createOrg: vi.fn(),
        selectOrg: vi.fn(),
        refetchOrganizations: vi.fn(),
      });

      render(<WorkspaceSidebar orgId="org-123" />);

      // Payments is visible for staff
      expect(screen.getByRole("link", { name: /payments/i })).toBeInTheDocument();
      // Expenses must NOT be visible for staff
      expect(screen.queryByRole("link", { name: /expenses/i })).not.toBeInTheDocument();

      vi.restoreAllMocks();
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

      await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/onboarding"));
      vi.restoreAllMocks();
    });
  });
});
