import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import {
  formatMoney,
  toMinorUnits,
  expenseCreateSchema,
  expenseVoidSchema,
  expenseCorrectSchema,
  Expense,
  ExpenseCategory,
} from "@/lib/schemas/expenses";
import { ExpensesView } from "@/components/expenses/expenses-view";
import { ExpenseDetailModal } from "@/components/expenses/expense-detail-modal";
import { ExpenseVoidModal } from "@/components/expenses/expense-void-modal";
import { ExpenseCorrectModal } from "@/components/expenses/expense-correct-modal";
import * as expensesApi from "@/lib/api/expenses";

vi.mock("@/lib/api/expenses", () => ({
  listExpenses: vi.fn(),
  getExpense: vi.fn(),
  getDailyExpenseTotal: vi.fn(),
  createExpense: vi.fn(),
  voidExpense: vi.fn(),
  correctExpense: vi.fn(),
  listExpenseCategories: vi.fn(),
  createExpenseCategory: vi.fn(),
  archiveExpenseCategory: vi.fn(),
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

const mockCategories: ExpenseCategory[] = [
  {
    id: "33333333-3333-4333-8333-333333333333",
    organization_id: "00000000-0000-0000-0000-000000000000",
    name: "Utilities",
    status: "active",
    created_at: "2026-09-24T10:00:00Z",
    updated_at: "2026-09-24T10:00:00Z",
  },
  {
    id: "44444444-4444-4444-8444-444444444444",
    organization_id: "00000000-0000-0000-0000-000000000000",
    name: "Rent",
    status: "active",
    created_at: "2026-09-24T10:00:00Z",
    updated_at: "2026-09-24T10:00:00Z",
  },
];

const mockExpenses: Expense[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    expense_category_id: "33333333-3333-4333-8333-333333333333",
    amount_minor: 120000,
    currency_code: "PKR",
    occurred_at: "2026-09-24T10:00:00Z",
    payment_method: "cash",
    payee: "LESCO Electric",
    description: "Office electricity bill",
    status: "active",
    created_by_user_id: null,
    corrects_expense_id: null,
    replaced_by_expense_id: null,
    created_at: "2026-09-24T10:00:00Z",
    updated_at: "2026-09-24T10:00:00Z",
    voided_at: null,
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    organization_id: "00000000-0000-0000-0000-000000000000",
    expense_category_id: "44444444-4444-4444-8444-444444444444",
    amount_minor: 500000,
    currency_code: "PKR",
    occurred_at: "2026-09-24T11:00:00Z",
    payment_method: "bank_transfer",
    payee: "Plaza Landlord",
    description: "Monthly warehouse lease",
    status: "voided",
    created_by_user_id: null,
    corrects_expense_id: null,
    replaced_by_expense_id: null,
    created_at: "2026-09-24T11:00:00Z",
    updated_at: "2026-09-24T11:30:00Z",
    voided_at: "2026-09-24T11:30:00Z",
  },
];

describe("Expenses UI & Schemas (EXP-003)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(expensesApi.listExpenseCategories).mockResolvedValue({
      items: mockCategories,
      total: mockCategories.length,
      limit: 100,
      offset: 0,
    });
    vi.mocked(expensesApi.listExpenses).mockResolvedValue({
      items: mockExpenses,
      total: mockExpenses.length,
      limit: 100,
      offset: 0,
    });
    vi.mocked(expensesApi.getDailyExpenseTotal).mockResolvedValue({
      date: "2026-09-24",
      total_minor: 120000,
      expense_count: 1,
      currency_code: "PKR",
    });
  });

  it("validates expenseCreateSchema rejecting zero or negative amounts", () => {
    const zeroResult = expenseCreateSchema.safeParse({
      amount_minor: 0,
      payment_method: "cash",
    });
    expect(zeroResult.success).toBe(false);

    const validResult = expenseCreateSchema.safeParse({
      amount_minor: 50000,
      payment_method: "bank_transfer",
      payee: "Vendor Corp",
    });
    expect(validResult.success).toBe(true);
    if (validResult.success) {
      expect(validResult.data.currency_code).toBe("PKR");
    }
  });

  it("validates expenseVoidSchema enforcing non-empty reason", () => {
    const emptyResult = expenseVoidSchema.safeParse({ reason: "" });
    expect(emptyResult.success).toBe(false);

    const validResult = expenseVoidSchema.safeParse({
      reason: "Duplicate voucher entry",
    });
    expect(validResult.success).toBe(true);
  });

  it("validates expenseCorrectSchema requiring reason and positive amount", () => {
    const invalidResult = expenseCorrectSchema.safeParse({
      reason: "",
      amount_minor: 0,
    });
    expect(invalidResult.success).toBe(false);

    const validResult = expenseCorrectSchema.safeParse({
      reason: "Correcting invoice calculation",
      amount_minor: 75000,
      payment_method: "cash",
    });
    expect(validResult.success).toBe(true);
  });

  it("formats currency correctly with formatMoney and toMinorUnits", () => {
    expect(formatMoney(15000)).toBe("Rs. 150.00");
    expect(formatMoney(500000)).toBe("Rs. 5000.00");
    expect(formatMoney(25000, "USD")).toBe("USD 250.00");
    expect(toMinorUnits(150.5)).toBe(15050);
  });

  it("denies access for Staff role with explicit restriction banner", () => {
    renderWithQueryClient(
      <ExpensesView
        orgId="00000000-0000-0000-0000-000000000000"
        userRole="staff"
      />
    );

    expect(screen.getByText("Access Restricted")).toBeInTheDocument();
    expect(
      screen.getByText(/Staff roles do not have permission to view or manage operating expenses/i)
    ).toBeInTheDocument();
    expect(screen.queryByText("Record Expense")).not.toBeInTheDocument();
    expect(screen.queryByText("Categories")).not.toBeInTheDocument();
  });

  it("renders expense table and daily summary for Owner with full controls (Void + Correct)", async () => {
    renderWithQueryClient(
      <ExpensesView
        orgId="00000000-0000-0000-0000-000000000000"
        userRole="owner"
      />
    );

    expect(await screen.findByText("Operating Expenses")).toBeInTheDocument();
    expect(screen.getByText("Record Expense")).toBeInTheDocument();
    expect(screen.getByText("Categories")).toBeInTheDocument();

    // Table rows
    expect(await screen.findByText("LESCO Electric")).toBeInTheDocument();
    expect(screen.getAllByText("Rs. 1200.00").length).toBeGreaterThanOrEqual(1);

    // Owner should see both Void and Correct buttons on active expense
    expect(screen.getByRole("button", { name: "Void" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correct" })).toBeInTheDocument();
  });

  it("renders Correct button but omits Void button for Manager role", async () => {
    renderWithQueryClient(
      <ExpensesView
        orgId="00000000-0000-0000-0000-000000000000"
        userRole="manager"
      />
    );

    expect(await screen.findByText("Operating Expenses")).toBeInTheDocument();
    expect(screen.getByText("Record Expense")).toBeInTheDocument();
    expect(await screen.findByText("LESCO Electric")).toBeInTheDocument();

    // Manager can correct but CANNOT void
    expect(screen.getByRole("button", { name: "Correct" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Void" })).not.toBeInTheDocument();
  });

  it("submits void form when Owner confirms void", async () => {
    const handleClose = vi.fn();
    vi.mocked(expensesApi.voidExpense).mockResolvedValue({
      ...mockExpenses[0],
      status: "voided",
      voided_at: "2026-09-24T12:00:00Z",
    });

    renderWithQueryClient(
      <ExpenseVoidModal
        isOpen={true}
        onClose={handleClose}
        expense={mockExpenses[0]}
        orgId="00000000-0000-0000-0000-000000000000"
      />
    );

    expect(screen.getByText("Void Expense")).toBeInTheDocument();
    const reasonInput = screen.getByPlaceholderText(/Duplicate expense entry/i);
    fireEvent.change(reasonInput, { target: { value: "Duplicate bill entry" } });

    const submitBtn = screen.getByRole("button", { name: "Confirm Void" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(expensesApi.voidExpense).toHaveBeenCalledWith(
        "00000000-0000-0000-0000-000000000000",
        mockExpenses[0].id,
        { reason: "Duplicate bill entry" },
        undefined,
        expect.any(String)
      );
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("submits correction form when authorized user corrects expense", async () => {
    const handleClose = vi.fn();
    vi.mocked(expensesApi.correctExpense).mockResolvedValue({
      ...mockExpenses[0],
      id: "55555555-5555-4555-8555-555555555555",
      amount_minor: 150000,
      corrects_expense_id: mockExpenses[0].id,
    });

    renderWithQueryClient(
      <ExpenseCorrectModal
        isOpen={true}
        onClose={handleClose}
        expense={mockExpenses[0]}
        categories={mockCategories}
        orgId="00000000-0000-0000-0000-000000000000"
      />
    );

    expect(screen.getByText("Correct Expense")).toBeInTheDocument();
    const reasonInput = screen.getByPlaceholderText(/Adjusted invoice amount/i);
    fireEvent.change(reasonInput, { target: { value: "Adjusted fuel surge surcharge" } });

    const submitBtn = screen.getByRole("button", { name: "Save Correction" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(expensesApi.correctExpense).toHaveBeenCalledWith(
        "00000000-0000-0000-0000-000000000000",
        mockExpenses[0].id,
        expect.objectContaining({
          reason: "Adjusted fuel surge surcharge",
        }),
        undefined,
        expect.any(String)
      );
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("displays expense details in ExpenseDetailModal", () => {
    const handleClose = vi.fn();
    render(
      <ExpenseDetailModal
        isOpen={true}
        onClose={handleClose}
        expense={mockExpenses[0]}
        categories={mockCategories}
      />
    );

    expect(screen.getByText("Expense Details")).toBeInTheDocument();
    expect(screen.getByText("LESCO Electric")).toBeInTheDocument();
    expect(screen.getByText("Office electricity bill")).toBeInTheDocument();
    expect(screen.getByText("Utilities")).toBeInTheDocument();
  });
});
