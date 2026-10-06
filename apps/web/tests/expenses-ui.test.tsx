import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { Expense, ExpenseCategory, expenseCorrectSchema, expenseCreateSchema, expenseVoidSchema } from "@/lib/schemas/expenses";
import { ExpensesView } from "@/components/expenses/expenses-view";
import { thisMonthRange } from "@/components/finance/record-meta";
import * as expensesApi from "@/lib/api/expenses";
import * as dashboardApi from "@/lib/api/dashboard";

vi.mock("@/lib/api/expenses", () => ({
  listExpenses: vi.fn(),
  getExpense: vi.fn(),
  createExpense: vi.fn(),
  voidExpense: vi.fn(),
  correctExpense: vi.fn(),
  listExpenseCategories: vi.fn(),
  createExpenseCategory: vi.fn(),
  updateExpenseCategory: vi.fn(),
  archiveExpenseCategory: vi.fn(),
}));
vi.mock("@/lib/api/dashboard", () => ({ getDashboard: vi.fn() }));

function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const ORG = "00000000-0000-0000-0000-000000000000";
const UTIL = "11111111-1111-4111-8111-111111111111";
const RENT = "22222222-2222-4222-8222-222222222222";
const OLD = "33333333-3333-4333-8333-333333333333";

const categories: ExpenseCategory[] = [
  { id: UTIL, organization_id: ORG, name: "Utilities", status: "active", created_at: "", updated_at: "" },
  { id: RENT, organization_id: ORG, name: "Rent", status: "active", created_at: "", updated_at: "" },
  { id: OLD, organization_id: ORG, name: "Generator diesel", status: "archived", created_at: "", updated_at: "" },
];

function makeExpense(overrides: Partial<Expense>): Expense {
  return {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    organization_id: ORG,
    expense_category_id: UTIL,
    amount_minor: 895_000,
    currency_code: "PKR",
    occurred_at: "2026-10-01T09:30:00Z",
    payment_method: "bank_transfer",
    payee: "K-Electric",
    description: "Electricity bill — September",
    status: "active",
    created_by_user_id: null,
    corrects_expense_id: null,
    replaced_by_expense_id: null,
    created_at: "2026-10-01T09:30:00Z",
    updated_at: "2026-10-01T09:30:00Z",
    voided_at: null,
    ...overrides,
  };
}

const bill = makeExpense({});
const tea = makeExpense({ id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", expense_category_id: null, amount_minor: 60_000, payee: null, description: "Tea for staff", payment_method: "cash", status: "voided" });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(expensesApi.listExpenses).mockResolvedValue({ items: [bill, tea], total: 2, limit: 50, offset: 0 });
  vi.mocked(expensesApi.listExpenseCategories).mockResolvedValue({ items: categories, total: 3, limit: 100, offset: 0 });
  vi.mocked(dashboardApi.getDashboard).mockImplementation(async (_org, params) => ({
    expenses: params?.period === "today" ? { expense_count: 3, total_expenses_minor: 1_235_000, currency_code: "PKR" } : { expense_count: 11, total_expenses_minor: 4_105_000, currency_code: "PKR" },
  }) as any);
});

describe("Expense schemas", () => {
  it("rejects non-positive amounts and short reasons", () => {
    expect(expenseCreateSchema.safeParse({ amount_minor: 0 }).success).toBe(false);
    expect(expenseCreateSchema.safeParse({ amount_minor: 100, payment_method: "mobile_wallet" }).success).toBe(true);
    expect(expenseVoidSchema.safeParse({ reason: "no" }).success).toBe(false);
    expect(expenseCorrectSchema.safeParse({ reason: "Bill was lower", amount_minor: 100 }).success).toBe(true);
  });
});

