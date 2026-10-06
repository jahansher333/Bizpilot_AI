import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { Payment, paymentCreateSchema, paymentCorrectSchema, paymentVoidSchema } from "@/lib/schemas/payments";
import { Order } from "@/lib/schemas/orders";
import { PaymentsView } from "@/components/payments/payments-view";
import { parseAmountMinor, pickedDateToIso, thisMonthRange, todayInput } from "@/components/finance/record-meta";
import * as paymentsApi from "@/lib/api/payments";
import * as ordersApi from "@/lib/api/orders";
import * as customersApi from "@/lib/api/customers";
import * as dashboardApi from "@/lib/api/dashboard";

vi.mock("@/lib/api/payments", () => ({ listPayments: vi.fn(), getPayment: vi.fn(), createPayment: vi.fn(), voidPayment: vi.fn(), correctPayment: vi.fn() }));
vi.mock("@/lib/api/orders", () => ({ listOrders: vi.fn(), getOrder: vi.fn() }));
vi.mock("@/lib/api/customers", () => ({ listCustomers: vi.fn() }));
vi.mock("@/lib/api/dashboard", () => ({ getDashboard: vi.fn() }));

function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const ORG = "00000000-0000-0000-0000-000000000000";
const CUSTOMER = "99999999-9999-4999-8999-999999999999";
const ORDER = "11111111-1111-4111-8111-111111111111";

function makePayment(overrides: Partial<Payment>): Payment {
  return {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    organization_id: ORG,
    payment_number: "PAY-0001",
    amount_minor: 1_000_000,
    channel: "bank_transfer",
    account_label: null,
    customer_id: CUSTOMER,
    order_id: ORDER,
    external_reference: "TID-778",
    received_at: "2026-09-24T10:42:00Z",
    status: "active",
    currency_code: "PKR",
    notes: null,
    created_by_user_id: null,
    corrects_payment_id: null,
    replaced_by_payment_id: null,
    created_at: "2026-09-24T10:42:00Z",
    updated_at: "2026-09-24T10:42:00Z",
    voided_at: null,
    ...overrides,
  };
}

