import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import {
  formatMoney,
  orderCorrectSchema,
  orderCreateSchema,
  orderVoidSchema,
  Order,
} from "@/lib/schemas/orders";
import { OrdersView } from "@/components/orders/orders-view";
import { OrderCreateModal } from "@/components/orders/order-create-modal";
import { OrderDetailModal } from "@/components/orders/order-detail-modal";
import { OrderVoidModal } from "@/components/orders/order-void-modal";
import { OrderCorrectModal } from "@/components/orders/order-correct-modal";
import * as ordersApi from "@/lib/api/orders";
import * as catalogApi from "@/lib/api/catalog";
import * as customersApi from "@/lib/api/customers";

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

vi.mock("@/lib/api/customers", () => ({
  listCustomers: vi.fn(),
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

const mockOrders: Order[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    order_number: "ORD-0001",
    customer_id: "99999999-9999-4999-8999-999999999999",
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
        product_id: "33333333-3333-4333-8333-333333333333",
        product_name_snapshot: "Cotton Fabric",
        product_code_snapshot: "FAB-01",
        unit_snapshot: "meter",
        quantity: 5,
        unit_price_minor: 3000,
        line_total_minor: 15000,
        currency_code: "PKR",
        created_at: "2026-09-24T10:00:00Z",
      },
    ],
  },
  {
    id: "44444444-4444-4444-8444-444444444444",
    organization_id: "00000000-0000-0000-0000-000000000000",
    order_number: "ORD-0002",
    customer_id: null,
    ordered_at: "2026-09-24T11:00:00Z",
    status: "voided",
    order_total_minor: 6000,
    currency_code: "PKR",
    created_by_user_id: null,
    corrects_order_id: null,
    replaced_by_order_id: null,
    created_at: "2026-09-24T11:00:00Z",
    updated_at: "2026-09-24T11:30:00Z",
    voided_at: "2026-09-24T11:30:00Z",
    items: [],
  },
];

