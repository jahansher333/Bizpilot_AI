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

describe("Dashboard UI & Schemas (DASH-003)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("validates dashboardSummarySchema correctly", () => {
    const parseResult = dashboardSummarySchema.safeParse(mockOwnerDashboardData);
    expect(parseResult.success).toBe(true);

    const staffParseResult = dashboardSummarySchema.safeParse(mockStaffDashboardData);
    expect(staffParseResult.success).toBe(true);
  });

  it("formats PKR currency properly using formatMoney", () => {
    expect(formatMoney(125000)).toBe("Rs. 1250.00");
    expect(formatMoney(95000)).toBe("Rs. 950.00");
    expect(formatMoney(0)).toBe("Rs. 0.00");
    expect(formatMoney(-5000)).toBe("Rs. -50.00");
  });

  it("renders full dashboard metrics for Owner role", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockOwnerDashboardData);

    renderWithQueryClient(
      <DashboardView
        orgId="00000000-0000-0000-0000-000000000000"
        userRole="owner"
      />
    );

    // Sales and Collections (wait for query data to render)
    expect(await screen.findByText("Rs. 1250.00")).toBeInTheDocument();
    expect(screen.getByText("Rs. 950.00")).toBeInTheDocument();
    expect(screen.getByText("5 active order(s)")).toBeInTheDocument();
    expect(screen.getByText("4 receipt(s)")).toBeInTheDocument();

    // Expenses and Net Cash Flow (Visible for Owner)
    expect(screen.getByText("Rs. 300.00")).toBeInTheDocument();
    expect(screen.getByText("Rs. 650.00")).toBeInTheDocument();
    expect(screen.getByText("2 expense record(s)")).toBeInTheDocument();

    // Low stock alerts
    expect(screen.getByText("Stock Alerts (2)")).toBeInTheDocument();
    expect(screen.getByText("Sugar 1kg")).toBeInTheDocument();
    expect(screen.getByText("Tea 500g")).toBeInTheDocument();
    expect(screen.getByText("Out of Stock")).toBeInTheDocument();
    expect(screen.getByText("Low Stock")).toBeInTheDocument();

    // Recent activity (includes order, payment, and expense)
    expect(screen.getByText("ORD-1001")).toBeInTheDocument();
    expect(screen.getByText("PAY-1001")).toBeInTheDocument();
    expect(screen.getByText("LESCO Electric")).toBeInTheDocument();
  });

  it("renders limited view for Staff role with expenses and net cash restricted", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockStaffDashboardData);

    renderWithQueryClient(
      <DashboardView
        orgId="00000000-0000-0000-0000-000000000000"
        userRole="staff"
      />
    );

    // Sales and Collections remain visible (wait for query data to render)
    expect(await screen.findByText("Rs. 1250.00")).toBeInTheDocument();
    expect(screen.getByText("Rs. 950.00")).toBeInTheDocument();

    // Expenses & Net Cash are explicitly marked restricted/unavailable
    expect(screen.getByText("Restricted")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/Staff role is not authorized to view operating expenses/i)
    ).toBeInTheDocument();

    // Recent activity does NOT contain expenses
    expect(screen.getByText("ORD-1001")).toBeInTheDocument();
    expect(screen.getByText("PAY-1001")).toBeInTheDocument();
    expect(screen.queryByText("LESCO Electric")).not.toBeInTheDocument();
  });

  it("triggers query with selected period when period button is clicked", async () => {
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockOwnerDashboardData);

    renderWithQueryClient(
      <DashboardView
        orgId="00000000-0000-0000-0000-000000000000"
        userRole="owner"
      />
    );

    expect(await screen.findByText("Operational Dashboard")).toBeInTheDocument();

    const yesterdayBtn = screen.getByRole("button", { name: "yesterday" });
    fireEvent.click(yesterdayBtn);

    await waitFor(() => {
      expect(dashboardApi.getDashboard).toHaveBeenCalledWith(
        "00000000-0000-0000-0000-000000000000",
        expect.objectContaining({ period: "yesterday" }),
        undefined
      );
    });
  });

  it("renders error state with retry button when query fails", async () => {
    vi.mocked(dashboardApi.getDashboard).mockRejectedValue(new Error("Network failure"));

    renderWithQueryClient(
      <DashboardView
        orgId="00000000-0000-0000-0000-000000000000"
        userRole="owner"
      />
    );

    expect(await screen.findByText("Failed to load dashboard metrics.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
