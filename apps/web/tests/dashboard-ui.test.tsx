import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import {
  formatMoney,
  dashboardSummarySchema,
  DashboardSummary,
} from "@/lib/schemas/dashboard";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import * as dashboardApi from "@/lib/api/dashboard";

vi.mock("@/lib/api/dashboard", () => ({
  getDashboard: vi.fn(),
}));

vi.mock("@/lib/api/inventory", () => ({
  fetchBalances: vi.fn().mockResolvedValue({ total: 20, items: [], limit: 1, offset: 0 }),
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

const mockOwnerDashboardData: DashboardSummary = {
  sales: {
    order_count: 5,
    total_sales_minor: 125000,
    currency_code: "PKR",
  },
  payments: {
    payment_count: 4,
    total_collected_minor: 95000,
    currency_code: "PKR",
  },
  expenses: {
    expense_count: 2,
    total_expenses_minor: 30000,
    currency_code: "PKR",
  },
  net_cash: {
    net_cash_minor: 65000,
    currency_code: "PKR",
    note: "Net operational cash flow",
  },
  inventory: {
    low_stock_count: 2,
    low_stock_threshold: 10,
    items: [
      {
        product_id: "11111111-1111-4111-8111-111111111111",
        product_code: "SKU-SUGAR",
        product_name: "Sugar 1kg",
        base_unit: "kg",
        on_hand_quantity: 4,
        is_out_of_stock: false,
      },
      {
        product_id: "22222222-2222-4222-8222-222222222222",
        product_code: "SKU-TEA",
        product_name: "Tea 500g",
        base_unit: "pack",
        on_hand_quantity: 0,
        is_out_of_stock: true,
      },
    ],
  },
  recent_activity: [
    {
      id: "33333333-3333-4333-8333-333333333333",
      activity_type: "order",
      reference_code: "ORD-1001",
      amount_minor: 25000,
      currency_code: "PKR",
      timestamp: "2026-09-26T10:00:00Z",
      status: "active",
      description: "Sales order ORD-1001",
    },
    {
      id: "44444444-4444-4444-8444-444444444444",
      activity_type: "payment",
      reference_code: "PAY-1001",
      amount_minor: 25000,
      currency_code: "PKR",
      timestamp: "2026-09-26T10:05:00Z",
      status: "active",
      description: "Payment received (cash)",
    },
    {
      id: "55555555-5555-4555-8555-555555555555",
      activity_type: "expense",
      reference_code: "LESCO Electric",
      amount_minor: 12000,
      currency_code: "PKR",
      timestamp: "2026-09-26T09:30:00Z",
      status: "active",
      description: "Office utility bill",
    },
  ],
  freshness: {
    generated_at: "2026-09-26T12:00:00Z",
    period: "today",
    local_start_date: "2026-09-26",
    local_end_date: "2026-09-26",
    timezone: "Asia/Karachi",
  },
};

const mockStaffDashboardData: DashboardSummary = {
  sales: {
    order_count: 5,
    total_sales_minor: 125000,
    currency_code: "PKR",
  },
  payments: {
    payment_count: 4,
    total_collected_minor: 95000,
    currency_code: "PKR",
  },
  expenses: null,
  net_cash: null,
  inventory: {
    low_stock_count: 2,
    low_stock_threshold: 10,
    items: mockOwnerDashboardData.inventory.items,
  },
  recent_activity: [
    mockOwnerDashboardData.recent_activity[0],
    mockOwnerDashboardData.recent_activity[1],
  ],
  freshness: mockOwnerDashboardData.freshness,
};

describe("Dashboard UI & Schemas (DASH-003, R3 design)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("validates dashboardSummarySchema correctly", () => {
    expect(dashboardSummarySchema.safeParse(mockOwnerDashboardData).success).toBe(true);
  });

  it("formats PKR currency properly using formatMoney", () => {
    expect(formatMoney(125000, "PKR")).toBe("Rs. 1250.00");
  });

  it("renders the four key figures, inventory health and activity for an Owner", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockOwnerDashboardData);
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="owner" />);

    const figures = await screen.findByRole("region", { name: "Key figures" });
    expect(figures).toHaveTextContent("Sales");
    expect(figures).toHaveTextContent("1,250");
    expect(figures).toHaveTextContent("5 completed orders · voided excluded");
    expect(figures).toHaveTextContent("950");
    expect(figures).toHaveTextContent("4 payments recorded");
    expect(figures).toHaveTextContent("300");
    expect(figures).toHaveTextContent("2 expenses recorded");
    expect(figures).toHaveTextContent("650");
    expect(figures).toHaveTextContent("Calculated · not a profit figure");

    // 20 tracked balances, 2 needing attention: 18 healthy, 1 low, 1 out
    expect(await screen.findByRole("img", { name: /20 tracked products: 18 healthy, 1 low stock, 1 out of stock/i })).toBeInTheDocument();
    expect(screen.getByText("Sugar 1kg")).toBeInTheDocument();
    expect(screen.getByText("Tea 500g")).toBeInTheDocument();
    expect(screen.getAllByText("Adjust stock").length).toBe(2);

    expect(screen.getByRole("link", { name: "ORD-1001" })).toHaveAttribute("href", "/workspace/org-1/orders");
    expect(screen.getByRole("link", { name: "PAY-1001" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "LESCO Electric" })).toBeInTheDocument();
  });

  it("shows a restricted card instead of expenses and net cash for Staff", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockStaffDashboardData);
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="staff" />);

    const figures = await screen.findByRole("region", { name: "Key figures" });
    expect(figures).toHaveTextContent("Visible to Owners and Managers.");
    expect(figures).not.toHaveTextContent("Net cash flow");
    expect(screen.queryByText("Adjust stock")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "LESCO Electric" })).not.toBeInTheDocument();
  });

  it("shows Unavailable rather than zero when an owner figure is missing (FR-011)", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue({ ...mockOwnerDashboardData, net_cash: null });
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="owner" />);
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
  });

  it("queries the selected period", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockOwnerDashboardData);
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="owner" />);
    await screen.findByRole("region", { name: "Key figures" });

    const yesterday = screen.getByRole("button", { name: "Yesterday" });
    fireEvent.click(yesterday);
    expect(yesterday).toHaveAttribute("aria-pressed", "true");
    await waitFor(() =>
      expect(dashboardApi.getDashboard).toHaveBeenCalledWith("org-1", expect.objectContaining({ period: "yesterday" }), undefined)
    );
  });

  it("waits for both dates before querying a custom range", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockOwnerDashboardData);
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="owner" />);
    await screen.findByRole("region", { name: "Key figures" });
    vi.mocked(dashboardApi.getDashboard).mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Custom" }));
    expect(screen.getByRole("button", { name: /apply dates/i })).toBeDisabled();
    expect(dashboardApi.getDashboard).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-09-30" } });
    fireEvent.click(screen.getByRole("button", { name: /apply dates/i }));
    await waitFor(() =>
      expect(dashboardApi.getDashboard).toHaveBeenCalledWith(
        "org-1",
        expect.objectContaining({ period: "custom", startDate: "2026-09-01", endDate: "2026-09-30" }),
        undefined
      )
    );
  });

  it("shows an error with retry when the dashboard fails to load", async () => {
    vi.mocked(dashboardApi.getDashboard).mockRejectedValue(new Error("Network failure"));
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="owner" />);
    expect(await screen.findByText("Couldn’t load the dashboard")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    await waitFor(() => expect(vi.mocked(dashboardApi.getDashboard).mock.calls.length).toBeGreaterThan(1));
  });
});
