import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  customerCreateSchema,
  customerUpdateSchema,
  normalizePhone,
  Customer,
} from "@/lib/schemas/customers";
import { CustomerView } from "@/components/customers/customer-view";
import { CustomerModal } from "@/components/customers/customer-modal";
import { CustomerDetail } from "@/components/customers/customer-detail";
import * as ordersApi from "@/lib/api/orders";
import * as paymentsApi from "@/lib/api/payments";
import * as customersApi from "@/lib/api/customers";

vi.mock("@/lib/api/customers", async (importOriginal) => {
  const actual = await importOriginal<typeof customersApi>();
  return {
    ...actual,
    listCustomers: vi.fn(),
    getCustomer: vi.fn(),
    createCustomer: vi.fn(),
    updateCustomer: vi.fn(),
    archiveCustomer: vi.fn(),
    getCustomerBalances: vi.fn(),
  };
});

vi.mock("@/lib/api/orders", () => ({ listOrders: vi.fn() }));
vi.mock("@/lib/api/payments", () => ({ listPayments: vi.fn() }));

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

const mockCustomers: Customer[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    name: "Tariq Ali",
    phone: "03001234567",
    email: "tariq@example.com",
    notes: "Wholesale buyer",
    status: "active",
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: null,
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    organization_id: "00000000-0000-0000-0000-000000000000",
    name: "Bilal Ahmed",
    phone: "03219876543",
    email: null,
    notes: null,
    status: "archived",
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: "2026-09-24T01:00:00Z",
  },
];

