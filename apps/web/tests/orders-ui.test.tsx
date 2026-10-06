import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { formatMoney, orderCorrectSchema, orderCreateSchema, orderVoidSchema, Order } from "@/lib/schemas/orders";
import { OrdersView } from "@/components/orders/orders-view";
import { OrderPos } from "@/components/orders/order-pos";
import { OrderDetail } from "@/components/orders/order-detail";
import * as ordersApi from "@/lib/api/orders";
import * as catalogApi from "@/lib/api/catalog";
import * as customersApi from "@/lib/api/customers";
import * as inventoryApi from "@/lib/api/inventory";
import * as dashboardApi from "@/lib/api/dashboard";
import * as paymentsApi from "@/lib/api/payments";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

vi.mock("@/lib/api/orders", () => ({
  listOrders: vi.fn(),
  getOrder: vi.fn(),
  createOrder: vi.fn(),
  voidOrder: vi.fn(),
  correctOrder: vi.fn(),
}));
vi.mock("@/lib/api/catalog", () => ({ listProducts: vi.fn(), listCategories: vi.fn() }));
vi.mock("@/lib/api/customers", () => ({ listCustomers: vi.fn() }));
vi.mock("@/lib/api/inventory", () => ({ fetchBalances: vi.fn() }));
vi.mock("@/lib/api/dashboard", () => ({ getDashboard: vi.fn() }));
vi.mock("@/lib/api/payments", () => ({ listPayments: vi.fn() }));

function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const ORG = "00000000-0000-0000-0000-000000000000";
const CUSTOMER = "99999999-9999-4999-8999-999999999999";
const RICE = "33333333-3333-4333-8333-333333333333";
const OIL = "55555555-5555-4555-8555-555555555555";

function makeOrder(overrides: Partial<Order>): Order {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: ORG,
    order_number: "ORD-0001",
    customer_id: CUSTOMER,
    ordered_at: "2026-09-24T10:00:00Z",
    status: "active",
    order_total_minor: 15000,
    currency_code: "PKR",
    created_by_user_id: null,
    corrects_order_id: null,
    replaced_by_order_id: null,
    created_at: "2026-09-24T10:00:00Z",
    updated_at: "2026-09-24T10:00:00Z",
    voided_at: null,
    items: [
      {
        id: "22222222-2222-4222-8222-222222222222",
        order_id: "11111111-1111-4111-8111-111111111111",
        product_id: RICE,
        product_name_snapshot: "Basmati Rice 5kg",
        product_code_snapshot: "RIC-005",
        unit_snapshot: "bag",
        quantity: 5,
        unit_price_minor: 3000,
        line_total_minor: 15000,
        currency_code: "PKR",
        created_at: "2026-09-24T10:00:00Z",
      },
    ],
    ...overrides,
  };
}

const activeOrder = makeOrder({});
const voidedOrder = makeOrder({
  id: "44444444-4444-4444-8444-444444444444",
  order_number: "ORD-0002",
  customer_id: null,
  status: "voided",
  order_total_minor: 6000,
  voided_at: "2026-09-24T11:30:00Z",
  items: [],
});

function product(id: string, code: string, name: string, price: number) {
  return { id, organization_id: ORG, category_id: null, code, name, base_unit: "bag", default_price_minor: price, currency_code: "PKR", status: "active", created_by_user_id: null, created_at: "", updated_at: "", archived_at: null };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(ordersApi.listOrders).mockResolvedValue({ items: [activeOrder, voidedOrder], total: 2, limit: 50, offset: 0 });
  vi.mocked(customersApi.listCustomers).mockResolvedValue({ items: [{ id: CUSTOMER, name: "Bilal General Store", phone: "0300 555 0142", status: "active" }], total: 1, limit: 100, offset: 0 } as any);
  vi.mocked(catalogApi.listProducts).mockResolvedValue({ items: [product(RICE, "RIC-005", "Basmati Rice 5kg", 245000), product(OIL, "OIL-005", "Cooking Oil 5L", 315000)], total: 2, limit: 100, offset: 0 } as any);
  vi.mocked(catalogApi.listCategories).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
  vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({ items: [{ id: "b1", organization_id: ORG, product_id: RICE, on_hand_quantity: 2, version: 1, updated_at: "" }], total: 1, limit: 100, offset: 0 });
  vi.mocked(dashboardApi.getDashboard).mockResolvedValue({ sales: { order_count: 24, total_sales_minor: 8450000, currency_code: "PKR" } } as any);
  vi.mocked(paymentsApi.listPayments).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
});

