import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { PaymentsView } from "@/components/payments/payments-view";
import { PaymentCreateModal } from "@/components/payments/payment-create-modal";
import { ExpensesView } from "@/components/expenses/expenses-view";
import * as paymentsApi from "@/lib/api/payments";
import * as expensesApi from "@/lib/api/expenses";
import * as customersApi from "@/lib/api/customers";
import * as ordersApi from "@/lib/api/orders";

vi.mock("@/lib/api/payments", () => ({
  listPayments: vi.fn(),
  getPayment: vi.fn(),
  createPayment: vi.fn(),
  voidPayment: vi.fn(),
  correctPayment: vi.fn(),
  getDailyPaymentTotal: vi.fn(),
}));

vi.mock("@/lib/api/expenses", () => ({
  listExpenses: vi.fn(),
  getExpense: vi.fn(),
  createExpense: vi.fn(),
  voidExpense: vi.fn(),
  correctExpense: vi.fn(),
  listExpenseCategories: vi.fn(),
  createExpenseCategory: vi.fn(),
  getDailyExpenseTotal: vi.fn(),
}));

vi.mock("@/lib/api/customers", () => ({
  listCustomers: vi.fn(),
}));

vi.mock("@/lib/api/orders", () => ({
  listOrders: vi.fn(),
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

describe("UX-005: Payment & Expense Workflow Completion", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(paymentsApi.listPayments).mockResolvedValue({
      items: [
        {
          id: "11111111-1111-4111-8111-111111111111",
          organization_id: "00000000-0000-0000-0000-000000000000",
          payment_number: "PAY-0001",
          amount_minor: 250000,
          currency_code: "PKR",
          channel: "cash",
          account_label: "Cash Counter",
          customer_id: "cust-1",
          order_id: "ord-1",
          external_reference: null,
          notes: null,
          status: "active",
          received_at: "2026-09-20T10:00:00Z",
          created_by_user_id: "user-1",
          voided_at: null,
          corrects_payment_id: null,
          replaced_by_payment_id: null,
          created_at: "2026-09-20T10:00:00Z",
          updated_at: "2026-09-20T10:00:00Z",
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });

    vi.mocked(paymentsApi.getDailyPaymentTotal).mockResolvedValue({
      date: "2026-09-27",
      total_minor: 250000,
      currency_code: "PKR",
      payment_count: 1,
    });

    vi.mocked(expensesApi.listExpenses).mockResolvedValue({
      items: [
        {
          id: "11111111-1111-4111-8111-111111111111",
          organization_id: "00000000-0000-0000-0000-000000000000",
          expense_category_id: "cat-1",
          amount_minor: 120000,
          currency_code: "PKR",
          occurred_at: "2026-09-20T10:00:00Z",
          payment_method: "cash",
          payee: "Stationery Mart",
          description: "Office supplies",
          status: "active",
          created_by_user_id: "user-1",
          corrects_expense_id: null,
          replaced_by_expense_id: null,
          voided_at: null,
          created_at: "2026-09-20T10:00:00Z",
          updated_at: "2026-09-20T10:00:00Z",
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });

    vi.mocked(expensesApi.listExpenseCategories).mockResolvedValue({
      items: [
        {
          id: "cat-1",
          organization_id: "00000000-0000-0000-0000-000000000000",
          name: "Supplies",
          status: "active",
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-01T00:00:00Z",
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });

    vi.mocked(expensesApi.getDailyExpenseTotal).mockResolvedValue({
      date: "2026-09-27",
      total_minor: 120000,
      currency_code: "PKR",
      expense_count: 1,
    });

    vi.mocked(customersApi.listCustomers).mockResolvedValue({
      items: [
        {
          id: "cust-1",
          organization_id: "org-1",
          name: "Ahmed Trading",
          phone: "03001234567",
          email: null,
          notes: null,
          status: "active",
          created_by_user_id: null,
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-01T00:00:00Z",
          archived_at: null,
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });

    vi.mocked(ordersApi.listOrders).mockResolvedValue({
      items: [
        {
          id: "ord-1",
          organization_id: "org-1",
          order_number: "ORD-0001",
          customer_id: "cust-1",
          ordered_at: "2026-09-20T10:00:00Z",
          status: "active",
          order_total_minor: 500000,
          currency_code: "PKR",
          created_by_user_id: null,
          corrects_order_id: null,
          replaced_by_order_id: null,
          created_at: "2026-09-20T10:00:00Z",
          updated_at: "2026-09-20T10:00:00Z",
          voided_at: null,
          items: [],
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
  });

  describe("Payments Integration & Scope Distinction", () => {
    it("renders operational distinction notice and links to Orders and Customers", async () => {
      renderWithQueryClient(<PaymentsView orgId="org-1" userRole="owner" />);

      await waitFor(() => {
        expect(screen.getByText(/operational receipt tracking:/i)).toBeInTheDocument();
        expect(screen.getByText(/not a reconciliation tool/i)).toBeInTheDocument();
      });

      const ordersLink = screen.getByRole("link", { name: /orders directory/i });
      expect(ordersLink).toHaveAttribute("href", "/workspace/org-1/orders");

      const customersLink = screen.getByRole("link", { name: /customers/i });
      expect(customersLink).toHaveAttribute("href", "/workspace/org-1/customers");
    });

    it("displays filter banner when initialCustomerId or initialOrderId is passed", async () => {
      renderWithQueryClient(
        <PaymentsView
          orgId="org-1"
          userRole="owner"
          initialOrderId="ord-1"
          initialCustomerId="cust-1"
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/filtering receipts for order:/i)).toBeInTheDocument();
        expect(screen.getByText(/ord-1/i)).toBeInTheDocument();
        expect(screen.getByText(/filtering receipts for customer:/i)).toBeInTheDocument();
        expect(screen.getByText(/cust-1/i)).toBeInTheDocument();
      });

      const clearLink = screen.getByRole("link", { name: /show all payments/i });
      expect(clearLink).toHaveAttribute("href", "/workspace/org-1/payments");
    });

    it("pre-selects orderId and customerId in PaymentCreateModal", async () => {
      renderWithQueryClient(
        <PaymentCreateModal
          isOpen={true}
          onClose={vi.fn()}
          orgId="org-1"
          initialOrderId="ord-1"
          initialCustomerId="cust-1"
        />
      );

      await waitFor(() => {
        expect(screen.getByText("Record Business Receipt")).toBeInTheDocument();
        const selectElements = screen.getAllByRole("combobox");
        // Customer select
        const customerSelect = selectElements.find(
          (el) => (el as HTMLSelectElement).value === "cust-1"
        );
        expect(customerSelect).toBeDefined();

        // Order select
        const orderSelect = selectElements.find(
          (el) => (el as HTMLSelectElement).value === "ord-1"
        );
        expect(orderSelect).toBeDefined();
      });
    });
  });

  describe("Expenses Integration & Scope Distinction", () => {
    it("renders operational distinction notice and link to Dashboard for Owner", async () => {
      renderWithQueryClient(<ExpensesView orgId="org-1" userRole="owner" />);

      await waitFor(() => {
        expect(screen.getByText(/operational outflow tracking:/i)).toBeInTheDocument();
        expect(screen.getByText(/not an accounting ledger/i)).toBeInTheDocument();
      });

      const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
      expect(dashboardLink).toHaveAttribute("href", "/workspace/org-1");
    });

    it("restricts Staff from viewing expenses", async () => {
      renderWithQueryClient(<ExpensesView orgId="org-1" userRole="staff" />);

      expect(screen.getByText("Access Restricted")).toBeInTheDocument();
      expect(
        screen.getByText(/staff roles do not have permission to view or manage operating expenses/i)
      ).toBeInTheDocument();
    });
  });
});