describe("Customer Frontend Slice (CUS-003)", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(customersApi.listCustomers).mockImplementation(async (_org, params) => {
      const items = mockCustomers.filter(
        (c) => (!params?.status || c.status === params.status) && (!params?.search || c.name.toLowerCase().includes(params.search.toLowerCase()))
      );
      return { items, total: items.length, limit: params?.limit ?? 50, offset: 0 };
    });
    vi.mocked(customersApi.getCustomerBalances).mockResolvedValue({
      currency_code: "PKR",
      items: [
        {
          customer_id: mockCustomers[0].id,
          order_count: 3,
          voided_order_count: 1,
          total_orders_minor: 3_500_000,
          payment_count: 2,
          total_payments_minor: 1_050_000,
          balance_minor: 2_450_000,
        },
      ],
      customers_with_orders: 1,
      customers_with_balance: 1,
      outstanding_minor: 2_450_000,
    });
  });

  describe("Customer Schema Validations", () => {
    it("normalizes phone formats correctly", () => {
      expect(normalizePhone(null)).toBeNull();
      expect(normalizePhone("   ")).toBeNull();
      expect(normalizePhone("+92 300 1234567")).toBe("03001234567");
      expect(normalizePhone("0092-300-1234567")).toBe("03001234567");
      expect(normalizePhone("0300-1234567")).toBe("03001234567");
    });

    it("validates customerCreateSchema requires name and normalizes phone", () => {
      const valid = customerCreateSchema.safeParse({
        name: "Usman Ghani",
        phone: "+92 311 1234567",
        email: "usman@example.com",
      });
      expect(valid.success).toBe(true);
      if (valid.success) {
        expect(valid.data.phone).toBe("03111234567");
      }

      const emptyName = customerCreateSchema.safeParse({
        name: "   ",
      });
      expect(emptyName.success).toBe(false);
    });

    it("validates customerUpdateSchema allows optional name", () => {
      const valid = customerUpdateSchema.safeParse({
        phone: "0345-1234567",
      });
      expect(valid.success).toBe(true);
      if (valid.success) {
        expect(valid.data.phone).toBe("03451234567");
      }
    });
  });

  describe("CustomerView (R5 design)", () => {
    it("shows customers with orders, balances and totals for Owner", async () => {
      renderWithQueryClient(<CustomerView orgId="org-1" userRole="owner" />);
      expect((await screen.findAllByRole("link", { name: "Tariq Ali" }))[0]).toHaveAttribute("href", `/workspace/org-1/customers/${mockCustomers[0].id}`);
      const summary = screen.getByRole("region", { name: "Customer summary" });
      await waitFor(() => expect(summary).toHaveTextContent("24,500"));
      expect(summary).toHaveTextContent("1 customer");
      const table = screen.getByRole("table");
      expect(table).toHaveTextContent("owes you");
      expect(table).not.toHaveTextContent("Bilal Ahmed");
      expect(screen.getByRole("link", { name: "New order for Tariq Ali" })).toHaveAttribute("href", `/workspace/org-1/orders/new?customerId=${mockCustomers[0].id}`);
      expect(screen.getByText(/walk-in sales:/i)).toBeInTheDocument();
    });

    it("never requests or shows balances for Staff", async () => {
      renderWithQueryClient(<CustomerView orgId="org-1" userRole="staff" />);
      expect((await screen.findAllByText("Tariq Ali")).length).toBeGreaterThan(0);
      expect(customersApi.getCustomerBalances).not.toHaveBeenCalled();
      expect(screen.queryByText(/outstanding balance/i)).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Has balance" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: /add customer/i })).toBeInTheDocument();
    });

    it("searches on the server and shows archived customers on demand", async () => {
      renderWithQueryClient(<CustomerView orgId="org-1" userRole="owner" />);
      await screen.findByRole("table");
      fireEvent.change(screen.getByLabelText("Search customers"), { target: { value: "tariq" } });
      await waitFor(() =>
        expect(customersApi.listCustomers).toHaveBeenCalledWith("org-1", expect.objectContaining({ search: "tariq" }), undefined)
      );
      fireEvent.change(screen.getByLabelText("Search customers"), { target: { value: "" } });
      fireEvent.click(screen.getByRole("button", { name: "Archived" }));
      await waitFor(() => expect(screen.getByRole("table")).toHaveTextContent("Bilal Ahmed"));
    });

    it("filters to customers who owe money", async () => {
      vi.mocked(customersApi.listCustomers).mockResolvedValue({
        items: [mockCustomers[0], { ...mockCustomers[1], id: "33333333-3333-4333-8333-333333333333", name: "Paid Up Store", status: "active" }],
        total: 2,
        limit: 100,
        offset: 0,
      });
      renderWithQueryClient(<CustomerView orgId="org-1" userRole="owner" />);
      await waitFor(() => expect(screen.getByRole("table")).toHaveTextContent("Paid Up Store"));
      fireEvent.click(screen.getByRole("button", { name: "Has balance" }));
      expect(screen.getByRole("table")).toHaveTextContent("Tariq Ali");
      expect(screen.getByRole("table")).not.toHaveTextContent("Paid Up Store");
    });
  });

  describe("CustomerModal Form", () => {
    it("submits a valid new customer with a normalised phone", async () => {
      vi.mocked(customersApi.createCustomer).mockResolvedValue(mockCustomers[0]);
      const onClose = vi.fn();
      renderWithQueryClient(<CustomerModal isOpen onClose={onClose} orgId="org-1" />);
      fireEvent.change(screen.getByLabelText("Customer name"), { target: { value: "Tariq Ali" } });
      fireEvent.change(screen.getByLabelText(/phone/i), { target: { value: "+92 300 1234567" } });
      fireEvent.click(screen.getByRole("button", { name: "Add customer" }));
      await waitFor(() =>
        expect(customersApi.createCustomer).toHaveBeenCalledWith("org-1", { name: "Tariq Ali", phone: "03001234567" }, undefined)
      );
      await waitFor(() => expect(onClose).toHaveBeenCalled());
    });

    it("rejects an empty name", async () => {
      renderWithQueryClient(<CustomerModal isOpen onClose={vi.fn()} orgId="org-1" />);
      fireEvent.click(screen.getByRole("button", { name: "Add customer" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/at least 1 character/i);
      expect(customersApi.createCustomer).not.toHaveBeenCalled();
    });

    it("shows a duplicate phone error from the server", async () => {
      vi.mocked(customersApi.createCustomer).mockRejectedValue(new customersApi.ApiError(409, "An active customer with this phone number already exists"));
      renderWithQueryClient(<CustomerModal isOpen onClose={vi.fn()} orgId="org-1" />);
      fireEvent.change(screen.getByLabelText("Customer name"), { target: { value: "Someone" } });
      fireEvent.change(screen.getByLabelText(/phone/i), { target: { value: "03001234567" } });
      fireEvent.click(screen.getByRole("button", { name: "Add customer" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/already exists/i);
    });
  });

  describe("CustomerDetail (R5 design)", () => {
    beforeEach(() => {
      vi.mocked(customersApi.getCustomer).mockResolvedValue(mockCustomers[0]);
      vi.mocked(ordersApi.listOrders).mockResolvedValue({
        items: [
          {
            id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            organization_id: "00000000-0000-0000-0000-000000000000",
            order_number: "BP-1028",
            customer_id: mockCustomers[0].id,
            ordered_at: "2026-10-03T05:31:00Z",
            status: "active",
            order_total_minor: 1_100_000,
            currency_code: "PKR",
            created_at: "2026-10-03T05:31:00Z",
            updated_at: "2026-10-03T05:31:00Z",
            items: [],
          },
          {
            id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            organization_id: "00000000-0000-0000-0000-000000000000",
            order_number: "BP-1016",
            customer_id: mockCustomers[0].id,
            ordered_at: "2026-10-02T09:52:00Z",
            status: "corrected",
            order_total_minor: 1_225_000,
            currency_code: "PKR",
            created_at: "2026-10-02T09:52:00Z",
            updated_at: "2026-10-02T09:52:00Z",
            items: [],
          },
        ],
        total: 2,
        limit: 100,
        offset: 0,
      });
      vi.mocked(paymentsApi.listPayments).mockResolvedValue({
        items: [
          {
            id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            organization_id: "00000000-0000-0000-0000-000000000000",
            payment_number: "PAY-0412",
            amount_minor: 1_100_000,
            channel: "cash",
            customer_id: mockCustomers[0].id,
            received_at: "2026-10-03T05:42:00Z",
            status: "active",
            currency_code: "PKR",
            created_at: "2026-10-03T05:42:00Z",
            updated_at: "2026-10-03T05:42:00Z",
          },
        ],
        total: 1,
        limit: 100,
        offset: 0,
      });
    });

    it("shows contact details, balance and a combined activity timeline", async () => {
      renderWithQueryClient(<CustomerDetail orgId="org-1" customerId={mockCustomers[0].id} userRole="owner" />);
      expect(await screen.findByRole("heading", { name: "Tariq Ali" })).toBeInTheDocument();
      const summary = screen.getByRole("region", { name: "Customer summary" });
      await waitFor(() => expect(summary).toHaveTextContent("24,500"));
      expect(summary).toHaveTextContent("1 voided, not counted");
      expect(customersApi.getCustomerBalances).toHaveBeenCalledWith("org-1", mockCustomers[0].id, undefined);

      const timeline = await screen.findByRole("list");
      expect(timeline).toHaveTextContent("BP-1028");
      expect(timeline).toHaveTextContent("Payment recorded · Cash");
      expect(timeline).toHaveTextContent("Order corrected");
      expect(screen.getByText("Wholesale buyer")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /create order/i })).toHaveAttribute("href", `/workspace/org-1/orders/new?customerId=${mockCustomers[0].id}`);
    });

    it("lists orders and payments in their tabs", async () => {
      renderWithQueryClient(<CustomerDetail orgId="org-1" customerId={mockCustomers[0].id} userRole="owner" />);
      fireEvent.click(await screen.findByRole("tab", { name: /orders/i }));
      expect(screen.getByRole("table")).toHaveTextContent("Corrected");
      fireEvent.click(screen.getByRole("tab", { name: /payments/i }));
      expect(screen.getByRole("table")).toHaveTextContent("PAY-0412");
    });

    it("hides the balance and archive action from Staff", async () => {
      renderWithQueryClient(<CustomerDetail orgId="org-1" customerId={mockCustomers[0].id} userRole="staff" />);
      expect(await screen.findByRole("heading", { name: "Tariq Ali" })).toBeInTheDocument();
      expect(customersApi.getCustomerBalances).not.toHaveBeenCalled();
      expect(screen.queryByText("Balance")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
    });

    it("confirms before archiving", async () => {
      vi.mocked(customersApi.archiveCustomer).mockResolvedValue({ ...mockCustomers[0], status: "archived" });
      renderWithQueryClient(<CustomerDetail orgId="org-1" customerId={mockCustomers[0].id} userRole="owner" />);
      fireEvent.click(await screen.findByRole("button", { name: "Archive" }));
      fireEvent.click(screen.getByRole("button", { name: "Archive customer" }));
      await waitFor(() => expect(customersApi.archiveCustomer).toHaveBeenCalledWith("org-1", mockCustomers[0].id, undefined));
    });
  });
});
