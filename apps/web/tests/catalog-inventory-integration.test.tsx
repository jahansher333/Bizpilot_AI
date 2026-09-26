import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InventoryView } from "@/components/inventory/inventory-view";
import { CatalogView } from "@/components/catalog/catalog-view";
import * as inventoryApi from "@/lib/api/inventory";
import * as catalogApi from "@/lib/api/catalog";

// Mock APIs
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
  listCategories: vi.fn(),
  getProduct: vi.fn(),
  createProduct: vi.fn(),
  updateProduct: vi.fn(),
  archiveProduct: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
  archiveCategory: vi.fn(),
}));

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const mockProducts = [
  {
    id: "p-1",
    organization_id: "org-1",
    code: "SKU-001",
    name: "Cotton Shirt",
    base_unit: "piece",
    default_price_minor: 150000,
    currency_code: "PKR",
    category_id: null,
    status: "active" as const,
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: null,
  },
  {
    id: "p-2",
    organization_id: "org-1",
    code: "SKU-002",
    name: "Linen Trousers",
    base_unit: "piece",
    default_price_minor: 250000,
    currency_code: "PKR",
    category_id: null,
    status: "active" as const,
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: null,
  },
  {
    id: "p-3",
    organization_id: "org-1",
    code: "SKU-003",
    name: "Silk Scarf",
    base_unit: "piece",
    default_price_minor: 95000,
    currency_code: "PKR",
    category_id: null,
    status: "active" as const,
    created_by_user_id: null,
    created_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:00:00Z",
    archived_at: null,
  },
];

const mockBalances = [
  {
    id: "b-1",
    organization_id: "org-1",
    product_id: "p-1",
    on_hand_quantity: 45, // In Stock (>10)
    version: 1,
    updated_at: "2026-09-24T01:00:00Z",
  },
  {
    id: "b-2",
    organization_id: "org-1",
    product_id: "p-2",
    on_hand_quantity: 4, // Low Stock (<=10)
    version: 1,
    updated_at: "2026-09-24T01:00:00Z",
  },
  {
    id: "b-3",
    organization_id: "org-1",
    product_id: "p-3",
    on_hand_quantity: 0, // Out of Stock
    version: 1,
    updated_at: "2026-09-24T01:00:00Z",
  },
];

describe("Catalog & Inventory Integration Polish (UX-003)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(catalogApi.listProducts).mockResolvedValue({
      items: mockProducts,
      total: mockProducts.length,
      limit: 100,
      offset: 0,
    });
    vi.mocked(catalogApi.listCategories).mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    });
    vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({
      items: mockBalances,
      total: mockBalances.length,
      limit: 100,
      offset: 0,
    });
  });

  it("renders bidirectional navigation between Catalog and Inventory", async () => {
    // InventoryView has link to Catalog
    const invView = renderWithQuery(<InventoryView orgId="org-1" userRole="owner" />);
    const toCatalogLink = await invView.findByRole("link", { name: /manage catalog/i });
    expect(toCatalogLink).toHaveAttribute("href", "/workspace/org-1/catalog");
    invView.unmount();

    // CatalogView has link to Inventory
    const catView = renderWithQuery(<CatalogView organizationId="org-1" initialRole="owner" />);
    const toInvLink = await catView.findByRole("link", { name: /check inventory stock/i });
    expect(toInvLink).toHaveAttribute("href", "/workspace/org-1/inventory");
    catView.unmount();
  });

  it("displays stock attention alert banner and filters products by status chips", async () => {
    renderWithQuery(<InventoryView orgId="org-1" userRole="owner" />);

    // Operational stock alert banner
    expect(
      await screen.findByText(/stock availability attention required/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/1 product\(s\) out of stock/i)).toBeInTheDocument();
    expect(screen.getByText(/1 product\(s\) below reorder threshold/i)).toBeInTheDocument();

    // Initially all 3 products are visible
    expect(screen.getByText("Cotton Shirt")).toBeInTheDocument();
    expect(screen.getByText("Linen Trousers")).toBeInTheDocument();
    expect(screen.getByText("Silk Scarf")).toBeInTheDocument();

    // Filter by Low Stock
    fireEvent.click(screen.getByRole("button", { name: /low stock/i }));
    expect(screen.getByText("Linen Trousers")).toBeInTheDocument();
    expect(screen.queryByText("Cotton Shirt")).not.toBeInTheDocument();
    expect(screen.queryByText("Silk Scarf")).not.toBeInTheDocument();

    // Filter by Out of Stock
    fireEvent.click(screen.getByRole("button", { name: /out of stock/i }));
    expect(screen.getByText("Silk Scarf")).toBeInTheDocument();
    expect(screen.queryByText("Cotton Shirt")).not.toBeInTheDocument();
    expect(screen.queryByText("Linen Trousers")).not.toBeInTheDocument();

    // Filter by In Stock
    fireEvent.click(screen.getByRole("button", { name: /in stock/i }));
    expect(screen.getByText("Cotton Shirt")).toBeInTheDocument();
    expect(screen.queryByText("Linen Trousers")).not.toBeInTheDocument();
    expect(screen.queryByText("Silk Scarf")).not.toBeInTheDocument();
  });

  it("enforces RBAC mutation boundaries for Staff role in Inventory", async () => {
    renderWithQuery(<InventoryView orgId="org-1" userRole="staff" />);

    expect(await screen.findByText("Cotton Shirt")).toBeInTheDocument();

    // Staff cannot perform opening stock, adjustments, or corrections
    expect(screen.queryByText("Record Opening Stock")).not.toBeInTheDocument();
    expect(screen.queryByText("Adjust Stock")).not.toBeInTheDocument();
    expect(screen.queryByText("Correct Count")).not.toBeInTheDocument();

    // Staff can view movement history
    expect(screen.getAllByText("History").length).toBe(3);
  });
});
