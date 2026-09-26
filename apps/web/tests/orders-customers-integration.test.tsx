import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { CustomerView } from "@/components/customers/customer-view";
import { OrdersView } from "@/components/orders/orders-view";
import { OrderCreateModal } from "@/components/orders/order-create-modal";
import { Order } from "@/lib/schemas/orders";
import * as customersApi from "@/lib/api/customers";
import * as ordersApi from "@/lib/api/orders";
import * as catalogApi from "@/lib/api/catalog";

vi.mock("@/lib/api/customers", () => ({
  listCustomers: vi.fn(),
  createCustomer: vi.fn(),
}));

vi.mock("@/lib/api/orders", () => ({
  listOrders: vi.fn(),
  getOrder: vi.fn(),
  createOrder: vi.fn(),
  voidOrder: vi.fn(),
  correctOrder: vi.fn(),
}));

vi.mock("@/lib/api/catalog", () => ({
  listProducts: vi.fn(),
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

const mockCustomers = [
  {
    id: "cust-1",
    name: "Ahmed Trading",
    phone: "03001234567",
    email: "ahmed@example.com",
    address: "Lahore",
    current_balance: 150000,
    created_at: "2026-09-01T10:00:00Z",
  },
  {
    id: "cust-2",
    name: "Karachi Traders",
    phone: "03219876543",
    email: null,
    address: null,
    current_balance: 0,
    created_at: "2026-09-02T10:00:00Z",
  },
];

const mockOrders: Order[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    order_number: "ORD-0001",
    customer_id: "22222222-2222-4222-8222-222222222222",
    ordered_at: "2026-09-20T10:00:00Z",
    status: "active" as const,
    order_total_minor: 10000,
    currency_code: "PKR",
    created_by_user_id: "33333333-3333-4333-8333-333333333333",
    corrects_order_id: null,
    replaced_by_order_id: null,
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    voided_at: null,
    items: [],
  },
];

describe("UX-004: Customer & Order Workflow Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(customersApi.listCustomers).mockResolvedValue({
      items: mockCustomers as any,
      total: 2,
      limit: 50,
      offset: 0,
    });
    vi.mocked(ordersApi.listOrders).mockResolvedValue({
      items: mockOrders,
      total: 1,
      limit: 100,
      offset: 0,
    });
    vi.mocked(catalogApi.listProducts).mockResolvedValue({
      items: [
        {
          id: "prod-1",
          organization_id: "org-1",
          category_id: null,
          code: "PROD-A",
          name: "Test Product A",
          base_unit: "piece",
          default_price_minor: 500000,
          currency_code: "PKR",
          status: "active" as const,
          created_by_user_id: null,
          archived_at: null,
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-01T00:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
  });

  it("renders customer directory with orders link and action to start order for customer", async () => {
    renderWithQueryClient(
      <CustomerView orgId="org-1" userRole="owner" />
    );

    await waitFor(() => {
      expect(screen.getByText("Ahmed Trading")).toBeInTheDocument();
    });

    // Check link to view all orders
    const ordersLink = screen.getByRole("link", { name: /view orders/i });
    expect(ordersLink).toHaveAttribute("href", "/workspace/org-1/orders");

    // Check customer-specific New Order link
    const newOrderLinks = screen.getAllByRole("link", { name: /new order/i });
    expect(newOrderLinks.length).toBeGreaterThan(0);
    expect(newOrderLinks[0]).toHaveAttribute("href", "/workspace/org-1/orders?customerId=cust-1");
  });

  it("renders orders view with customer filter notice and navigation link back to customers directory", async () => {
    renderWithQueryClient(
      <OrdersView orgId="org-1" userRole="owner" initialCustomerId="cust-1" />
    );

    // Filter banner is displayed
    await waitFor(() => {
      expect(screen.getByText(/filtering orders for customer:/i)).toBeInTheDocument();
      expect(screen.getByText("cust-1")).toBeInTheDocument();
    });

    // Link back to Customers Directory exists
    const customersLink = screen.getByRole("link", { name: /customers directory/i });
    expect(customersLink).toHaveAttribute("href", "/workspace/org-1/customers");

    // Link to clear filter exists
    const clearFilterLink = screen.getByRole("link", { name: /show all orders/i });
    expect(clearFilterLink).toHaveAttribute("href", "/workspace/org-1/orders");
  });

  it("pre-selects the customer in OrderCreateModal when initialCustomerId is supplied", async () => {
    renderWithQueryClient(
      <OrderCreateModal
        isOpen={true}
        onClose={vi.fn()}
        orgId="org-1"
        initialCustomerId="cust-1"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("New Order Entry")).toBeInTheDocument();
      const customerSelect = screen.getByLabelText(/customer/i) as HTMLSelectElement;
      expect(customerSelect.value).toBe("cust-1");
    });
  });
});
