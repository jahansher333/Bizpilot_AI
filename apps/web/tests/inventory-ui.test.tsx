import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import {
  openingStockSchema,
  adjustmentSchema,
  correctionSchema,
  InventoryBalance,
  InventoryMovement,
} from "@/lib/schemas/inventory";
import { Product } from "@/lib/schemas/catalog";
import { InventoryView } from "@/components/inventory/inventory-view";
import { OpeningStockModal } from "@/components/inventory/opening-stock-modal";
import { StockChangeModal } from "@/components/inventory/stock-change-modal";
import { StockDetail } from "@/components/inventory/stock-detail";
import * as inventoryApi from "@/lib/api/inventory";
import * as catalogApi from "@/lib/api/catalog";

// Mock the API client functions
vi.mock("@/lib/api/inventory", () => ({
  fetchBalances: vi.fn(),
  fetchBalance: vi.fn(),
  fetchMovements: vi.fn(),
  recordOpeningStock: vi.fn(),
  recordAdjustment: vi.fn(),
  recordCorrection: vi.fn(),
  recordVoidReversal: vi.fn(),
}));

vi.mock("@/lib/api/catalog", async (importOriginal) => {
  const actual = await importOriginal<typeof catalogApi>();
  return { ...actual, listProducts: vi.fn(), getProduct: vi.fn(), listCategories: vi.fn() };
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

const mockProducts: Product[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    code: "SKU-001",
    name: "Cotton Shirt",
    base_unit: "piece",
    default_price_minor: 150000,
    currency_code: "PKR",
    status: "active",
    category_id: null,
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: null,
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    organization_id: "00000000-0000-0000-0000-000000000000",
    code: "SKU-002",
    name: "Linen Trousers",
    base_unit: "piece",
    default_price_minor: 250000,
    currency_code: "PKR",
    status: "active",
    category_id: null,
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: null,
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    organization_id: "00000000-0000-0000-0000-000000000000",
    code: "SKU-003",
    name: "Silk Scarf",
    base_unit: "piece",
    default_price_minor: 80000,
    currency_code: "PKR",
    status: "active",
    category_id: null,
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: null,
  },
];

const mockBalances: InventoryBalance[] = [
  {
    id: "ba111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    product_id: "11111111-1111-4111-8111-111111111111",
    on_hand_quantity: 45, // In Stock
    version: 1,
    updated_at: "2026-09-24T01:00:00Z",
  },
  {
    id: "ba222222-2222-4222-8222-222222222222",
    organization_id: "00000000-0000-0000-0000-000000000000",
    product_id: "22222222-2222-4222-8222-222222222222",
    on_hand_quantity: 4, // Low Stock (<= 10)
    version: 2,
    updated_at: "2026-09-24T01:00:00Z",
  },
  {
    id: "ba333333-3333-4333-8333-333333333333",
    organization_id: "00000000-0000-0000-0000-000000000000",
    product_id: "33333333-3333-4333-8333-333333333333",
    on_hand_quantity: 0, // Out of Stock
    version: 1,
    updated_at: "2026-09-24T01:00:00Z",
  },
];

const mockMovements: InventoryMovement[] = [
  {
    id: "ea111111-1111-4111-8111-111111111111",
    organization_id: "00000000-0000-0000-0000-000000000000",
    product_id: "11111111-1111-4111-8111-111111111111",
    movement_type: "opening",
    quantity_delta: 50,
    source_type: "opening",
    source_id: null,
    reason: "Initial opening stock",
    created_by_user_id: null,
    created_at: "2026-09-24T01:00:00Z",
  },
  {
    id: "ea222222-2222-4222-8222-222222222222",
    organization_id: "00000000-0000-0000-0000-000000000000",
    product_id: "11111111-1111-4111-8111-111111111111",
    movement_type: "adjustment",
    quantity_delta: -5,
    source_type: "adjustment",
    source_id: null,
    reason: "Sample write-off",
    created_by_user_id: null,
    created_at: "2026-09-24T02:00:00Z",
  },
];

describe("Inventory Frontend Slice (INV-005)", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(catalogApi.listProducts).mockResolvedValue({
      items: mockProducts,
      total: mockProducts.length,
      limit: 100,
      offset: 0,
    });

    vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({
      items: mockBalances,
      total: mockBalances.length,
      limit: 100,
      offset: 0,
    });

    vi.mocked(inventoryApi.fetchMovements).mockResolvedValue({
      items: mockMovements,
      total: mockMovements.length,
      limit: 50,
      offset: 0,
    });
  });

  describe("Inventory Schema Validations", () => {
    it("validates openingStockSchema requires positive integer", () => {
      const valid = openingStockSchema.safeParse({
        product_id: "11111111-1111-4111-8111-111111111111",
        quantity: 20,
        reason: "Initial",
      });
      expect(valid.success).toBe(true);

      const zeroQty = openingStockSchema.safeParse({
        product_id: "11111111-1111-4111-8111-111111111111",
        quantity: 0,
      });
      expect(zeroQty.success).toBe(false);

      const negativeQty = openingStockSchema.safeParse({
        product_id: "11111111-1111-4111-8111-111111111111",
        quantity: -5,
      });
      expect(negativeQty.success).toBe(false);
    });

    it("validates adjustmentSchema requires non-zero delta and min 3 char reason", () => {
      const valid = adjustmentSchema.safeParse({
        product_id: "11111111-1111-4111-8111-111111111111",
        quantity_delta: -5,
        reason: "Cycle count variance",
      });
      expect(valid.success).toBe(true);

      const zeroDelta = adjustmentSchema.safeParse({
        product_id: "11111111-1111-4111-8111-111111111111",
        quantity_delta: 0,
        reason: "Valid reason",
      });
      expect(zeroDelta.success).toBe(false);

      const shortReason = adjustmentSchema.safeParse({
        product_id: "11111111-1111-4111-8111-111111111111",
        quantity_delta: 5,
        reason: "ab",
      });
      expect(shortReason.success).toBe(false);
    });

    it("validates correctionSchema requires non-zero delta and min 3 char reason", () => {
      const valid = correctionSchema.safeParse({
        product_id: "11111111-1111-4111-8111-111111111111",
        quantity_delta: 2,
        reason: "Physical count correction",
      });
      expect(valid.success).toBe(true);
    });
  });

  describe("InventoryView (R4 design)", () => {
    it("joins products with balances and summarises stock health", async () => {
      renderWithQueryClient(<InventoryView orgId="org-1" userRole="owner" />);
      const table = await screen.findByRole("table");
      await waitFor(() => expect(table).toHaveTextContent("Cotton Shirt"));
      const summary = screen.getByRole("region", { name: "Stock summary" });
      expect(summary).toHaveTextContent("Healthy1");
      expect(summary).toHaveTextContent("Low stock1");
      expect(summary).toHaveTextContent("Out of stock1");
      expect(table).toHaveTextContent("Adjustment −5");
      expect(screen.getByRole("link", { name: "Cotton Shirt" })).toHaveAttribute("href", `/workspace/org-1/inventory/${mockProducts[0].id}`);
    });

    it("shows Adjust for Owner/Manager and only History for Staff", async () => {
      const { unmount } = renderWithQueryClient(<InventoryView orgId="org-1" userRole="manager" />);
      expect(await screen.findByRole("link", { name: "Adjust stock for Cotton Shirt" })).toHaveAttribute("href", `/workspace/org-1/inventory/${mockProducts[0].id}?action=adjust`);
      unmount();
      renderWithQueryClient(<InventoryView orgId="org-1" userRole="staff" />);
      expect(await screen.findByRole("link", { name: "Stock history for Cotton Shirt" })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /adjust stock for/i })).not.toBeInTheDocument();
    });

    it("filters by summary card and by search", async () => {
      renderWithQueryClient(<InventoryView orgId="org-1" userRole="owner" />);
      const table = await screen.findByRole("table");
      await waitFor(() => expect(table).toHaveTextContent("Silk Scarf"));
      fireEvent.click(screen.getByRole("button", { name: /out of stock1/i }));
      expect(screen.getByRole("table")).toHaveTextContent("Silk Scarf");
      expect(screen.getByRole("table")).not.toHaveTextContent("Cotton Shirt");

      fireEvent.click(screen.getByRole("button", { name: "All" }));
      fireEvent.change(screen.getByLabelText("Search inventory"), { target: { value: "linen" } });
      expect(screen.getByRole("table")).toHaveTextContent("Linen Trousers");
      expect(screen.getByRole("table")).not.toHaveTextContent("Silk Scarf");
    });

    it("offers opening stock for products without a balance", async () => {
      vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({ items: mockBalances.slice(0, 2), total: 2, limit: 100, offset: 0 });
      renderWithQueryClient(<InventoryView orgId="org-1" userRole="owner" />);
      expect(await screen.findByRole("link", { name: "Set opening stock for Silk Scarf" })).toHaveAttribute("href", `/workspace/org-1/inventory/${mockProducts[2].id}?action=opening`);
    });
  });

  describe("StockChangeModal", () => {
    const base = { orgId: "org-1", productId: mockProducts[0].id, productName: "Cotton Shirt", productCode: "SKU-001", unit: "piece", currentQuantity: 45, onClose: vi.fn() };

    it("records an adjustment with reason and an idempotency key", async () => {
      vi.mocked(inventoryApi.recordAdjustment).mockResolvedValue({} as never);
      renderWithQueryClient(<StockChangeModal {...base} mode="adjust" />);
      fireEvent.click(screen.getByRole("button", { name: "− Decrease" }));
      fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "3" } });
      fireEvent.click(screen.getByRole("button", { name: "Damaged" }));
      expect(screen.getByText("42 piece")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Confirm adjustment" }));
      await waitFor(() =>
        expect(inventoryApi.recordAdjustment).toHaveBeenCalledWith(
          "org-1",
          { product_id: mockProducts[0].id, quantity_delta: -3, reason: "Damaged" },
          undefined,
          expect.any(String)
        )
      );
    });

    it("blocks a decrease below zero", () => {
      renderWithQueryClient(<StockChangeModal {...base} mode="adjust" />);
      fireEvent.click(screen.getByRole("button", { name: "− Decrease" }));
      fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "50" } });
      expect(screen.getByRole("alert")).toHaveTextContent(/stock can’t go below zero/i);
      expect(screen.getByRole("button", { name: "Confirm adjustment" })).toBeDisabled();
    });

    it("requires a reason when Other is chosen", () => {
      renderWithQueryClient(<StockChangeModal {...base} mode="adjust" />);
      fireEvent.click(screen.getByRole("button", { name: "Other" }));
      expect(screen.getByRole("button", { name: "Confirm adjustment" })).toBeDisabled();
      fireEvent.change(screen.getByLabelText("Describe the reason"), { target: { value: "Sample given to customer" } });
      expect(screen.getByRole("button", { name: "Confirm adjustment" })).toBeEnabled();
    });

    it("records a correction as the difference from the counted quantity", async () => {
      vi.mocked(inventoryApi.recordCorrection).mockResolvedValue({} as never);
      renderWithQueryClient(<StockChangeModal {...base} mode="correct" />);
      expect(screen.getByLabelText("Counted quantity")).toHaveValue("45");
      expect(screen.getByRole("button", { name: "Confirm correction" })).toBeDisabled();
      fireEvent.change(screen.getByLabelText("Counted quantity"), { target: { value: "47" } });
      fireEvent.click(screen.getByRole("button", { name: "Confirm correction" }));
      await waitFor(() =>
        expect(inventoryApi.recordCorrection).toHaveBeenCalledWith(
          "org-1",
          { product_id: mockProducts[0].id, quantity_delta: 2, reason: "Shelf count" },
          undefined,
          expect.any(String)
        )
      );
    });
  });

  describe("OpeningStockModal", () => {
    it("records a positive opening quantity", async () => {
      vi.mocked(inventoryApi.recordOpeningStock).mockResolvedValue({} as never);
      const onClose = vi.fn();
      renderWithQueryClient(<OpeningStockModal orgId="org-1" productId={mockProducts[2].id} productName="Silk Scarf" unit="piece" isOpen onClose={onClose} />);
      fireEvent.click(screen.getByRole("button", { name: "Record opening stock" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/greater than zero/i);
      fireEvent.change(screen.getByLabelText("Quantity on hand"), { target: { value: "12" } });
      fireEvent.click(screen.getByRole("button", { name: "Record opening stock" }));
      await waitFor(() =>
        expect(inventoryApi.recordOpeningStock).toHaveBeenCalledWith("org-1", { product_id: mockProducts[2].id, quantity: 12, reason: "Opening stock" }, undefined)
      );
      await waitFor(() => expect(onClose).toHaveBeenCalled());
    });
  });

  describe("StockDetail", () => {
    beforeEach(() => {
      vi.mocked(catalogApi.getProduct).mockResolvedValue(mockProducts[0]);
      vi.mocked(catalogApi.listCategories).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
      vi.mocked(inventoryApi.fetchBalance).mockResolvedValue(mockBalances[0]);
    });

    it("shows current stock and a timeline with running balances", async () => {
      renderWithQueryClient(<StockDetail orgId="org-1" productId={mockProducts[0].id} userRole="owner" />);
      expect(await screen.findByRole("heading", { name: "Cotton Shirt" })).toBeInTheDocument();
      await waitFor(() => expect(screen.getAllByText("45 piece").length).toBeGreaterThan(0));
      // Newest first: adjustment −5 leaves 45; opening +50 left 50
      const timeline = screen.getByRole("list");
      expect(timeline).toHaveTextContent("Adjustment");
      expect(timeline).toHaveTextContent("Balance 45 piece");
      expect(timeline).toHaveTextContent("Balance 50 piece");
      expect(screen.getByRole("button", { name: /adjust stock/i })).toBeInTheDocument();
      expect(inventoryApi.fetchMovements).toHaveBeenCalledWith("org-1", { productId: mockProducts[0].id, limit: 100 }, undefined);
    });

    it("opens the adjust modal from ?action=adjust and hides actions for Staff", async () => {
      const { unmount } = renderWithQueryClient(<StockDetail orgId="org-1" productId={mockProducts[0].id} userRole="owner" initialAction="adjust" />);
      expect(await screen.findByRole("dialog", { name: "Adjust stock" })).toBeInTheDocument();
      unmount();
      renderWithQueryClient(<StockDetail orgId="org-1" productId={mockProducts[0].id} userRole="staff" initialAction="adjust" />);
      expect(await screen.findByRole("heading", { name: "Cotton Shirt" })).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /adjust stock/i })).not.toBeInTheDocument();
    });

    it("offers opening stock when the product has no balance yet", async () => {
      vi.mocked(inventoryApi.fetchBalance).mockRejectedValue(new catalogApi.ApiError("Not found", 404));
      renderWithQueryClient(<StockDetail orgId="org-1" productId={mockProducts[0].id} userRole="owner" />);
      expect(await screen.findByRole("button", { name: /set opening stock/i })).toBeInTheDocument();
      expect(screen.getByText("No stock recorded yet.")).toBeInTheDocument();
    });
  });
});
