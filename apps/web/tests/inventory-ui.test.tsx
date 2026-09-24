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
import { AdjustmentModal } from "@/components/inventory/adjustment-modal";
import { MovementHistoryModal } from "@/components/inventory/movement-history-modal";
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

  describe("InventoryView UI & RBAC Rendering", () => {
    it("renders inventory table with products and balances for Owner", async () => {
      renderWithQueryClient(
        <InventoryView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />
      );

      expect(await screen.findByText("Cotton Shirt")).toBeInTheDocument();
      expect(screen.getByText("SKU-001")).toBeInTheDocument();
      expect(screen.getByText("45")).toBeInTheDocument();
      expect(screen.getByText("In Stock")).toBeInTheDocument();

      expect(screen.getByText("Linen Trousers")).toBeInTheDocument();
      expect(screen.getByText("4")).toBeInTheDocument();
      expect(screen.getByText("Low Stock")).toBeInTheDocument();

      expect(screen.getByText("Silk Scarf")).toBeInTheDocument();
      expect(screen.getByText("0")).toBeInTheDocument();
      expect(screen.getByText("Out of Stock")).toBeInTheDocument();
    });

    it("displays mutation controls for Owner and Manager", async () => {
      renderWithQueryClient(
        <InventoryView orgId="00000000-0000-0000-0000-000000000000" userRole="manager" />
      );

      expect(await screen.findByText("Cotton Shirt")).toBeInTheDocument();
      expect(screen.getByText("Record Opening Stock")).toBeInTheDocument();
      expect(screen.getAllByText("Adjust Stock").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Correct Count").length).toBeGreaterThan(0);
    });

    it("restricts Staff to read-only experience (no mutation buttons)", async () => {
      renderWithQueryClient(
        <InventoryView orgId="00000000-0000-0000-0000-000000000000" userRole="staff" />
      );

      expect(await screen.findByText("Cotton Shirt")).toBeInTheDocument();
      expect(screen.queryByText("Record Opening Stock")).not.toBeInTheDocument();
      expect(screen.queryByText("Adjust Stock")).not.toBeInTheDocument();
      expect(screen.queryByText("Correct Count")).not.toBeInTheDocument();

      // Staff can still view movement history
      expect(screen.getAllByText("History").length).toBe(3);
    });

    it("filters products by search term", async () => {
      renderWithQueryClient(
        <InventoryView orgId="00000000-0000-0000-0000-000000000000" userRole="owner" />
      );

      expect(await screen.findByText("Cotton Shirt")).toBeInTheDocument();
      expect(screen.getByText("Linen Trousers")).toBeInTheDocument();

      const searchInput = screen.getByPlaceholderText("Search by product name or code...");
      fireEvent.change(searchInput, { target: { value: "Silk" } });

      expect(screen.getByText("Silk Scarf")).toBeInTheDocument();
      expect(screen.queryByText("Cotton Shirt")).not.toBeInTheDocument();
      expect(screen.queryByText("Linen Trousers")).not.toBeInTheDocument();
    });
  });

  describe("OpeningStockModal", () => {
    it("submits valid opening stock", async () => {
      const onClose = vi.fn();
      vi.mocked(inventoryApi.recordOpeningStock).mockResolvedValueOnce({
        balance: mockBalances[0],
        movement: mockMovements[0],
      });

      renderWithQueryClient(
        <OpeningStockModal
          isOpen={true}
          onClose={onClose}
          orgId="00000000-0000-0000-0000-000000000000"
          products={mockProducts}
        />
      );

      const qtyInput = screen.getByLabelText("Opening Quantity");
      fireEvent.change(qtyInput, { target: { value: "25" } });

      const submitBtn = screen.getByText("Save Opening Stock");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(inventoryApi.recordOpeningStock).toHaveBeenCalledWith(
          "00000000-0000-0000-0000-000000000000",
          {
            product_id: mockProducts[0].id,
            quantity: 25,
            reason: "Initial opening stock",
          },
          undefined
        );
        expect(onClose).toHaveBeenCalled();
      });
    });

    it("rejects non-positive quantity in form", async () => {
      renderWithQueryClient(
        <OpeningStockModal
          isOpen={true}
          onClose={vi.fn()}
          orgId="00000000-0000-0000-0000-000000000000"
          products={mockProducts}
        />
      );

      const qtyInput = screen.getByLabelText("Opening Quantity");
      fireEvent.change(qtyInput, { target: { value: "0" } });

      const submitBtn = screen.getByText("Save Opening Stock");
      fireEvent.click(submitBtn);

      expect(
        await screen.findByText("Opening quantity must be a positive integer")
      ).toBeInTheDocument();
      expect(inventoryApi.recordOpeningStock).not.toHaveBeenCalled();
    });
  });

  describe("AdjustmentModal", () => {
    it("submits valid stock adjustment", async () => {
      const onClose = vi.fn();
      vi.mocked(inventoryApi.recordAdjustment).mockResolvedValueOnce({
        balance: mockBalances[0],
        movement: mockMovements[1],
      });

      renderWithQueryClient(
        <AdjustmentModal
          isOpen={true}
          onClose={onClose}
          orgId="00000000-0000-0000-0000-000000000000"
          product={mockProducts[0]}
          currentOnHand={45}
          mode="adjustment"
        />
      );

      const deltaInput = screen.getByLabelText(/Quantity Delta/);
      fireEvent.change(deltaInput, { target: { value: "-10" } });

      const reasonInput = screen.getByLabelText(/Reason/);
      fireEvent.change(reasonInput, { target: { value: "Damaged inventory" } });

      const submitBtn = screen.getByText("Save Adjustment");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(inventoryApi.recordAdjustment).toHaveBeenCalledWith(
          "00000000-0000-0000-0000-000000000000",
          {
            product_id: mockProducts[0].id,
            quantity_delta: -10,
            reason: "Damaged inventory",
          },
          undefined,
          undefined
        );
        expect(onClose).toHaveBeenCalled();
      });
    });

    it("rejects reason shorter than 3 characters", async () => {
      renderWithQueryClient(
        <AdjustmentModal
          isOpen={true}
          onClose={vi.fn()}
          orgId="00000000-0000-0000-0000-000000000000"
          product={mockProducts[0]}
          currentOnHand={45}
          mode="adjustment"
        />
      );

      const reasonInput = screen.getByLabelText(/Reason/);
      fireEvent.change(reasonInput, { target: { value: "ab" } });

      const submitBtn = screen.getByText("Save Adjustment");
      fireEvent.click(submitBtn);

      expect(
        await screen.findByText("Reason is required (minimum 3 characters)")
      ).toBeInTheDocument();
      expect(inventoryApi.recordAdjustment).not.toHaveBeenCalled();
    });

    it("prevents negative stock in client validation", async () => {
      renderWithQueryClient(
        <AdjustmentModal
          isOpen={true}
          onClose={vi.fn()}
          orgId="00000000-0000-0000-0000-000000000000"
          product={mockProducts[0]}
          currentOnHand={10}
          mode="adjustment"
        />
      );

      const deltaInput = screen.getByLabelText(/Quantity Delta/);
      fireEvent.change(deltaInput, { target: { value: "-15" } });

      const reasonInput = screen.getByLabelText(/Reason/);
      fireEvent.change(reasonInput, { target: { value: "Overselling attempt" } });

      const submitBtn = screen.getByText("Save Adjustment");
      fireEvent.click(submitBtn);

      expect(
        await screen.findByText(/resulting balance cannot be negative/)
      ).toBeInTheDocument();
      expect(inventoryApi.recordAdjustment).not.toHaveBeenCalled();
    });
  });

  describe("MovementHistoryModal", () => {
    it("renders movement history table", async () => {
      renderWithQueryClient(
        <MovementHistoryModal
          isOpen={true}
          onClose={vi.fn()}
          orgId="00000000-0000-0000-0000-000000000000"
          product={mockProducts[0]}
        />
      );

      expect(await screen.findByText("Initial opening stock")).toBeInTheDocument();
      expect(screen.getByText("Movement History")).toBeInTheDocument();
      expect(screen.getByText("Sample write-off")).toBeInTheDocument();
      expect(screen.getByText("+50")).toBeInTheDocument();
      expect(screen.getByText("-5")).toBeInTheDocument();
    });
  });
});
