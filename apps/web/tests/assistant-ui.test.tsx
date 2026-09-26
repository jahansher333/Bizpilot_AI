import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { AssistantView } from "@/components/assistant/assistant-view";
import * as assistantApi from "@/lib/api/assistant";
import { AssistantResponse } from "@/lib/schemas/assistant";

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

const mockAssistantResponse: AssistantResponse = {
  content: "Today's sales total is PKR 25,000 across 10 orders.",
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
  model: "gpt-4o-mini",
  latency_ms: 350.0,
  trace_id: "trc_test_ui_001",
  interaction_id: "00000000-0000-0000-0000-000000000001",
};

describe("BizPilot AI Assistant UI (AI-008)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the initial welcome state, business badges, and read-only notice", () => {
    renderWithQueryClient(
      <AssistantView orgId="test-org-123" userRole="owner" />
    );

    expect(screen.getByText("BizPilot Copilot")).toBeInTheDocument();
    expect(
      screen.getByText("Read-Only Business Copilot (P0)")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Grounded in your PostgreSQL business records/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/BizPilot AI is strictly read-only/i)
    ).toBeInTheDocument();
  });

  it("renders suggested business prompts for Owner role including expenses", () => {
    renderWithQueryClient(
      <AssistantView orgId="test-org-123" userRole="owner" />
    );

    expect(screen.getByText("How are sales today?")).toBeInTheDocument();
    expect(screen.getByText("Which products are low in stock?")).toBeInTheDocument();
    expect(screen.getByText("Summarize this month's expenses.")).toBeInTheDocument();
  });

  it("omits expense suggestions for Staff role to prevent financial leakage", () => {
    renderWithQueryClient(
      <AssistantView orgId="test-org-123" userRole="staff" />
    );

    expect(screen.getByText("How are sales today?")).toBeInTheDocument();
    expect(screen.getByText("Which products are low in stock?")).toBeInTheDocument();
    expect(
      screen.queryByText("Summarize this month's expenses.")
    ).not.toBeInTheDocument();
  });

  it("sends a message when clicking a suggested prompt and renders grounded response", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValueOnce(
      mockAssistantResponse
    );

    renderWithQueryClient(
      <AssistantView orgId="test-org-123" userRole="owner" />
    );

    const promptBtn = screen.getByText("How are sales today?");
    fireEvent.click(promptBtn);

    // Verify user message appears
    expect(screen.getByText("How are sales today?")).toBeInTheDocument();

    // Verify API call was initiated with correct parameters
    await waitFor(() => {
      expect(assistantApi.sendAssistantQuery).toHaveBeenCalledWith(
        "test-org-123",
        expect.objectContaining({
          message: "How are sales today?",
        }),
        undefined
      );
    });

    // Wait for response and provenance badge to render
    await waitFor(() => {
      expect(
        screen.getByText("Today's sales total is PKR 25,000 across 10 orders.")
      ).toBeInTheDocument();
      expect(screen.getByText(/get_sales_summary \(today\)/i)).toBeInTheDocument();
    });
  });

  it("sends message from input composer and clears input", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValueOnce(
      mockAssistantResponse
    );

    renderWithQueryClient(
      <AssistantView orgId="test-org-123" userRole="owner" />
    );

    const input = screen.getByPlaceholderText(
      /Ask a question about your sales, stock, customers, or payments/i
    );
    fireEvent.change(input, { target: { value: "Show stock alerts" } });
    const sendBtn = screen.getByRole("button", { name: "Send" });
    fireEvent.click(sendBtn);

    expect(screen.getByText("Show stock alerts")).toBeInTheDocument();
    expect(input).toHaveValue("");

    await waitFor(() => {
      expect(
        screen.getByText("Today's sales total is PKR 25,000 across 10 orders.")
      ).toBeInTheDocument();
    });
  });

  it("renders safe error state when assistant API call fails", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockRejectedValueOnce(
      new Error("AI assistant provider timeout")
    );

    renderWithQueryClient(
      <AssistantView orgId="test-org-123" userRole="owner" />
    );

    const input = screen.getByPlaceholderText(
      /Ask a question about your sales, stock, customers, or payments/i
    );
    fireEvent.change(input, { target: { value: "Trigger error" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(
        screen.getByText(/AI assistant provider timeout/i)
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    });
  });

  it("verifies privacy: does not persist conversation in localStorage or sessionStorage", async () => {
    const localSpy = vi.spyOn(Storage.prototype, "setItem");

    renderWithQueryClient(
      <AssistantView orgId="test-org-123" userRole="owner" />
    );

    const promptBtn = screen.getByText("How are sales today?");
    fireEvent.click(promptBtn);

    // Ensure no conversation text is written to storage
    expect(localSpy).not.toHaveBeenCalledWith(
      expect.stringContaining("message"),
      expect.anything()
    );
    localSpy.mockRestore();
  });
});
