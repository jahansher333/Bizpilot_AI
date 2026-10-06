import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { OrderPos } from "@/components/orders/order-pos";
import * as ordersApi from "@/lib/api/orders";
import * as catalogApi from "@/lib/api/catalog";
import * as customersApi from "@/lib/api/customers";
import * as inventoryApi from "@/lib/api/inventory";

vi.mock("@/lib/api/orders", () => ({ createOrder: vi.fn() }));
vi.mock("@/lib/api/catalog", () => ({ listProducts: vi.fn(), listCategories: vi.fn() }));
vi.mock("@/lib/api/customers", () => ({ listCustomers: vi.fn() }));
vi.mock("@/lib/api/inventory", () => ({ fetchBalances: vi.fn() }));

const ORG = "00000000-0000-0000-0000-000000000000";
const RICE = "33333333-3333-4333-8333-333333333333";
const CUSTOMER = "99999999-9999-4999-8999-999999999999";

function setPhone(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({ matches, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })) as any;
}

function renderPos() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <OrderPos orgId={ORG} />
    </QueryClientProvider>
  );
}

const original = window.matchMedia;
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(catalogApi.listProducts).mockResolvedValue({ items: [{ id: RICE, organization_id: ORG, category_id: null, code: "RIC-005", name: "Basmati Rice 5kg", base_unit: "bag", default_price_minor: 245_000, currency_code: "PKR", status: "active" }], total: 1, limit: 100, offset: 0 } as any);
  vi.mocked(catalogApi.listCategories).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
  vi.mocked(customersApi.listCustomers).mockResolvedValue({ items: [{ id: CUSTOMER, name: "Bilal General Store", phone: "0300 555 0142", status: "active" }], total: 1, limit: 100, offset: 0 } as any);
  vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({ items: [{ id: "b1", organization_id: ORG, product_id: RICE, on_hand_quantity: 3, version: 1, updated_at: "" }], total: 1, limit: 100, offset: 0 });
});
afterEach(() => {
  window.matchMedia = original;
});

describe("Create order on phones (R10b)", () => {
  it("uses the desktop POS on wide screens", async () => {
    setPhone(false);
    renderPos();
    expect(screen.getByRole("heading", { name: "New order" })).toBeInTheDocument();
    expect(screen.queryByText("Step 1 of 4")).not.toBeInTheDocument();
  });

  it("walks products → cart → customer → review and submits the same order payload", async () => {
    setPhone(true);
    vi.mocked(ordersApi.createOrder).mockResolvedValue({ id: "77777777-7777-4777-8777-777777777777", order_number: "ORD-0042", customer_id: CUSTOMER, order_total_minor: 490_000, currency_code: "PKR" } as any);
    renderPos();

    expect(screen.getByRole("heading", { name: "Add products" })).toHaveFocus();
    expect(screen.getByRole("progressbar", { name: "Order progress" })).toHaveAttribute("aria-valuenow", "1");
    const viewCart = screen.getByRole("button", { name: /View cart/ });
    expect(viewCart).toBeDisabled();

    const rice = await screen.findByRole("button", { name: /Basmati Rice 5kg, PKR 2,450, 3 in stock/ });
    fireEvent.click(rice);
    fireEvent.click(rice);
    expect(viewCart).toHaveTextContent("PKR 4,900");
    fireEvent.click(viewCart);

    expect(screen.getByRole("heading", { name: "Cart" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Increase Basmati Rice 5kg" }));
    expect(screen.getByRole("button", { name: "Increase Basmati Rice 5kg" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Decrease Basmati Rice 5kg" }));
    fireEvent.click(screen.getByRole("button", { name: "Choose customer" }));

    fireEvent.change(screen.getByLabelText("Find customer"), { target: { value: "0300" } });
    expect(screen.getByRole("radio", { name: /Walk-in customer/ })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: /Bilal General Store/ }));
    fireEvent.click(screen.getByRole("button", { name: "Review order" }));

    expect(screen.getByRole("heading", { name: "Review" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("radio", { name: /Bilal General Store/ })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Review order" }));
    fireEvent.click(screen.getByRole("button", { name: "Complete order · PKR 4,900" }));

    await waitFor(() =>
      expect(ordersApi.createOrder).toHaveBeenCalledWith(ORG, { customer_id: CUSTOMER, items: [{ product_id: RICE, quantity: 2, unit_price_minor: 245_000 }], currency_code: "PKR" }, undefined, expect.any(String))
    );
    expect(await screen.findByRole("heading", { name: "Order completed" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Record payment" })).toHaveAttribute("href", `/workspace/${ORG}/payments?record=1&orderId=77777777-7777-4777-8777-777777777777&customerId=${CUSTOMER}`);
    fireEvent.click(screen.getByRole("button", { name: "New order" }));
    expect(screen.getByRole("heading", { name: "Add products" })).toBeInTheDocument();
  });
});