const recorded = makePayment({});
const voided = makePayment({ id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", payment_number: "PAY-0002", amount_minor: 420_000, channel: "cash", customer_id: null, order_id: null, status: "voided", voided_at: "2026-09-24T11:00:00Z" });

const order: Order = {
  id: ORDER,
  organization_id: ORG,
  order_number: "ORD-0001",
  customer_id: CUSTOMER,
  ordered_at: "2026-09-24T10:00:00Z",
  status: "active",
  order_total_minor: 15_000,
  currency_code: "PKR",
  created_by_user_id: null,
  corrects_order_id: null,
  replaced_by_order_id: null,
  created_at: "2026-09-24T10:00:00Z",
  updated_at: "2026-09-24T10:00:00Z",
  voided_at: null,
  items: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(paymentsApi.listPayments).mockImplementation(async (_org, params) =>
    params?.orderId
      ? { items: [makePayment({ id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", amount_minor: 5_000, order_id: ORDER })], total: 1, limit: 100, offset: 0 }
      : { items: [recorded, voided], total: 2, limit: 50, offset: 0 }
  );
  vi.mocked(ordersApi.listOrders).mockResolvedValue({ items: [order], total: 1, limit: 100, offset: 0 });
  vi.mocked(ordersApi.getOrder).mockResolvedValue(order);
  vi.mocked(customersApi.listCustomers).mockResolvedValue({ items: [{ id: CUSTOMER, name: "Bilal General Store", status: "active" }], total: 1, limit: 100, offset: 0 } as any);
  vi.mocked(dashboardApi.getDashboard).mockImplementation(async (_org, params) => ({
    payments: params?.period === "today" ? { payment_count: 15, total_collected_minor: 6_120_000, currency_code: "PKR" } : { payment_count: 58, total_collected_minor: 25_410_000, currency_code: "PKR" },
  }) as any);
});

describe("Payment schemas and helpers", () => {
  it("only accepts the backend's payment methods", () => {
    const base = { amount_minor: 100 };
    expect(paymentCreateSchema.safeParse({ ...base, channel: "digital" }).success).toBe(true);
    expect(paymentCreateSchema.safeParse({ ...base, channel: "cheque" }).success).toBe(false);
    expect(paymentCreateSchema.safeParse({ ...base, channel: "mobile_wallet" }).success).toBe(false);
    expect(paymentCreateSchema.safeParse({ amount_minor: 0, channel: "cash" }).success).toBe(false);
  });

  it("requires a reason of at least 3 characters to void or correct", () => {
    expect(paymentVoidSchema.safeParse({ reason: "no" }).success).toBe(false);
    expect(paymentCorrectSchema.safeParse({ reason: "Typo in amount", amount_minor: 100, channel: "cash" }).success).toBe(true);
  });

  it("parses amounts, dates and month ranges", () => {
    expect(parseAmountMinor("9,120")).toBe(912_000);
    expect(parseAmountMinor("12.5")).toBe(1_250);
    expect(parseAmountMinor("0")).toBeNull();
    expect(parseAmountMinor("1.234")).toBeNull();
    const now = new Date(2026, 9, 7, 9, 30);
    expect(todayInput(now)).toBe("2026-10-07");
    expect(pickedDateToIso("2026-10-07", now)).toBeUndefined();
    expect(pickedDateToIso("2026-10-05", now)).toBe(new Date(2026, 9, 5, 12).toISOString());
    expect(thisMonthRange(now)).toEqual({ start: "2026-10-01", end: "2026-10-31" });
  });
});

describe("Payments list (R7)", () => {
  it("shows payments with customer, order, method and status, plus dashboard totals", async () => {
    renderWithQueryClient(<PaymentsView orgId={ORG} userRole="staff" />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByRole("button", { name: "PAY-0001" })).toBeInTheDocument();
    await waitFor(() => expect(within(rows[1]).getByText("Bilal General Store")).toBeInTheDocument());
    await waitFor(() => expect(within(rows[1]).getByText("ORD-0001")).toBeInTheDocument());
    expect(within(rows[1]).getByText("Bank transfer")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Recorded")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Voided")).toBeInTheDocument();

    const summary = screen.getByRole("region", { name: "Payment summary" });
    await waitFor(() => expect(within(summary).getByText("61,200")).toBeInTheDocument());
    expect(within(summary).getByText("254,100")).toBeInTheDocument();
    expect(within(summary).getByText("58")).toBeInTheDocument();
    expect(dashboardApi.getDashboard).toHaveBeenCalledWith(ORG, { period: "today" }, undefined);
  });

  it("filters by method through the API", async () => {
    renderWithQueryClient(<PaymentsView orgId={ORG} userRole="owner" />);
    await screen.findByRole("table");
    fireEvent.click(within(screen.getByRole("group", { name: "Method" })).getByRole("button", { name: "Digital wallet" }));
    await waitFor(() => expect(paymentsApi.listPayments).toHaveBeenLastCalledWith(ORG, expect.objectContaining({ channel: "digital", offset: 0 }), undefined));
  });

  it("gates detail actions by role: Owner void+correct, Manager correct, Staff neither", async () => {
    for (const [role, canCorrect, canVoid] of [
      ["owner", true, true],
      ["manager", true, false],
      ["staff", false, false],
    ] as const) {
      const view = renderWithQueryClient(<PaymentsView orgId={ORG} userRole={role} />);
      fireEvent.click(await screen.findByRole("button", { name: "PAY-0001" }));
      const sheet = screen.getByRole("dialog", { name: "PAY-0001" });
      expect(!!within(sheet).queryByRole("button", { name: /correct payment/i })).toBe(canCorrect);
      expect(!!within(sheet).queryByRole("button", { name: /void payment/i })).toBe(canVoid);
      if (role === "staff") expect(within(sheet).getByText(/only owners and managers/i)).toBeInTheDocument();
      view.unmount();
    }
  });

  it("records a digital payment with a reference", async () => {
    vi.mocked(paymentsApi.createPayment).mockResolvedValue(makePayment({ payment_number: "PAY-0042", amount_minor: 250_000, channel: "digital", order_id: null, customer_id: null }));
    renderWithQueryClient(<PaymentsView orgId={ORG} userRole="staff" />);
    fireEvent.click(screen.getAllByRole("button", { name: "Record payment" })[0]);
    const sheet = screen.getByRole("dialog", { name: "Record payment" });
    expect(within(sheet).getByLabelText("Amount")).toHaveFocus();

    fireEvent.click(within(sheet).getByRole("button", { name: "Record payment" }));
    expect(await within(sheet).findByRole("alert")).toHaveTextContent(/amount greater than 0/i);

    fireEvent.change(within(sheet).getByLabelText("Amount"), { target: { value: "2,500" } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Digital wallet" }));
    expect(within(sheet).getByText(/JazzCash, Easypaisa/)).toBeInTheDocument();
    fireEvent.change(within(sheet).getByLabelText(/reference/i), { target: { value: "TID-9001" } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Record PKR 2,500" }));

    await waitFor(() =>
      expect(paymentsApi.createPayment).toHaveBeenCalledWith(ORG, expect.objectContaining({ amount_minor: 250_000, channel: "digital", external_reference: "TID-9001", currency_code: "PKR" }), undefined, expect.any(String))
    );
    expect(vi.mocked(paymentsApi.createPayment).mock.calls[0][1]).not.toHaveProperty("received_at", expect.anything());
    expect(await within(sheet).findByRole("heading", { name: "Payment recorded" })).toBeInTheDocument();
  });

  it("opens pre-filled from an order: customer, remaining amount and an order hint", async () => {
    vi.mocked(paymentsApi.createPayment).mockResolvedValue(makePayment({ amount_minor: 10_000 }));
    renderWithQueryClient(<PaymentsView orgId={ORG} userRole="owner" initialOrderId={ORDER} startRecording />);
    const sheet = await screen.findByRole("dialog", { name: "Record payment" });
    await waitFor(() => expect(within(sheet).getByText(/Order ORD-0001 total is PKR 150 · PKR 50 paid so far/)).toBeInTheDocument());
    await waitFor(() => expect(within(sheet).getByLabelText("Amount")).toHaveValue("100"));
    await waitFor(() => expect(within(sheet).getByLabelText(/customer/i)).toHaveValue(CUSTOMER));
    // Opened to record: the list is not filtered.
    expect(paymentsApi.listPayments).toHaveBeenCalledWith(ORG, expect.objectContaining({ orderId: undefined, customerId: undefined }), undefined);

    fireEvent.click(within(sheet).getByRole("button", { name: "Record PKR 100" }));
    await waitFor(() =>
      expect(paymentsApi.createPayment).toHaveBeenCalledWith(ORG, expect.objectContaining({ amount_minor: 10_000, order_id: ORDER, customer_id: CUSTOMER }), undefined, expect.any(String))
    );
  });

  it("filters to one order when linked without record=1", async () => {
    renderWithQueryClient(<PaymentsView orgId={ORG} userRole="owner" initialOrderId={ORDER} />);
    await waitFor(() => expect(screen.getByText("order ORD-0001", { selector: "b" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Show all payments" })).toHaveAttribute("href", `/workspace/${ORG}/payments`);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("voids from the detail sheet with a required reason", async () => {
    vi.mocked(paymentsApi.voidPayment).mockResolvedValue({ ...recorded, status: "voided" });
    renderWithQueryClient(<PaymentsView orgId={ORG} userRole="owner" />);
    fireEvent.click(await screen.findByRole("button", { name: "PAY-0001" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "PAY-0001" })).getByRole("button", { name: /void payment/i }));

    const dialog = screen.getByRole("alertdialog", { name: "Void payment PAY-0001?" });
    expect(within(dialog).getByRole("button", { name: "Keep payment" })).toHaveFocus();
    fireEvent.click(within(dialog).getByRole("button", { name: "Void payment" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/at least 3 characters/i);
    fireEvent.change(within(dialog).getByLabelText(/reason/i), { target: { value: "Recorded twice" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Void payment" }));
    await waitFor(() => expect(paymentsApi.voidPayment).toHaveBeenCalledWith(ORG, recorded.id, { reason: "Recorded twice" }, undefined, expect.stringMatching(/^web-void-/)));
  });

  it("corrects a payment and opens the replacement", async () => {
    const replacement = makePayment({ id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", payment_number: "PAY-0003", amount_minor: 400_000, corrects_payment_id: recorded.id });
    vi.mocked(paymentsApi.correctPayment).mockResolvedValue(replacement);
    vi.mocked(paymentsApi.getPayment).mockResolvedValue({ ...recorded, status: "corrected", replaced_by_payment_id: replacement.id });
    renderWithQueryClient(<PaymentsView orgId={ORG} userRole="manager" />);
    fireEvent.click(await screen.findByRole("button", { name: "PAY-0001" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "PAY-0001" })).getByRole("button", { name: /correct payment/i }));

    const dialog = screen.getByRole("dialog", { name: "Correct payment PAY-0001" });
    expect(within(dialog).getByLabelText("Correct amount")).toHaveValue("10,000");
    fireEvent.change(within(dialog).getByLabelText("Correct amount"), { target: { value: "4000" } });
    fireEvent.change(within(dialog).getByLabelText(/reason/i), { target: { value: "Amount typed wrong" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save correction" }));
    await waitFor(() =>
      expect(paymentsApi.correctPayment).toHaveBeenCalledWith(
        ORG,
        recorded.id,
        expect.objectContaining({ reason: "Amount typed wrong", amount_minor: 400_000, channel: "bank_transfer", customer_id: CUSTOMER, order_id: ORDER, external_reference: "TID-778" }),
        undefined,
        expect.stringMatching(/^web-correct-/)
      )
    );
    expect(await screen.findByRole("dialog", { name: "PAY-0003" })).toBeInTheDocument();
  });
});