describe("Order schemas", () => {
  it("rejects empty line items or non-positive quantity", () => {
    expect(orderCreateSchema.safeParse({ items: [] }).success).toBe(false);
    expect(orderCreateSchema.safeParse({ items: [{ product_id: RICE, quantity: 0, unit_price_minor: 100 }] }).success).toBe(false);
    expect(orderCreateSchema.safeParse({ items: [{ product_id: RICE, quantity: 2, unit_price_minor: 5000 }] }).success).toBe(true);
  });

  it("requires a reason of at least 3 characters to void or correct", () => {
    expect(orderVoidSchema.safeParse({ reason: "no" }).success).toBe(false);
    expect(orderVoidSchema.safeParse({ reason: "Customer requested" }).success).toBe(true);
    const items = [{ product_id: RICE, quantity: 1, unit_price_minor: 1000 }];
    expect(orderCorrectSchema.safeParse({ reason: "ab", items }).success).toBe(false);
    expect(orderCorrectSchema.safeParse({ reason: "Adjusted per customer", items }).success).toBe(true);
  });

  it("formats legacy money strings", () => {
    expect(formatMoney(15000, "PKR")).toBe("Rs. 150.00");
  });
});

describe("Orders list (R6)", () => {
  it("renders orders with customer names, design status labels and detail links", async () => {
    renderWithQueryClient(<OrdersView orgId={ORG} userRole="owner" />);
    expect(screen.getByLabelText("Loading orders")).toBeInTheDocument();

    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByRole("link", { name: "ORD-0001" })).toHaveAttribute("href", `/workspace/${ORG}/orders/${activeOrder.id}`);
    await waitFor(() => expect(within(rows[1]).getByText("Bilal General Store")).toBeInTheDocument());
    expect(within(rows[1]).getByText("Completed")).toBeInTheDocument();
    expect(within(rows[1]).getByText("150")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Walk-in customer")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Voided")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new order/i })).toHaveAttribute("href", `/workspace/${ORG}/orders/new`);
  });

  it("shows today's sales cards to Owners from the dashboard summary", async () => {
    renderWithQueryClient(<OrdersView orgId={ORG} userRole="owner" />);
    const cards = await screen.findByRole("region", { name: "Orders today" });
    await waitFor(() => expect(within(cards).getByText("24")).toBeInTheDocument());
    expect(within(cards).getByText("84,500")).toBeInTheDocument();
    expect(dashboardApi.getDashboard).toHaveBeenCalledWith(ORG, { period: "today" }, undefined);
  });

  it("gates row actions by role: Owner correct+void, Manager correct, Staff neither and no sales cards", async () => {
    const { unmount } = renderWithQueryClient(<OrdersView orgId={ORG} userRole="owner" />);
    await screen.findByRole("link", { name: "ORD-0001" });
    expect(screen.getByRole("link", { name: "Correct ORD-0001" })).toHaveAttribute("href", `/workspace/${ORG}/orders/${activeOrder.id}?action=correct`);
    expect(screen.getByRole("button", { name: "Void ORD-0001" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Void ORD-0002" })).not.toBeInTheDocument();
    unmount();

    const manager = renderWithQueryClient(<OrdersView orgId={ORG} userRole="manager" />);
    await screen.findByRole("link", { name: "ORD-0001" });
    expect(screen.getByRole("link", { name: "Correct ORD-0001" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Void ORD-0001" })).not.toBeInTheDocument();
    manager.unmount();

    vi.mocked(dashboardApi.getDashboard).mockClear();
    renderWithQueryClient(<OrdersView orgId={ORG} userRole="staff" />);
    await screen.findByRole("link", { name: "ORD-0001" });
    expect(screen.queryByRole("link", { name: "Correct ORD-0001" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Void ORD-0001" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Orders today" })).not.toBeInTheDocument();
    expect(dashboardApi.getDashboard).not.toHaveBeenCalled();
  });

  it("filters by status through the API", async () => {
    renderWithQueryClient(<OrdersView orgId={ORG} userRole="owner" />);
    await screen.findByRole("link", { name: "ORD-0001" });
    fireEvent.click(screen.getByRole("button", { name: "Voided" }));
    await waitFor(() => expect(ordersApi.listOrders).toHaveBeenLastCalledWith(ORG, expect.objectContaining({ status: "voided", offset: 0 }), undefined));
  });

  it("voids from the list with a required reason and an idempotency key", async () => {
    vi.mocked(ordersApi.voidOrder).mockResolvedValue({ ...activeOrder, status: "voided" });
    renderWithQueryClient(<OrdersView orgId={ORG} userRole="owner" />);
    fireEvent.click(await screen.findByRole("button", { name: "Void ORD-0001" }));

    const dialog = screen.getByRole("alertdialog", { name: "Void order ORD-0001?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Void order" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/at least 3 characters/i);
    expect(ordersApi.voidOrder).not.toHaveBeenCalled();

    fireEvent.change(within(dialog).getByLabelText(/reason/i), { target: { value: "Duplicate entry" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Void order" }));
    await waitFor(() =>
      expect(ordersApi.voidOrder).toHaveBeenCalledWith(ORG, activeOrder.id, { reason: "Duplicate entry" }, undefined, expect.stringMatching(/^web-void-/))
    );
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  });

  it("shows a customer filter banner when opened from a customer", async () => {
    renderWithQueryClient(<OrdersView orgId={ORG} userRole="owner" initialCustomerId={CUSTOMER} />);
    await waitFor(() => expect(screen.getByText("Bilal General Store", { selector: "b" })).toBeInTheDocument());
    expect(ordersApi.listOrders).toHaveBeenCalledWith(ORG, expect.objectContaining({ customerId: CUSTOMER }), undefined);
    expect(screen.getByRole("link", { name: "Show all orders" })).toHaveAttribute("href", `/workspace/${ORG}/orders`);
    expect(screen.getByRole("link", { name: /new order/i })).toHaveAttribute("href", `/workspace/${ORG}/orders/new?customerId=${CUSTOMER}`);
  });
});

describe("Create order POS (R6)", () => {
  it("adds products up to available stock and blocks out-of-stock products", async () => {
    renderWithQueryClient(<OrderPos orgId={ORG} />);
    const rice = await screen.findByRole("button", { name: /Basmati Rice 5kg, PKR 2,450, 2 in stock/ });
    const oil = await screen.findByRole("button", { name: /Cooking Oil 5L, .*out of stock/ });
    expect(oil).toBeDisabled();
    expect(screen.getByRole("button", { name: /complete order/i })).toBeDisabled();

    fireEvent.click(rice);
    fireEvent.click(rice);
    expect(rice).toBeDisabled();
    const cart = screen.getByRole("list", { name: "Cart items" });
    expect(within(cart).getByLabelText("Quantity of Basmati Rice 5kg")).toHaveTextContent("2");
    expect(within(cart).getByRole("button", { name: "Increase Basmati Rice 5kg" })).toBeDisabled();
    expect(within(cart).getByText("Max · 2 in stock")).toBeInTheDocument();
  });

  it("completes the order with the selected customer and shows the success dialog", async () => {
    vi.mocked(ordersApi.createOrder).mockResolvedValue(makeOrder({ id: "77777777-7777-4777-8777-777777777777", order_number: "ORD-0042", order_total_minor: 245000 }));
    renderWithQueryClient(<OrderPos orgId={ORG} initialCustomerId={CUSTOMER} />);
    fireEvent.click(await screen.findByRole("button", { name: /Basmati Rice 5kg, PKR 2,450/ }));
    await waitFor(() => expect(screen.getByLabelText("Customer")).toHaveValue(CUSTOMER));

    fireEvent.click(screen.getByRole("button", { name: /complete order/i }));
    await waitFor(() =>
      expect(ordersApi.createOrder).toHaveBeenCalledWith(
        ORG,
        { customer_id: CUSTOMER, items: [{ product_id: RICE, quantity: 1, unit_price_minor: 245000 }], currency_code: "PKR" },
        undefined,
        expect.any(String)
      )
    );
    const done = await screen.findByRole("dialog", { name: "Order ORD-0042 completed" });
    expect(within(done).getByRole("link", { name: "View order" })).toHaveAttribute("href", `/workspace/${ORG}/orders/77777777-7777-4777-8777-777777777777`);
  });

  it("reuses the idempotency key when retrying the same cart and shows backend errors", async () => {
    vi.mocked(ordersApi.createOrder).mockRejectedValueOnce(new Error("Insufficient stock for product 'Basmati Rice 5kg'. Available: 0, Requested: 1"));
    renderWithQueryClient(<OrderPos orgId={ORG} />);
    fireEvent.click(await screen.findByRole("button", { name: /Basmati Rice 5kg, PKR 2,450/ }));
    fireEvent.click(screen.getByRole("button", { name: /complete order/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Insufficient stock/);

    vi.mocked(ordersApi.createOrder).mockResolvedValueOnce(makeOrder({ order_number: "ORD-0043" }));
    fireEvent.click(screen.getByRole("button", { name: /complete order/i }));
    await waitFor(() => expect(ordersApi.createOrder).toHaveBeenCalledTimes(2));
    const keys = vi.mocked(ordersApi.createOrder).mock.calls.map((c) => c[3]);
    expect(keys[0]).toBe(keys[1]);
  });

  it("lets the seller change the unit price", async () => {
    vi.mocked(ordersApi.createOrder).mockResolvedValue(makeOrder({}));
    renderWithQueryClient(<OrderPos orgId={ORG} />);
    fireEvent.click(await screen.findByRole("button", { name: /Basmati Rice 5kg, PKR 2,450/ }));
    fireEvent.change(screen.getByLabelText("Unit price of Basmati Rice 5kg"), { target: { value: "2400.50" } });
    fireEvent.click(screen.getByRole("button", { name: /complete order/i }));
    await waitFor(() =>
      expect(ordersApi.createOrder).toHaveBeenCalledWith(ORG, expect.objectContaining({ items: [{ product_id: RICE, quantity: 1, unit_price_minor: 240050 }] }), undefined, expect.any(String))
    );
  });
});

describe("Order detail & correction (R6)", () => {
  it("shows items, related payments and role-gated actions", async () => {
    vi.mocked(ordersApi.getOrder).mockResolvedValue(activeOrder);
    vi.mocked(paymentsApi.listPayments).mockResolvedValue({
      items: [{ id: "p1", organization_id: ORG, payment_number: "PAY-0412", amount_minor: 15000, channel: "cash", order_id: activeOrder.id, received_at: "2026-09-24T10:42:00Z", status: "active", currency_code: "PKR", created_at: "", updated_at: "" }],
      total: 1,
      limit: 100,
      offset: 0,
    } as any);
    const { unmount } = renderWithQueryClient(<OrderDetail orgId={ORG} orderId={activeOrder.id} userRole="owner" />);
    expect(await screen.findByRole("heading", { name: "Order #ORD-0001" })).toBeInTheDocument();
    expect(screen.getByText("Basmati Rice 5kg")).toBeInTheDocument();
    expect(await screen.findByText("PAY-0412")).toBeInTheDocument();
    expect(screen.getByText("Paid in full")).toBeInTheDocument();
    expect(paymentsApi.listPayments).toHaveBeenCalledWith(ORG, expect.objectContaining({ orderId: activeOrder.id }), undefined);
    expect(screen.getByRole("button", { name: /void order/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /correct order/i })).toBeInTheDocument();
    unmount();

    renderWithQueryClient(<OrderDetail orgId={ORG} orderId={activeOrder.id} userRole="staff" />);
    await screen.findByRole("heading", { name: "Order #ORD-0001" });
    expect(screen.queryByRole("button", { name: /void order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /correct order/i })).not.toBeInTheDocument();
    expect(screen.getByText(/only owners and managers can correct/i)).toBeInTheDocument();
  });

  it("links a corrected original to its replacement", async () => {
    const replacementId = "88888888-8888-4888-8888-888888888888";
    vi.mocked(ordersApi.getOrder).mockImplementation(async (_org, id) =>
      id === replacementId
        ? makeOrder({ id: replacementId, order_number: "ORD-0009", corrects_order_id: activeOrder.id })
        : makeOrder({ status: "corrected", replaced_by_order_id: replacementId })
    );
    renderWithQueryClient(<OrderDetail orgId={ORG} orderId={activeOrder.id} userRole="owner" />);
    expect(await screen.findByText(/This order was corrected/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Open ORD-0009" })).toHaveAttribute("href", `/workspace/${ORG}/orders/${replacementId}`);
    expect(screen.queryByRole("button", { name: /correct order/i })).not.toBeInTheDocument();
  });

  it("corrects an order: edit quantity, give a reason, review, submit, open the replacement", async () => {
    vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({ items: [{ id: "b1", organization_id: ORG, product_id: RICE, on_hand_quantity: 0, version: 1, updated_at: "" }], total: 1, limit: 100, offset: 0 });
    vi.mocked(ordersApi.getOrder).mockResolvedValue(activeOrder);
    const replacement = makeOrder({ id: "66666666-6666-4666-8666-666666666666", order_number: "ORD-0010", corrects_order_id: activeOrder.id });
    vi.mocked(ordersApi.correctOrder).mockResolvedValue(replacement);

    renderWithQueryClient(<OrderDetail orgId={ORG} orderId={activeOrder.id} userRole="manager" initialAction="correct" />);
    expect(await screen.findByRole("heading", { name: "Correct order ORD-0001" })).toBeInTheDocument();
    const review = screen.getByRole("button", { name: "Review correction" });
    expect(review).toBeDisabled();

    // All 5 units can be re-sold: the original's stock is returned before the replacement is deducted.
    await waitFor(() => expect(screen.getByRole("button", { name: "Increase Basmati Rice 5kg" })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Decrease Basmati Rice 5kg" }));
    expect(screen.getByText("1 change")).toBeInTheDocument();
    expect(screen.getByText(/1 unit back in stock/)).toBeInTheDocument();

    fireEvent.click(review);
    expect(await screen.findByRole("alert")).toHaveTextContent(/at least 3 characters/i);
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "Customer took 4 bags" } });
    fireEvent.click(review);

    const confirm = await screen.findByRole("alertdialog", { name: "Submit correction?" });
    fireEvent.click(within(confirm).getByRole("button", { name: "Submit correction" }));
    await waitFor(() =>
      expect(ordersApi.correctOrder).toHaveBeenCalledWith(
        ORG,
        activeOrder.id,
        { reason: "Customer took 4 bags", customer_id: CUSTOMER, items: [{ product_id: RICE, quantity: 4, unit_price_minor: 3000 }], currency_code: "PKR" },
        undefined,
        expect.stringMatching(/^web-correct-/)
      )
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith(`/workspace/${ORG}/orders/${replacement.id}`));
  });

  it("ignores ?action=correct for Staff", async () => {
    vi.mocked(ordersApi.getOrder).mockResolvedValue(activeOrder);
    renderWithQueryClient(<OrderDetail orgId={ORG} orderId={activeOrder.id} userRole="staff" initialAction="correct" />);
    expect(await screen.findByRole("heading", { name: "Order #ORD-0001" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /correct order/i })).not.toBeInTheDocument();
  });
});
