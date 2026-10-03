import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { DashboardView } from "@/components/dashboard/dashboard-view";
import { AssistantView } from "@/components/assistant/assistant-view";
import * as dashboardApi from "@/lib/api/dashboard";
import * as assistantApi from "@/lib/api/assistant";

vi.mock("@/lib/api/dashboard", () => ({
  getDashboard: vi.fn(),
}));

vi.mock("@/lib/api/inventory", () => ({
  fetchBalances: vi.fn().mockResolvedValue({ total: 5, items: [], limit: 1, offset: 0 }),
}));

vi.mock("@/lib/api/assistant", () => ({
  sendAssistantQuery: vi.fn(),
}));

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
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

const mockDashboardData = {
  freshness: {
    period: "today",
    generated_at: "2026-09-27T10:00:00Z",
    local_start_date: "2026-09-27",
    local_end_date: "2026-09-27",
    timezone: "Asia/Karachi",
  },
  sales: {
    order_count: 3,
    total_sales_minor: 150000,
    currency_code: "PKR",
  },
  payments: {
    payment_count: 2,
    total_collected_minor: 100000,
    currency_code: "PKR",
  },
  expenses: {
    expense_count: 1,
    total_expenses_minor: 40000,
    currency_code: "PKR",
  },
  net_cash: {
    net_cash_minor: 60000,
    currency_code: "PKR",
    note: "Operational cash",
  },
  inventory: {
    low_stock_count: 1,
    low_stock_threshold: 10,
    items: [],
  },
  recent_activity: [],
};

describe("UX-006: Dashboard & AI Workspace Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardApi.getDashboard).mockResolvedValue(mockDashboardData);
  });

  it("renders the AI spotlight with suggested questions linking to the assistant (R3)", async () => {
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="owner" />);

    expect(await screen.findByRole("heading", { name: /ask bizpilot about your business/i })).toBeInTheDocument();
    expect(screen.getByText(/read-only · answers from your own records/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open bizpilot ai/i })).toHaveAttribute("href", "/workspace/org-1/assistant");
    expect(screen.getByRole("link", { name: /how are sales doing today\?/i })).toHaveAttribute(
      "href",
      "/workspace/org-1/assistant?prompt=How%20are%20sales%20doing%20today%3F"
    );
    expect(screen.getByRole("link", { name: /what are my expenses this month\?/i })).toBeInTheDocument();
  });

  it("omits the expense question for Staff", async () => {
    renderWithQueryClient(<DashboardView orgId="org-1" userRole="staff" />);
    expect(await screen.findByRole("heading", { name: /ask bizpilot about your business/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /what are my expenses this month\?/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /how are sales doing today\?/i })).toBeInTheDocument();
  });

  it("automatically queries assistant when initialPrompt is provided to AssistantView", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValue({
      content: "Sales today are PKR 1,500.00 across 3 orders.",
      tool_calls: [
        {
          tool_name: "get_sales_summary",
          arguments: { period: "today" },
          latency_ms: 120.0,
          status: "success",
        },
      ],
      provenance: [
        {
          source_tool: "get_sales_summary",
          period_applied: "today",
          calculation_method: "deterministic_service",
          caveats: [],
          source_refs: [],
        },
      ],
      model: "gpt-4o",
      latency_ms: 350.0,
    });

    renderWithQueryClient(
      <AssistantView
        orgId="org-1"
        userRole="owner"
        initialPrompt="How are sales doing today?"
      />
    );

    await waitFor(() => {
      expect(assistantApi.sendAssistantQuery).toHaveBeenCalledWith(
        "org-1",
        expect.objectContaining({
          message: "How are sales doing today?",
        }),
        undefined
      );
      expect(screen.getByText(/sales today are pkr 1,500\.00 across 3 orders\./i)).toBeInTheDocument();
      expect(screen.getByText("get_sales_summary (today)")).toBeInTheDocument();
    });
  });
});
