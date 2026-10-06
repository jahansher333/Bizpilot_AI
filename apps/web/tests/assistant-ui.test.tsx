import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { AssistantView } from "@/components/assistant/assistant-view";
import { humanPeriod } from "@/components/assistant/assistant-parts";
import * as assistantApi from "@/lib/api/assistant";
import { AssistantResponse } from "@/lib/schemas/assistant";

vi.mock("@/lib/api/assistant", () => ({ sendAssistantQuery: vi.fn() }));

function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function answer(overrides: Partial<AssistantResponse> = {}): AssistantResponse {
  return {
    content: "Today's sales total is PKR 25,000 across 10 orders.",
    tool_calls: [{ tool_name: "get_sales_summary", arguments: { period: "today" }, latency_ms: 120, status: "success" }],
    provenance: [{ source_tool: "get_sales_summary", period_applied: "today", freshness_timestamp: "2026-10-07T07:06:00Z", calculation_method: "deterministic_service", caveats: [], source_refs: [] }],
    model: "gpt-4o-mini",
    latency_ms: 350,
    trace_id: "trc_test_ui_001",
    interaction_id: "00000000-0000-0000-0000-000000000001",
    ...overrides,
  };
}

class HttpError extends Error {
  constructor(public status: number) {
    super(`HTTP ${status}`);
  }
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("BizPilot AI (R8)", () => {
  it("welcomes with six suggested questions and the read-only promise", () => {
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="owner" />);
    expect(screen.getByRole("heading", { name: "BizPilot AI" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What would you like to know about your business?" })).toBeInTheDocument();
    expect(screen.getByText(/can’t create or change records/i)).toBeInTheDocument();
    for (const q of ["How are sales doing today?", "Which products are low on stock?", "How much did customers pay this week?", "What are my expenses this month?", "Show my top-selling products.", "Give me today’s business summary."]) {
      expect(screen.getByRole("button", { name: new RegExp(q.replace(/[?.]/g, "\\$&")) })).toBeEnabled();
    }
  });

  it("locks the expenses question for Staff, with the reason", () => {
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="staff" />);
    const expenses = screen.getByRole("button", { name: /What are my expenses this month\?/ });
    expect(expenses).toBeDisabled();
    expect(expenses).toHaveAccessibleDescription("Owners & Managers");
    expect(screen.getByRole("button", { name: /Give me today’s business summary/ })).toBeEnabled();
  });

  it("asks a suggested question and shows the grounded answer with its sources", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValueOnce(answer());
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="owner" />);
    fireEvent.click(screen.getByRole("button", { name: /How are sales doing today\?/ }));

    expect(screen.getByText("Checking your records…")).toBeInTheDocument();
    expect(await screen.findByText("Today's sales total is PKR 25,000 across 10 orders.")).toBeInTheDocument();
    const footer = screen.getByLabelText("Where this answer came from");
    expect(footer).toHaveTextContent("Verified from Orders");
    expect(footer).toHaveTextContent("Period Today");
    expect(footer).toHaveTextContent("Calculated from Completed orders");
    expect(footer).toHaveTextContent("As of 12:06");
    expect(assistantApi.sendAssistantQuery).toHaveBeenCalledWith("org-1", { message: "How are sales doing today?", conversation_history: [] }, undefined);
  });

  it("sends only earlier turns as history, never the current question twice", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValueOnce(answer()).mockResolvedValueOnce(answer({ content: "Three products are low." }));
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="owner" />);
    const input = screen.getByLabelText("Ask BizPilot AI");
    fireEvent.change(input, { target: { value: "Sales today?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(input).toHaveValue("");
    await screen.findByText(/PKR 25,000/);

    fireEvent.change(input, { target: { value: "And low stock?" } });
    fireEvent.submit(input.closest("form")!);
    await screen.findByText("Three products are low.");
    expect(vi.mocked(assistantApi.sendAssistantQuery).mock.calls[1][1]).toEqual({
      message: "And low stock?",
      conversation_history: [
        { role: "user", content: "Sales today?" },
        { role: "assistant", content: "Today's sales total is PKR 25,000 across 10 orders." },
      ],
    });
  });

  it("explains a role denial calmly when a tool is denied", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValueOnce(
      answer({ content: "Expense details are restricted for your role.", tool_calls: [{ tool_name: "get_expense_summary", arguments: {}, latency_ms: 3, status: "denied" }], provenance: [] })
    );
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="staff" />);
    fireEvent.change(screen.getByLabelText("Ask BizPilot AI"), { target: { value: "What did I spend?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("I can’t access expense information with your current role.")).toBeInTheDocument();
    expect(screen.getByText("I can still help with sales, stock, customers and payments.")).toBeInTheDocument();
  });

  it.each([
    [new HttpError(503), "BizPilot AI is temporarily unavailable."],
    [new HttpError(504), "That request took longer than expected."],
    [new TypeError("Failed to fetch"), "Couldn’t reach BizPilot AI."],
  ])("shows a calm failure notice and retries the same question (%s)", async (err, title) => {
    vi.mocked(assistantApi.sendAssistantQuery).mockRejectedValueOnce(err).mockResolvedValueOnce(answer());
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="owner" />);
    fireEvent.click(screen.getByRole("button", { name: /Show my top-selling products/ }));
    const notice = await screen.findByRole("alert");
    expect(notice).toHaveTextContent(title);

    fireEvent.click(within(notice).getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/PKR 25,000/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getAllByText("Show my top-selling products.")).toHaveLength(1);
    expect(vi.mocked(assistantApi.sendAssistantQuery).mock.calls[1][1]).toEqual({ message: "Show my top-selling products.", conversation_history: [] });
  });

  it("starts a new chat", async () => {
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValueOnce(answer());
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="owner" />);
    fireEvent.click(screen.getByRole("button", { name: /How are sales doing today\?/ }));
    await screen.findByText(/PKR 25,000/);
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.getByRole("heading", { name: "What would you like to know about your business?" })).toBeInTheDocument();
    expect(screen.queryByText(/PKR 25,000/)).not.toBeInTheDocument();
  });

  it("does not persist the conversation in browser storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    vi.mocked(assistantApi.sendAssistantQuery).mockResolvedValueOnce(answer());
    renderWithQueryClient(<AssistantView orgId="org-1" userRole="owner" />);
    fireEvent.click(screen.getByRole("button", { name: /How are sales doing today\?/ }));
    await screen.findByText(/PKR 25,000/);
    expect(setItem).not.toHaveBeenCalled();
    setItem.mockRestore();
  });

  it("humanises backend period names", () => {
    expect(humanPeriod("this_week")).toBe("This week");
    expect(humanPeriod("today")).toBe("Today");
  });
});
