import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import {
  formatMoney,
  toMinorUnits,
  paymentCorrectSchema,
  paymentCreateSchema,
  paymentVoidSchema,
  Payment,
} from "@/lib/schemas/payments";
import { PaymentsView } from "@/components/payments/payments-view";
import { PaymentDetailModal } from "@/components/payments/payment-detail-modal";
import { PaymentVoidModal } from "@/components/payments/payment-void-modal";
import { PaymentCorrectModal } from "@/components/payments/payment-correct-modal";
import * as paymentsApi from "@/lib/api/payments";
import * as customersApi from "@/lib/api/customers";
import * as ordersApi from "@/lib/api/orders";

vi.mock("@/lib/api/payments", () => ({
  listPayments: vi.fn(),
  getPayment: vi.fn(),
  getDailyPaymentTotal: vi.fn(),
  createPayment: vi.fn(),
  voidPayment: vi.fn(),
  correctPayment: vi.fn(),
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

const mockPayments: Payment[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    payment_number: "PAY-0001",
    amount_minor: 25000,
    channel: "cash",
    account_label: "Cash Drawer 1",
    customer_id: "99999999-9999-4999-8999-999999999999",
    order_id: "88888888-8888-4888-8888-888888888888",
    external_reference: null,
    received_at: "2026-09-24T10:00:00Z",
    status: "active",
    currency_code: "PKR",
    notes: "Counter sale payment",
    created_by_user_id: null,
    corrects_payment_id: null,
    replaced_by_payment_id: null,
    created_at: "2026-09-24T10:00:00Z",
    updated_at: "2026-09-24T10:00:00Z",
    voided_at: null,
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    organization_id: "00000000-0000-0000-0000-000000000000",
    payment_number: "PAY-0002",
    amount_minor: 50000,
    channel: "bank_transfer",
    account_label: "Meezan Bank",
    customer_id: null,
    order_id: null,
    external_reference: "TXN-90214",
    received_at: "2026-09-24T11:00:00Z",
    status: "voided",
    currency_code: "PKR",
    notes: "Deposit receipt",
    created_by_user_id: null,
    corrects_payment_id: null,
    replaced_by_payment_id: null,
    created_at: "2026-09-24T11:00:00Z",
    updated_at: "2026-09-24T11:30:00Z",
    voided_at: "2026-09-24T11:30:00Z",
  },
];

describe("Payments UI & Domain Schemas (PAY-004)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(customersApi.listCustomers).mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    });
    vi.mocked(ordersApi.listOrders).mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    });
  });

  it("validates paymentCreateSchema rejecting non-positive amounts or invalid channels", () => {
    const zeroAmount = paymentCreateSchema.safeParse({
      amount_minor: 0,
      channel: "cash",
    });
    expect(zeroAmount.success).toBe(false);

    const negativeAmount = paymentCreateSchema.safeParse({
      amount_minor: -500,
      channel: "cash",
    });
    expect(negativeAmount.success).toBe(false);

    const invalidChannel = paymentCreateSchema.safeParse({
      amount_minor: 1000,
      channel: "crypto",
    });
    expect(invalidChannel.success).toBe(false);

    const validPayment = paymentCreateSchema.safeParse({
      amount_minor: 15000,
      channel: "bank_transfer",
      account_label: "Main Account",
    });
    expect(validPayment.success).toBe(true);
  });

  it("validates paymentVoidSchema and paymentCorrectSchema requiring minimum 3 char reason", () => {
    expect(paymentVoidSchema.safeParse({ reason: "no" }).success).toBe(false);
    expect(paymentVoidSchema.safeParse({ reason: "Cheque bounced" }).success).toBe(true);

    expect(
      paymentCorrectSchema.safeParse({
        reason: "ab",
        amount_minor: 1000,
        channel: "cash",
      }).success
    ).toBe(false);

    expect(
      paymentCorrectSchema.safeParse({
        reason: "Corrected customer reference",
        amount_minor: 12000,
        channel: "mobile_wallet",
      }).success
    ).toBe(true);
  });

  it("formats minor units and converts major units accurately", () => {
    expect(formatMoney(25000, "PKR")).toBe("Rs. 250.00");
    expect(formatMoney(0, "PKR")).toBe("Rs. 0.00");
    expect(toMinorUnits(150.5)).toBe(15050);
  });

  it("renders payments list with totals, channels, and status badges", async () => {
    vi.mocked(paymentsApi.listPayments).mockResolvedValue({
      items: mockPayments,
      total: 2,
      limit: 100,
      offset: 0,
    });
    vi.mocked(paymentsApi.getDailyPaymentTotal).mockResolvedValue({
      date: "2026-09-24",
      total_minor: 25000,
      payment_count: 1,
      currency_code: "PKR",
    });

    renderWithQueryClient(
      <PaymentsView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />
    );

    expect(screen.getByText("Loading payments...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("PAY-0001")).toBeInTheDocument();
      expect(screen.getByText("PAY-0002")).toBeInTheDocument();
      expect(screen.getAllByText("Rs. 250.00").length).toBeGreaterThan(0);
      expect(screen.getByText("Rs. 500.00")).toBeInTheDocument();
    });
  });

  it("enforces role-based action buttons in payments table", async () => {
    vi.mocked(paymentsApi.listPayments).mockResolvedValue({
      items: mockPayments,
      total: 2,
      limit: 100,
      offset: 0,
    });
    vi.mocked(paymentsApi.getDailyPaymentTotal).mockResolvedValue({
      date: "2026-09-24",
      total_minor: 25000,
      payment_count: 1,
      currency_code: "PKR",
    });

    // Test as Owner: has Void and Correct buttons on active payment
    const { unmount } = renderWithQueryClient(
      <PaymentsView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />
    );

    await waitFor(() => {
      expect(screen.getByText("PAY-0001")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Void" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correct" })).toBeInTheDocument();
    unmount();

    // Test as Manager: has Correct button, but Void button is NOT rendered
    const { unmount: unmountManager } = renderWithQueryClient(
      <PaymentsView orgId="00000000-0000-0000-0000-000000000000" userRole="manager" />
    );

    await waitFor(() => {
      expect(screen.getByText("PAY-0001")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "Void" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correct" })).toBeInTheDocument();
    unmountManager();

    // Test as Staff: read-only actions (only View, neither Void nor Correct)
    renderWithQueryClient(
      <PaymentsView orgId="00000000-0000-0000-0000-000000000000" userRole="staff" />
    );

    await waitFor(() => {
      expect(screen.getByText("PAY-0001")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "Void" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Correct" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "View" }).length).toBeGreaterThan(0);
    expect(screen.getByText(/Staff Permissions:/i)).toBeInTheDocument();
  });

  it("renders PaymentDetailModal with metadata and amount", () => {
    const handleClose = vi.fn();
    render(
      <PaymentDetailModal
        isOpen={true}
        onClose={handleClose}
        payment={mockPayments[0]}
      />
    );

    expect(screen.getByText("PAY-0001")).toBeInTheDocument();
    expect(screen.getByText("Rs. 250.00")).toBeInTheDocument();
    expect(screen.getByText("Cash Drawer 1")).toBeInTheDocument();
    expect(screen.getByText("Counter sale payment")).toBeInTheDocument();

    const closeButtons = screen.getAllByRole("button", { name: /close/i });
    fireEvent.click(closeButtons[0]);
    expect(handleClose).toHaveBeenCalled();
  });

  it("submits PaymentVoidModal with mandatory reason", async () => {
    const handleClose = vi.fn();
    vi.mocked(paymentsApi.voidPayment).mockResolvedValue({
      ...mockPayments[0],
      status: "voided",
      voided_at: "2026-09-24T12:00:00Z",
    });

    renderWithQueryClient(
      <PaymentVoidModal
        isOpen={true}
        onClose={handleClose}
        payment={mockPayments[0]}
        orgId="00000000-0000-0000-0000-000000000000"
      />
    );

    expect(screen.getByText(/Void Payment PAY-0001/i)).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/Dishonored cheque/i);
    fireEvent.change(textarea, { target: { value: "Customer cheque bounced" } });

    const submitBtn = screen.getByRole("button", { name: "Confirm Void" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(paymentsApi.voidPayment).toHaveBeenCalledWith(
        "00000000-0000-0000-0000-000000000000",
        mockPayments[0].id,
        { reason: "Customer cheque bounced" },
        undefined,
        expect.any(String)
      );
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("submits PaymentCorrectModal with replacement values and reason", async () => {
    const handleClose = vi.fn();
    vi.mocked(paymentsApi.correctPayment).mockResolvedValue({
      ...mockPayments[0],
      status: "corrected",
      replaced_by_payment_id: "33333333-3333-4333-8333-333333333333",
    });

    renderWithQueryClient(
      <PaymentCorrectModal
        isOpen={true}
        onClose={handleClose}
        payment={mockPayments[0]}
        orgId="00000000-0000-0000-0000-000000000000"
      />
    );

    expect(screen.getByText(/Correct Payment PAY-0001/i)).toBeInTheDocument();

    const reasonInput = screen.getByPlaceholderText(/Correcting mistyped cash amount/i);
    fireEvent.change(reasonInput, { target: { value: "Received 300 instead of 250" } });

    const submitBtn = screen.getByRole("button", { name: "Apply Correction" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(paymentsApi.correctPayment).toHaveBeenCalledWith(
        "00000000-0000-0000-0000-000000000000",
        mockPayments[0].id,
        expect.objectContaining({
          reason: "Received 300 instead of 250",
          amount_minor: 25000,
          channel: "cash",
        }),
        undefined,
        expect.any(String)
      );
      expect(handleClose).toHaveBeenCalled();
    });
  });
});