describe("Expenses (R7)", () => {
  it("shows Staff a restricted state and never asks the API for expenses", () => {
    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="staff" />);
    expect(screen.getByRole("heading", { name: "Expenses are visible to Owners and Managers" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to dashboard" })).toHaveAttribute("href", `/workspace/${ORG}`);
    expect(expensesApi.listExpenses).not.toHaveBeenCalled();
    expect(dashboardApi.getDashboard).not.toHaveBeenCalled();
  });

  it("lists this month's expenses with categories, totals and the This month filter", async () => {
    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="owner" />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByRole("button", { name: "Electricity bill — September" })).toBeInTheDocument();
    expect(within(rows[1]).getByText("K-Electric")).toBeInTheDocument();
    await waitFor(() => expect(within(rows[1]).getByText("Utilities")).toBeInTheDocument());
    expect(within(rows[1]).getByText("Bank transfer")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Uncategorised")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Voided")).toBeInTheDocument();

    const summary = screen.getByRole("region", { name: "Expense summary" });
    await waitFor(() => expect(within(summary).getByText("12,350")).toBeInTheDocument());
    expect(within(summary).getByText("41,050")).toBeInTheDocument();

    const { start, end } = thisMonthRange();
    expect(expensesApi.listExpenses).toHaveBeenCalledWith(ORG, expect.objectContaining({ startDate: start, endDate: end }), undefined);
    fireEvent.click(screen.getByRole("button", { name: "This month" }));
    await waitFor(() => expect(expensesApi.listExpenses).toHaveBeenLastCalledWith(ORG, expect.objectContaining({ startDate: undefined, endDate: undefined }), undefined));

    const chips = screen.getByRole("group", { name: "Category" });
    expect(within(chips).queryByRole("button", { name: "Generator diesel" })).not.toBeInTheDocument();
    fireEvent.click(within(chips).getByRole("button", { name: "Rent" }));
    await waitFor(() => expect(expensesApi.listExpenses).toHaveBeenLastCalledWith(ORG, expect.objectContaining({ categoryId: RENT }), undefined));
  });

  it("lets Managers correct but only Owners void", async () => {
    const owner = renderWithQueryClient(<ExpensesView orgId={ORG} userRole="owner" />);
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: "Correct Electricity bill — September" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Void Electricity bill — September" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Correct Tea for staff" })).not.toBeInTheDocument();
    owner.unmount();

    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="manager" />);
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: "Correct Electricity bill — September" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Void Electricity bill — September" })).not.toBeInTheDocument();
  });

  it("records an expense in two steps: fill in, review, confirm", async () => {
    vi.mocked(expensesApi.createExpense).mockResolvedValue(makeExpense({ description: "Gas cylinder refill", amount_minor: 240_000 }));
    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="manager" />);
    fireEvent.click(screen.getByRole("button", { name: /record expense/i }));
    const dialog = screen.getByRole("dialog", { name: "Record expense" });
    const review = within(dialog).getByRole("button", { name: "Review expense" });
    expect(review).toBeDisabled();

    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Utilities" })).toBeInTheDocument());
    fireEvent.click(within(dialog).getByRole("button", { name: "Utilities" }));
    fireEvent.change(within(dialog).getByLabelText("Description"), { target: { value: "Gas cylinder refill" } });
    fireEvent.change(within(dialog).getByLabelText("Amount"), { target: { value: "2,400" } });
    fireEvent.click(review);

    expect(within(dialog).getByText("You’re recording")).toBeInTheDocument();
    expect(within(dialog).getByText(/Gas cylinder refill · Utilities · Cash · Today/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /confirm & record/i }));
    await waitFor(() =>
      expect(expensesApi.createExpense).toHaveBeenCalledWith(
        ORG,
        expect.objectContaining({ amount_minor: 240_000, expense_category_id: UTIL, description: "Gas cylinder refill", payment_method: "cash", currency_code: "PKR" }),
        undefined,
        expect.any(String)
      )
    );
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Record expense" })).not.toBeInTheDocument());
  });

  it("voids an expense with a reason (Owner)", async () => {
    vi.mocked(expensesApi.voidExpense).mockResolvedValue({ ...bill, status: "voided" });
    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="owner" />);
    fireEvent.click(await screen.findByRole("button", { name: "Void Electricity bill — September" }));
    const dialog = screen.getByRole("alertdialog", { name: "Void this expense?" });
    expect(within(dialog).getByRole("button", { name: "Keep expense" })).toHaveFocus();
    fireEvent.change(within(dialog).getByLabelText(/reason/i), { target: { value: "Entered twice" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Void expense" }));
    await waitFor(() => expect(expensesApi.voidExpense).toHaveBeenCalledWith(ORG, bill.id, { reason: "Entered twice" }, undefined, expect.stringMatching(/^web-void-/)));
  });

  it("corrects an expense keeping its details unless changed", async () => {
    vi.mocked(expensesApi.correctExpense).mockResolvedValue(makeExpense({ id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", amount_minor: 859_000 }));
    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="manager" />);
    fireEvent.click(await screen.findByRole("button", { name: "Correct Electricity bill — September" }));
    const dialog = screen.getByRole("dialog", { name: "Correct expense" });
    expect(within(dialog).getByLabelText("Correct amount")).toHaveValue("8,950");
    fireEvent.change(within(dialog).getByLabelText("Correct amount"), { target: { value: "8590" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Review correction" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/at least 3 characters/i);
    fireEvent.change(within(dialog).getByLabelText(/reason/i), { target: { value: "Bill was 8,590" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Review correction" }));

    const review = screen.getByRole("alertdialog", { name: "Correct this expense?" });
    expect(within(review).getByLabelText("Changes")).toHaveTextContent("Amount8,950 → 8,590");
    fireEvent.click(within(review).getByRole("button", { name: "Back" }));
    expect(screen.getByRole("dialog", { name: "Correct expense" })).toBeInTheDocument();
    expect(screen.getByLabelText("Correct amount")).toHaveValue("8590");
    fireEvent.click(screen.getByRole("button", { name: "Review correction" }));
    fireEvent.click(within(screen.getByRole("alertdialog", { name: "Correct this expense?" })).getByRole("button", { name: "Submit correction" }));
    await waitFor(() =>
      expect(expensesApi.correctExpense).toHaveBeenCalledWith(
        ORG,
        bill.id,
        expect.objectContaining({ reason: "Bill was 8,590", amount_minor: 859_000, expense_category_id: UTIL, description: "Electricity bill — September", payee: "K-Electric", payment_method: "bank_transfer" }),
        undefined,
        expect.stringMatching(/^web-correct-/)
      )
    );
  });

  it("opens details from the list", async () => {
    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="manager" />);
    fireEvent.click(await screen.findByRole("button", { name: "Electricity bill — September" }));
    const dialog = screen.getByRole("dialog", { name: "Electricity bill — September" });
    expect(within(dialog).getByText("K-Electric")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /correct expense/i })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /void expense/i })).not.toBeInTheDocument();
  });

  it("manages categories: add, rename, archive (no restore)", async () => {
    vi.mocked(expensesApi.createExpenseCategory).mockResolvedValue({ ...categories[0], id: "44444444-4444-4444-8444-444444444444", name: "Transport" });
    vi.mocked(expensesApi.updateExpenseCategory).mockResolvedValue({ ...categories[1], name: "Shop rent" });
    vi.mocked(expensesApi.archiveExpenseCategory).mockResolvedValue({ ...categories[0], status: "archived" });
    renderWithQueryClient(<ExpensesView orgId={ORG} userRole="owner" />);
    const panel = await screen.findByRole("region", { name: "Expense categories" });
    await waitFor(() => expect(within(panel).getByText("Generator diesel")).toBeInTheDocument());
    expect(within(panel).getByText("Archived")).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: /restore/i })).not.toBeInTheDocument();

    fireEvent.click(within(panel).getByRole("button", { name: "New" }));
    fireEvent.change(within(panel).getByLabelText("New category name"), { target: { value: "Transport" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Add" }));
    await waitFor(() => expect(expensesApi.createExpenseCategory).toHaveBeenCalledWith(ORG, { name: "Transport" }, undefined));

    fireEvent.click(within(panel).getByRole("button", { name: "Rename Rent" }));
    fireEvent.change(within(panel).getByLabelText("Rename Rent"), { target: { value: "Shop rent" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(expensesApi.updateExpenseCategory).toHaveBeenCalledWith(ORG, RENT, { name: "Shop rent" }, undefined));

    fireEvent.click(within(panel).getByRole("button", { name: "Archive Utilities" }));
    const confirm = screen.getByRole("alertdialog", { name: "Archive “Utilities”?" });
    fireEvent.click(within(confirm).getByRole("button", { name: "Archive category" }));
    await waitFor(() => expect(expensesApi.archiveExpenseCategory).toHaveBeenCalledWith(ORG, UTIL, undefined));
  });
});
