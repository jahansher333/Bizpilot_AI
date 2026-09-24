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
  };
});

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

    vi.mocked(customersApi.listCustomers).mockResolvedValue({
      items: mockCustomers,
      total: mockCustomers.length,
      limit: 100,
      offset: 0,
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

  describe("CustomerView UI & RBAC Rendering", () => {
    it("renders customer directory with walk-in banner and actions for Owner", async () => {
      renderWithQueryClient(
        <CustomerView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />
      );

      expect(await screen.findByText("Tariq Ali")).toBeInTheDocument();
      expect(screen.getByText("03001234567")).toBeInTheDocument();
      expect(screen.getByText("Walk-in alternative:")).toBeInTheDocument();
      expect(screen.getByText("Add Customer")).toBeInTheDocument();
      expect(screen.getByText("Edit")).toBeInTheDocument();
      expect(screen.getByText("Archive")).toBeInTheDocument();
    });

    it("restricts Staff to read-only experience (no Edit/Archive buttons, but can Add Customer)", async () => {
      renderWithQueryClient(
        <CustomerView orgId="00000000-0000-0000-0000-000000000000" userRole="staff" />
      );

      expect(await screen.findByText("Tariq Ali")).toBeInTheDocument();
      expect(screen.getByText("Add Customer")).toBeInTheDocument();
      expect(screen.queryByText("Edit")).not.toBeInTheDocument();
      expect(screen.queryByText("Archive")).not.toBeInTheDocument();
      expect(screen.getAllByText("Read-only").length).toBeGreaterThan(0);
    });

    it("filters customers by search term", async () => {
      renderWithQueryClient(
        <CustomerView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />
      );

      const searchInput = screen.getByPlaceholderText("Search by customer name or phone...");
      fireEvent.change(searchInput, { target: { value: "Tariq" } });

      await waitFor(() => {
        expect(customersApi.listCustomers).toHaveBeenCalledWith(
          "00000000-0000-0000-0000-000000000000",
          expect.objectContaining({ search: "Tariq" }),
          undefined
        );
      });
    });
  });

  describe("CustomerModal Form", () => {
    it("submits valid new customer", async () => {
      const onClose = vi.fn();
      vi.mocked(customersApi.createCustomer).mockResolvedValueOnce(mockCustomers[0]);

      renderWithQueryClient(
        <CustomerModal
          isOpen={true}
          onClose={onClose}
          orgId="00000000-0000-0000-0000-000000000000"
        />
      );

      const nameInput = screen.getByLabelText(/Customer Name/);
      fireEvent.change(nameInput, { target: { value: "New Customer" } });

      const phoneInput = screen.getByLabelText(/Phone Number/);
      fireEvent.change(phoneInput, { target: { value: "0300-5555555" } });

      const submitBtn = screen.getByText("Create Customer");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(customersApi.createCustomer).toHaveBeenCalledWith(
          "00000000-0000-0000-0000-000000000000",
          expect.objectContaining({
            name: "New Customer",
            phone: "03005555555",
          }),
          undefined
        );
        expect(onClose).toHaveBeenCalled();
      });
    });

    it("rejects empty name in form submission", async () => {
      renderWithQueryClient(
        <CustomerModal
          isOpen={true}
          onClose={vi.fn()}
          orgId="00000000-0000-0000-0000-000000000000"
        />
      );

      const submitBtn = screen.getByText("Create Customer");
      fireEvent.click(submitBtn);

      expect(
        await screen.findByText(/Customer name must be at least 1 character/)
      ).toBeInTheDocument();
      expect(customersApi.createCustomer).not.toHaveBeenCalled();
    });
  });
});
