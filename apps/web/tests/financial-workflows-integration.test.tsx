import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { Order } from "@/lib/schemas/orders";
import { OrderDetail } from "@/components/orders/order-detail";
import { OrderPos } from "@/components/orders/order-pos";
import { CustomerDetail } from "@/components/customers/customer-detail";
import { PaymentsView } from "@/components/payments/payments-view";
import * as ordersApi from "@/lib/api/orders";
import * as paymentsApi from "@/lib/api/payments";
import * as customersApi from "@/lib/api/customers";
import * as catalogApi from "@/lib/api/catalog";
import * as inventoryApi from "@/lib/api/inventory";
import * as dashboardApi from "@/lib/api/dashboard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/lib/api/orders", () => ({ listOrders: vi.fn(), getOrder: vi.fn(), createOrder: vi.fn() }));
vi.mock("@/lib/api/payments", () => ({ listPayments: vi.fn(), getPayment: vi.fn(), createPayment: vi.fn() }));
vi.mock("@/lib/api/customers", () => ({ listCustomers: vi.fn(), getCustomer: vi.fn(), getCustomerBalances: vi.fn() }));
vi.mock("@/lib/api/catalog", () => ({ listProducts: vi.fn(), listCategories: vi.fn() }));
vi.mock("@/lib/api/inventory", () => ({ fetchBalances: vi.fn() }));
vi.mock("@/lib/api/dashboard", () => ({ getDashboard: vi.fn() }));

const ORG = "00000000-0000-0000-0000-000000000000";
const CUSTOMER = "99999999-9999-4999-8999-999999999999";
const PRODUCT = "33333333-3333-4333-8333-333333333333";

const order: Order = {
  id: "11111111-1111-4111-8111-111111111111",
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

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: Infinity } } });
  const view = (ui: React.ReactElement) => render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
  return { client, view };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(ordersApi.getOrder).mockResolvedValue(order);
  vi.mocked(ordersApi.listOrders).mockResolvedValue({ items: [order], total: 1, limit: 100, offset: 0 });
  vi.mocked(paymentsApi.listPayments).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
  vi.mocked(customersApi.listCustomers).mockResolvedValue({ items: [{ id: CUSTOMER, name: "Bilal General Store", status: "active" }], total: 1, limit: 100, offset: 0 } as any);
  vi.mocked(customersApi.getCustomer).mockResolvedValue({ id: CUSTOMER, name: "Bilal General Store", status: "active", phone: null, email: null, notes: null, created_at: "2026-01-01T00:00:00Z" } as any);
  vi.mocked(customersApi.getCustomerBalances).mockResolvedValue({ currency_code: "PKR", items: [], customers_with_orders: 0, customers_with_balance: 0, outstanding_minor: 0 });
  vi.mocked(catalogApi.listProducts).mockResolvedValue({ items: [{ id: PRODUCT, organization_id: ORG, category_id: null, code: "RIC-005", name: "Basmati Rice 5kg", base_unit: "bag", default_price_minor: 15_000, currency_code: "PKR", status: "active" }], total: 1, limit: 100, offset: 0 } as any);
  vi.mocked(catalogApi.listCategories).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
  vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({ items: [{ id: "b1", organization_id: ORG, product_id: PRODUCT, on_hand_quantity: 5, version: 1, updated_at: "" }], total: 1, limit: 100, offset: 0 });
  vi.mocked(dashboardApi.getDashboard).mockResolvedValue({ payments: { payment_count: 0, total_collected_minor: 0, currency_code: "PKR" } } as any);
});

describe("Record payment from orders and customers (R7)", () => {
  it("order detail links to a pre-filled payment form", async () => {
    setup().view(<OrderDetail orgId={ORG} orderId={order.id} userRole="staff" />);
    expect(await screen.findByRole("link", { name: "Record payment" })).toHaveAttribute("href", `/workspace/${ORG}/payments?record=1&orderId=${order.id}&customerId=${CUSTOMER}`);
  });

  it("the POS success dialog links to a pre-filled payment form", async () => {
    vi.mocked(ordersApi.createOrder).mockResolvedValue({ ...order, id: "77777777-7777-4777-8777-777777777777", order_number: "ORD-0042" });
    setup().view(<OrderPos orgId={ORG} initialCustomerId={CUSTOMER} />);
    fireEvent.click(await screen.findByRole("button", { name: /Basmati Rice 5kg, PKR 150/ }));
    fireEvent.click(screen.getByRole("button", { name: /complete order/i }));
    const done = await screen.findByRole("dialog", { name: "Order ORD-0042 completed" });
    expect(within(done).getByRole("link", { name: "Record payment" })).toHaveAttribute("href", `/workspace/${ORG}/payments?record=1&orderId=77777777-7777-4777-8777-777777777777&customerId=${CUSTOMER}`);
  });

  it("customer detail links to a payment form for that customer", async () => {
    setup().view(<CustomerDetail orgId={ORG} customerId={CUSTOMER} userRole="owner" />);
    expect(await screen.findByRole("link", { name: "Record payment" })).toHaveAttribute("href", `/workspace/${ORG}/payments?record=1&customerId=${CUSTOMER}`);
  });

  it("recording a payment refreshes the dashboard and customer balances", async () => {
    vi.mocked(paymentsApi.createPayment).mockResolvedValue({ id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", payment_number: "PAY-0001", amount_minor: 15_000, channel: "cash", currency_code: "PKR", status: "active" } as any);
    const { client, view } = setup();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    view(<PaymentsView orgId={ORG} userRole="staff" initialCustomerId={CUSTOMER} startRecording />);
    const sheet = await screen.findByRole("dialog", { name: "Record payment" });
    fireEvent.change(within(sheet).getByLabelText("Amount"), { target: { value: "150" } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Record PKR 150" }));
    await waitFor(() => expect(paymentsApi.createPayment).toHaveBeenCalledWith(ORG, expect.objectContaining({ customer_id: CUSTOMER, amount_minor: 15_000 }), undefined, expect.any(String)));
    const keys = invalidate.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toEqual(expect.arrayContaining([JSON.stringify(["payments", ORG]), JSON.stringify(["dashboard", ORG]), JSON.stringify(["customers", ORG, "balances"])]));
  });
});
