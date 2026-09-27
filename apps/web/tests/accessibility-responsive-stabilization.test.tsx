import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { WorkspaceLayout } from "@/components/shell/workspace-layout";
import { OrderCreateModal } from "@/components/orders/order-create-modal";
import { OrderDetailModal } from "@/components/orders/order-detail-modal";
import * as authHook from "@/hooks/use-auth";
import * as catalogApi from "@/lib/api/catalog";
import * as customersApi from "@/lib/api/customers";

vi.mock("@/lib/api/catalog", () => ({
  listProducts: vi.fn(),
}));

vi.mock("@/lib/api/customers", () => ({
  listCustomers: vi.fn(),
}));

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const testQueryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={testQueryClient}>{ui}</QueryClientProvider>
  );
}

describe("UX-007: Mobile Responsive & Accessibility Stabilization", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(authHook, "useAuth").mockReturnValue({
      user: { id: "user-1", email: "owner@example.com", is_active: true } as any,
      activeOrg: { id: "org-1", slug: "lahore-store", display_name: "Lahore Store" } as any,
      activeOrgId: "org-1",
      activeRole: "owner",
      organizations: [],
      token: "mock-token",
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      createOrg: vi.fn(),
      selectOrg: vi.fn(),
      refetchOrganizations: vi.fn(),
    });

    vi.mocked(catalogApi.listProducts).mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    });

    vi.mocked(customersApi.listCustomers).mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    });
  });

  describe("Accessible Dialogs & Keyboard Navigation", () => {
    it("OrderCreateModal has role='dialog', aria-modal='true', and closes on Escape key", async () => {
      const handleClose = vi.fn();

      renderWithQueryClient(
        <OrderCreateModal
          isOpen={true}
          onClose={handleClose}
          orgId="org-1"
        />
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveAttribute("aria-modal", "true");
      expect(dialog).toHaveAttribute("aria-labelledby", "order-create-modal-title");

      // Verify close button has aria-label
      const closeBtn = screen.getByRole("button", { name: /close dialog/i });
      expect(closeBtn).toBeInTheDocument();

      // Press Escape key to close
      fireEvent.keyDown(window, { key: "Escape", code: "Escape" });
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it("OrderDetailModal renders with semantic dialog attributes and closes on Escape", async () => {
      const handleClose = vi.fn();
      const mockOrder = {
        id: "11111111-1111-4111-8111-111111111111",
        organization_id: "org-1",
        order_number: "ORD-0001",
        customer_id: null,
        ordered_at: "2026-09-20T10:00:00Z",
        status: "active" as const,
        order_total_minor: 50000,
        currency_code: "PKR",
        created_by_user_id: null,
        corrects_order_id: null,
        replaced_by_order_id: null,
        created_at: "2026-09-20T10:00:00Z",
        updated_at: "2026-09-20T10:00:00Z",
        voided_at: null,
        items: [],
      };

      renderWithQueryClient(
        <OrderDetailModal
          isOpen={true}
          onClose={handleClose}
          order={mockOrder}
        />
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveAttribute("aria-modal", "true");
      expect(dialog).toHaveAttribute("aria-labelledby", "order-detail-modal-title");

      const closeBtn = screen.getByRole("button", { name: /close order details/i });
      expect(closeBtn).toBeInTheDocument();

      fireEvent.keyDown(window, { key: "Escape", code: "Escape" });
      expect(handleClose).toHaveBeenCalledTimes(1);
    });
  });

  describe("Mobile Drawer and Responsive Viewport Controls", () => {
    it("opens and closes mobile navigation drawer with keyboard and backdrop controls", async () => {
      renderWithQueryClient(
        <WorkspaceLayout orgId="org-1">
          <div>Workspace Content</div>
        </WorkspaceLayout>
      );

      // Open button has aria-label
      const openButton = screen.getByRole("button", { name: /open navigation menu/i });
      expect(openButton).toBeInTheDocument();

      // Drawer is initially closed
      expect(screen.queryByRole("dialog", { name: /navigation drawer/i })).not.toBeInTheDocument();

      // Click to open drawer
      fireEvent.click(openButton);

      const drawer = screen.getByRole("dialog", { name: /navigation drawer/i });
      expect(drawer).toHaveAttribute("aria-modal", "true");

      // Close button inside drawer
      const closeButton = screen.getByRole("button", { name: /close navigation menu/i });
      expect(closeButton).toBeInTheDocument();

      // Close via Escape key
      fireEvent.keyDown(window, { key: "Escape", code: "Escape" });
      expect(screen.queryByRole("dialog", { name: /navigation drawer/i })).not.toBeInTheDocument();
    });

    it("includes accessible breadcrumbs with semantic nav landmark", () => {
      renderWithQueryClient(
        <WorkspaceLayout orgId="org-1">
          <div>Workspace Content</div>
        </WorkspaceLayout>
      );

      const breadcrumbNav = screen.getByRole("navigation", { name: /breadcrumb/i });
      expect(breadcrumbNav).toBeInTheDocument();
    });
  });
});