describe("Orders UI & Domain Schemas (ORD-007)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("validates orderCreateSchema rejecting empty line items or non-positive quantity", () => {
    const emptyItems = orderCreateSchema.safeParse({
      items: [],
    });
    expect(emptyItems.success).toBe(false);

    const zeroQuantity = orderCreateSchema.safeParse({
      items: [
        {
          product_id: "33333333-3333-4333-8333-333333333333",
          quantity: 0,
          unit_price_minor: 100,
        },
      ],
    });
    expect(zeroQuantity.success).toBe(false);

    const validOrder = orderCreateSchema.safeParse({
      items: [
        {
          product_id: "33333333-3333-4333-8333-333333333333",
          quantity: 2,
          unit_price_minor: 5000,
        },
      ],
    });
    expect(validOrder.success).toBe(true);
  });

  it("validates orderVoidSchema and orderCorrectSchema requiring minimum 3 char reason", () => {
    expect(orderVoidSchema.safeParse({ reason: "no" }).success).toBe(false);
    expect(orderVoidSchema.safeParse({ reason: "Customer requested" }).success).toBe(true);

    expect(
      orderCorrectSchema.safeParse({
        reason: "ab",
        items: [
          {
            product_id: "33333333-3333-4333-8333-333333333333",
            quantity: 1,
            unit_price_minor: 1000,
          },
        ],
      }).success
    ).toBe(false);

    expect(
      orderCorrectSchema.safeParse({
        reason: "Adjusted size per customer",
        items: [
          {
            product_id: "33333333-3333-4333-8333-333333333333",
            quantity: 1,
            unit_price_minor: 1000,
          },
        ],
      }).success
    ).toBe(true);
  });

  it("formats currency correctly into human readable PKR representation", () => {
    expect(formatMoney(15000, "PKR")).toBe("Rs. 150.00");
    expect(formatMoney(0, "PKR")).toBe("Rs. 0.00");
  });

  it("renders order list with totals, status badges, and numbers", async () => {
    vi.mocked(ordersApi.listOrders).mockResolvedValue({
      items: mockOrders,
      total: 2,
      limit: 100,
      offset: 0,
    });

    renderWithQueryClient(<OrdersView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />);

    expect(screen.getByText("Loading orders...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("ORD-0001")).toBeInTheDocument();
      expect(screen.getByText("ORD-0002")).toBeInTheDocument();
      expect(screen.getByText("Rs. 150.00")).toBeInTheDocument();
      expect(screen.getByText("Rs. 60.00")).toBeInTheDocument();
    });
  });

  it("enforces role-based action buttons in orders table", async () => {
    vi.mocked(ordersApi.listOrders).mockResolvedValue({
      items: mockOrders,
      total: 2,
      limit: 100,
      offset: 0,
    });

    // Test as Owner: has Void and Correct buttons on active order
    const { unmount } = renderWithQueryClient(
      <OrdersView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />
    );

    await waitFor(() => {
      expect(screen.getByText("ORD-0001")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Void" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correct" })).toBeInTheDocument();
    unmount();

    // Test as Manager: has Correct button, but Void button is NOT rendered
    const { unmount: unmountManager } = renderWithQueryClient(
      <OrdersView orgId="00000000-0000-0000-0000-000000000000" userRole="manager" />
    );

    await waitFor(() => {
      expect(screen.getByText("ORD-0001")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "Void" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correct" })).toBeInTheDocument();
    unmountManager();

    // Test as Staff: read-only actions (only View, neither Void nor Correct)
    renderWithQueryClient(
      <OrdersView orgId="00000000-0000-0000-0000-000000000000" userRole="staff" />
    );

    await waitFor(() => {
      expect(screen.getByText("ORD-0001")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "Void" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Correct" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "View" }).length).toBeGreaterThan(0);
    expect(screen.getByText(/Staff Permissions:/i)).toBeInTheDocument();
  });

  it("renders OrderDetailModal with line item snapshots and grand total", () => {
    const handleClose = vi.fn();
    render(
      <OrderDetailModal
        isOpen={true}
        onClose={handleClose}
        order={mockOrders[0]}
      />
    );

    expect(screen.getByText("Order ORD-0001")).toBeInTheDocument();
    expect(screen.getByText("Cotton Fabric")).toBeInTheDocument();
    expect(screen.getByText("FAB-01")).toBeInTheDocument();
    expect(screen.getByText("5 meter")).toBeInTheDocument();
    expect(screen.getByText("Rs. 30.00")).toBeInTheDocument();
    expect(screen.getByText("Order Total:")).toBeInTheDocument();
    expect(screen.getAllByText("Rs. 150.00").length).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("submits OrderVoidModal with reason and idempotency key", async () => {
    vi.mocked(ordersApi.voidOrder).mockResolvedValue({
      ...mockOrders[0],
      status: "voided",
    });

    const handleClose = vi.fn();
    renderWithQueryClient(
      <OrderVoidModal
        isOpen={true}
        onClose={handleClose}
        order={mockOrders[0]}
        orgId="00000000-0000-0000-0000-000000000000"
      />
    );

    expect(screen.getByText(/Void Order ORD-0001/i)).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/Customer cancelled order/i);
    fireEvent.change(input, { target: { value: "Customer changed mind" } });

    const submitBtn = screen.getByRole("button", { name: /Confirm Void Order/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(ordersApi.voidOrder).toHaveBeenCalledWith(
        "00000000-0000-0000-0000-000000000000",
        mockOrders[0].id,
        { reason: "Customer changed mind" },
        undefined,
        expect.stringMatching(/^web-void-/)
      );
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it("handles OrderCreateModal product selection and live total calculation", async () => {
    vi.mocked(catalogApi.listProducts).mockResolvedValue({
      items: [
        {
          id: "33333333-3333-4333-8333-333333333333",
          organization_id: "00000000-0000-0000-0000-000000000000",
          code: "FAB-01",
          name: "Cotton Fabric",
          base_unit: "meter",
          default_price_minor: 2500,
          currency_code: "PKR",
          status: "active",
          category_id: null,
          created_at: "2026-09-24T00:00:00Z",
          updated_at: "2026-09-24T00:00:00Z",
          archived_at: null,
          created_by_user_id: null,
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
    vi.mocked(customersApi.listCustomers).mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    });
    vi.mocked(ordersApi.createOrder).mockResolvedValue(mockOrders[0]);

    const handleClose = vi.fn();
    renderWithQueryClient(
      <OrderCreateModal
        isOpen={true}
        onClose={handleClose}
        orgId="00000000-0000-0000-0000-000000000000"
      />
    );

    expect(screen.getByText("New Order Entry")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/Cotton Fabric \(FAB-01\)/i)).toBeInTheDocument();
    });

    const select = screen.getByLabelText("Product item 1");
    fireEvent.change(select, { target: { value: "33333333-3333-4333-8333-333333333333" } });

    // Live total preview: 1 * 2500 = Rs. 25.00
    await waitFor(() => {
      expect(screen.getAllByText("Rs. 25.00").length).toBeGreaterThan(0);
    });

    const submitBtn = screen.getByRole("button", { name: /Confirm & Save Order/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(ordersApi.createOrder).toHaveBeenCalledWith(
        "00000000-0000-0000-0000-000000000000",
        expect.objectContaining({
          items: [
            {
              product_id: "33333333-3333-4333-8333-333333333333",
              quantity: 1,
              unit_price_minor: 2500,
            },
          ],
        }),
        undefined,
        expect.stringMatching(/^web-create-/)
      );
      expect(handleClose).toHaveBeenCalled();
    });
  });
});
