import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  formatPriceMinor,
  parseMajorToMinor,
  categoryCreateSchema,
  categoryUpdateSchema,
  productCreateSchema,
  productUpdateSchema,
  Category,
  Product,
} from "@/lib/schemas/catalog";
import { catalogQueryKeys } from "@/hooks/use-catalog";
import { ApiError } from "@/lib/api/catalog";
import { CategoryList } from "@/components/catalog/category-list";
import { ProductList } from "@/components/catalog/product-list";
import { CategoryModal } from "@/components/catalog/category-modal";
import { ProductSheet } from "@/components/catalog/product-sheet";
import * as inventoryApi from "@/lib/api/inventory";
import { CatalogView } from "@/components/catalog/catalog-view";
import * as catalogApi from "@/lib/api/catalog";

// Mock the API client functions
vi.mock("@/lib/api/catalog", async (importOriginal) => {
  const actual = await importOriginal<typeof catalogApi>();
  return {
    ...actual,
    listCategories: vi.fn(),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    archiveCategory: vi.fn(),
    listProducts: vi.fn(),
    getProduct: vi.fn(),
    createProduct: vi.fn(),
    updateProduct: vi.fn(),
    archiveProduct: vi.fn(),
  };
});

vi.mock("@/lib/api/inventory", () => ({
  fetchBalances: vi.fn(),
  recordOpeningStock: vi.fn(),
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

const mockCategories: Category[] = [
  {
    id: "cat-1111-1111-1111-111111111111",
    organization_id: "org-100",
    name: "Beverages",
    status: "active",
    created_by_user_id: "user-1",
    created_at: "2026-09-23T10:00:00Z",
    updated_at: "2026-09-23T10:00:00Z",
    archived_at: null,
  },
  {
    id: "cat-2222-2222-2222-222222222222",
    organization_id: "org-100",
    name: "Old Category",
    status: "archived",
    created_by_user_id: "user-1",
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-22T10:00:00Z",
    archived_at: "2026-09-22T10:00:00Z",
  },
];

const mockProducts: Product[] = [
  {
    id: "prod-1111-1111-1111-111111111111",
    organization_id: "org-100",
    category_id: "cat-1111-1111-1111-111111111111",
    code: "TEA-001",
    name: "Black Tea 500g",
    base_unit: "pack",
    default_price_minor: 45000,
    currency_code: "PKR",
    status: "active",
    created_by_user_id: "user-1",
    created_at: "2026-09-23T10:00:00Z",
    updated_at: "2026-09-23T10:00:00Z",
    archived_at: null,
  },
  {
    id: "prod-2222-2222-2222-222222222222",
    organization_id: "org-100",
    category_id: null,
    code: "WATER-01",
    name: "Mineral Water 1.5L",
    base_unit: "bottle",
    default_price_minor: 12000,
    currency_code: "PKR",
    status: "active",
    created_by_user_id: "user-1",
    created_at: "2026-09-23T11:00:00Z",
    updated_at: "2026-09-23T11:00:00Z",
    archived_at: null,
  },
];

describe("CAT-003: Catalog Frontend Slice", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ============================================================================
  // 1. Money & Price Helpers
  // ============================================================================
  describe("Deterministic Money Helpers", () => {
    it("formats minor units to PKR string correctly", () => {
      expect(formatPriceMinor(150000)).toBe("PKR 1,500.00");
      expect(formatPriceMinor(0)).toBe("PKR 0.00");
      expect(formatPriceMinor(50)).toBe("PKR 0.50");
      expect(formatPriceMinor(5)).toBe("PKR 0.05");
      expect(formatPriceMinor(123456789)).toBe("PKR 1,234,567.89");
    });

    it("handles negative or invalid values gracefully in formatPriceMinor", () => {
      expect(formatPriceMinor(-100)).toBe("PKR 0.00");
      expect(formatPriceMinor(NaN)).toBe("PKR 0.00");
    });

    it("parses valid major unit strings to integer minor units", () => {
      expect(parseMajorToMinor("500")).toBe(50000);
      expect(parseMajorToMinor("500.5")).toBe(50050);
      expect(parseMajorToMinor("500.50")).toBe(50050);
      expect(parseMajorToMinor("0.05")).toBe(5);
      expect(parseMajorToMinor("0.1")).toBe(10);
      expect(parseMajorToMinor("0")).toBe(0);
      expect(parseMajorToMinor("  123.45  ")).toBe(12345);
    });

    it("rejects invalid or unsafe major unit strings in parseMajorToMinor", () => {
      expect(() => parseMajorToMinor("")).toThrow("Price is required");
      expect(() => parseMajorToMinor("   ")).toThrow("Price is required");
      expect(() => parseMajorToMinor("-50")).toThrow();
      expect(() => parseMajorToMinor("12.345")).toThrow(); // > 2 decimals
      expect(() => parseMajorToMinor("12.3.4")).toThrow();
      expect(() => parseMajorToMinor("abc")).toThrow();
      expect(() => parseMajorToMinor("$50")).toThrow();
    });
  });

  // ============================================================================
  // 2. Zod Schema Validation
  // ============================================================================
  describe("Zod Validation Schemas", () => {
    it("validates valid category create/update payloads", () => {
      expect(categoryCreateSchema.safeParse({ name: "Beverages" }).success).toBe(true);
      expect(categoryUpdateSchema.safeParse({ name: "Soft Drinks" }).success).toBe(true);
    });

    it("rejects invalid category names (too short, empty, too long)", () => {
      expect(categoryCreateSchema.safeParse({ name: "A" }).success).toBe(false);
      expect(categoryCreateSchema.safeParse({ name: "   " }).success).toBe(false);
      expect(categoryCreateSchema.safeParse({ name: "X".repeat(101) }).success).toBe(false);
    });

    it("validates valid product create payloads", () => {
      const valid = productCreateSchema.safeParse({
        code: "PROD-001",
        name: "Test Product",
        base_unit: "piece",
        price_major: "150.00",
      });
      expect(valid.success).toBe(true);
    });

    it("rejects invalid product payloads", () => {
      expect(
        productCreateSchema.safeParse({
          code: "",
          name: "Test",
          base_unit: "piece",
          price_major: "100",
        }).success
      ).toBe(false);

      expect(
        productCreateSchema.safeParse({
          code: "P1",
          name: "T", // too short
          base_unit: "piece",
          price_major: "100",
        }).success
      ).toBe(false);

      expect(
        productCreateSchema.safeParse({
          code: "P1",
          name: "Valid Name",
          base_unit: "piece",
          price_major: "-50.00", // negative price
        }).success
      ).toBe(false);
    });
  });

  // ============================================================================
  // 3. Tenant Cache Isolation & Query Keys
  // ============================================================================
  describe("Query Keys & Tenant Isolation", () => {
    it("strictly namespaces query keys by organizationId", () => {
      const org1Keys = catalogQueryKeys.categories("org-1", { status: "active" });
      const org2Keys = catalogQueryKeys.categories("org-2", { status: "active" });

      expect(org1Keys[0]).toBe("catalog");
      expect(org1Keys[1]).toBe("org-1");
      expect(org2Keys[1]).toBe("org-2");
      expect(org1Keys).not.toEqual(org2Keys);

      const prodKeys1 = catalogQueryKeys.products("org-1");
      const prodKeys2 = catalogQueryKeys.products("org-2");
      expect(prodKeys1[1]).toBe("org-1");
      expect(prodKeys2[1]).toBe("org-2");
      expect(prodKeys1).not.toEqual(prodKeys2);
    });
  });

  // ============================================================================
  // 4. ApiError Handling
  // ============================================================================
  describe("ApiError Handling", () => {
    it("correctly constructs ApiError with status and code", () => {
      const err = new ApiError("A product with code already exists", 409, "CONFLICT");
      expect(err.message).toBe("A product with code already exists");
      expect(err.status).toBe(409);
      expect(err.code).toBe("CONFLICT");
      expect(err.name).toBe("ApiError");
    });
  });

  // ============================================================================
  // 5. CategoryList Component & Role Permissions
  // ============================================================================
  // ============================================================================
  // R4 design components
  // ============================================================================
  function mockCatalog(products: Product[] = mockProducts, categories: Category[] = mockCategories) {
    vi.mocked(catalogApi.listCategories).mockResolvedValue({ items: categories, total: categories.length, limit: 100, offset: 0 });
    vi.mocked(catalogApi.listProducts).mockImplementation(async (_org, params) => {
      const status = params?.status;
      const filtered = products.filter((p) => (status === "active" ? p.status === "active" : true) && (!params?.category_id || p.category_id === params.category_id));
      return { items: filtered, total: filtered.length, limit: params?.limit ?? 50, offset: 0 };
    });
    vi.mocked(inventoryApi.fetchBalances).mockResolvedValue({
      items: [
        { id: "b1", organization_id: "org-100", product_id: mockProducts[0].id, on_hand_quantity: 4, version: 1, updated_at: "2026-09-24T00:00:00Z" },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });
  }

  describe("CategoryList Component", () => {
    it("renders categories with status and actions for Owner", async () => {
      mockCatalog();
      renderWithQueryClient(<CategoryList organizationId="org-100" userRole="owner" productCounts={new Map([[mockCategories[0].id, 1]])} />);
      expect(await screen.findByText("Beverages")).toBeInTheDocument();
      expect(screen.getByText("Old Category")).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: "Products" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Rename Beverages" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Archive Beverages" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Archive Old Category" })).not.toBeInTheDocument();
      expect(catalogApi.listCategories).toHaveBeenCalledWith("org-100", { status: "all", limit: 100 }, undefined);
    });

    it("is read-only for Staff", async () => {
      mockCatalog();
      renderWithQueryClient(<CategoryList organizationId="org-100" userRole="staff" />);
      expect(await screen.findByText("Beverages")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /rename/i })).not.toBeInTheDocument();
    });

    it("shows an empty state", async () => {
      mockCatalog(mockProducts, []);
      renderWithQueryClient(<CategoryList organizationId="org-100" userRole="owner" />);
      expect(await screen.findByText("No categories yet")).toBeInTheDocument();
    });

    it("shows an error with retry", async () => {
      vi.mocked(catalogApi.listCategories).mockRejectedValue(new Error("down"));
      renderWithQueryClient(<CategoryList organizationId="org-100" userRole="owner" />);
      expect(await screen.findByText("Couldn\u2019t load your categories")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    });

    it("confirms before archiving and calls the API", async () => {
      mockCatalog();
      vi.mocked(catalogApi.archiveCategory).mockResolvedValue({ ...mockCategories[0], status: "archived" });
      renderWithQueryClient(<CategoryList organizationId="org-100" userRole="owner" />);
      fireEvent.click(await screen.findByRole("button", { name: "Archive Beverages" }));
      expect(screen.getByRole("alertdialog", { name: /archive “beverages”\?/i })).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Archive category" }));
      await waitFor(() => expect(catalogApi.archiveCategory).toHaveBeenCalledWith("org-100", mockCategories[0].id, undefined));
    });
  });

  describe("CategoryModal Component", () => {
    it("validates and creates a category", async () => {
      vi.mocked(catalogApi.createCategory).mockResolvedValue(mockCategories[0]);
      const onClose = vi.fn();
      renderWithQueryClient(<CategoryModal organizationId="org-100" isOpen onClose={onClose} />);
      fireEvent.change(screen.getByLabelText("Category name"), { target: { value: "A" } });
      fireEvent.click(screen.getByRole("button", { name: "Create category" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(/at least 2 characters/i);

      fireEvent.change(screen.getByLabelText("Category name"), { target: { value: "Spices" } });
      fireEvent.click(screen.getByRole("button", { name: "Create category" }));
      await waitFor(() => expect(catalogApi.createCategory).toHaveBeenCalledWith("org-100", { name: "Spices" }, undefined));
      await waitFor(() => expect(onClose).toHaveBeenCalled());
    });

    it("renames an existing category", async () => {
      vi.mocked(catalogApi.updateCategory).mockResolvedValue({ ...mockCategories[0], name: "Drinks" });
      renderWithQueryClient(<CategoryModal organizationId="org-100" isOpen onClose={vi.fn()} category={mockCategories[0]} />);
      expect(screen.getByLabelText("Category name")).toHaveValue("Beverages");
      fireEvent.change(screen.getByLabelText("Category name"), { target: { value: "Drinks" } });
      fireEvent.click(screen.getByRole("button", { name: "Save name" }));
      await waitFor(() => expect(catalogApi.updateCategory).toHaveBeenCalledWith("org-100", mockCategories[0].id, { name: "Drinks" }, undefined));
    });
  });

  describe("ProductList Component", () => {
    it("shows summary, PKR prices, stock and category names for Owner", async () => {
      mockCatalog();
      renderWithQueryClient(<ProductList organizationId="org-100" userRole="owner" />);
      const summary = await screen.findByRole("region", { name: "Catalog summary" });
      await waitFor(() => expect(summary).toHaveTextContent("Low stock1"));

      const table = screen.getByRole("table");
      expect(table).toHaveTextContent("Black Tea 500g");
      expect(table).toHaveTextContent("450");
      expect(table).toHaveTextContent("Beverages");
      expect(table).toHaveTextContent("low stock");
      expect(screen.getAllByRole("link", { name: "Black Tea 500g" })[0]).toHaveAttribute("href", `/workspace/org-100/inventory/${mockProducts[0].id}`);
      expect(screen.getByRole("button", { name: "Edit Black Tea 500g" })).toBeInTheDocument();
    });

    it("is read-only for Staff", async () => {
      mockCatalog();
      renderWithQueryClient(<ProductList organizationId="org-100" userRole="staff" />);
      expect(await screen.findByRole("table")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /^edit/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /^archive/i })).not.toBeInTheDocument();
    });

    it("searches by name or code and offers to add a missing product", async () => {
      mockCatalog();
      renderWithQueryClient(<ProductList organizationId="org-100" userRole="owner" />);
      await screen.findByRole("table");
      fireEvent.change(screen.getByLabelText("Search products"), { target: { value: "WATER" } });
      expect(screen.getByRole("table")).toHaveTextContent("Mineral Water 1.5L");
      expect(screen.getByRole("table")).not.toHaveTextContent("Black Tea 500g");

      fireEvent.change(screen.getByLabelText("Search products"), { target: { value: "Saffron" } });
      expect(screen.getByText("No products match “Saffron”")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Add “Saffron” as product" })).toBeInTheDocument();
    });

    it("filters by category on the server", async () => {
      mockCatalog();
      renderWithQueryClient(<ProductList organizationId="org-100" userRole="owner" />);
      fireEvent.click(await screen.findByRole("button", { name: "Beverages" }));
      await waitFor(() =>
        expect(catalogApi.listProducts).toHaveBeenCalledWith("org-100", expect.objectContaining({ category_id: mockCategories[0].id }), undefined)
      );
    });

    it("shows the first-product empty state", async () => {
      mockCatalog([], mockCategories);
      renderWithQueryClient(<ProductList organizationId="org-100" userRole="owner" />);
      expect(await screen.findByText("Add your first product")).toBeInTheDocument();
    });
  });

  describe("ProductSheet Component", () => {
    it("creates a product with price in minor units, then records opening stock", async () => {
      mockCatalog();
      vi.mocked(catalogApi.createProduct).mockResolvedValue({ ...mockProducts[0], id: "prod-new" });
      vi.mocked(inventoryApi.recordOpeningStock).mockResolvedValue({} as never);
      const onClose = vi.fn();
      renderWithQueryClient(<ProductSheet organizationId="org-100" open onClose={onClose} />);

      fireEvent.change(screen.getByLabelText("Product name"), { target: { value: "Green Tea 250g" } });
      fireEvent.change(screen.getByLabelText("Product code"), { target: { value: "TEA-002" } });
      fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "520.50" } });
      fireEvent.change(screen.getByLabelText(/opening stock/i), { target: { value: "40" } });
      fireEvent.click(screen.getByRole("button", { name: "Create product" }));

      await waitFor(() =>
        expect(catalogApi.createProduct).toHaveBeenCalledWith(
          "org-100",
          { code: "TEA-002", name: "Green Tea 250g", base_unit: "piece", default_price_minor: 52050, category_id: null },
          undefined
        )
      );
      await waitFor(() =>
        expect(inventoryApi.recordOpeningStock).toHaveBeenCalledWith("org-100", { product_id: "prod-new", quantity: 40, reason: "Opening stock" }, undefined)
      );
      await waitFor(() => expect(onClose).toHaveBeenCalled());
    });

    it("shows field errors for an invalid price", async () => {
      mockCatalog();
      renderWithQueryClient(<ProductSheet organizationId="org-100" open onClose={vi.fn()} />);
      fireEvent.change(screen.getByLabelText("Product name"), { target: { value: "Green Tea" } });
      fireEvent.change(screen.getByLabelText("Product code"), { target: { value: "TEA-002" } });
      fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "12.345" } });
      fireEvent.click(screen.getByRole("button", { name: "Create product" }));
      expect(await screen.findByText(/at most 2 decimal places/i)).toBeInTheDocument();
      expect(catalogApi.createProduct).not.toHaveBeenCalled();
    });

    it("shows a duplicate code from the server on the code field", async () => {
      mockCatalog();
      vi.mocked(catalogApi.createProduct).mockRejectedValue(new ApiError("Product code already exists", 409, "CONFLICT"));
      renderWithQueryClient(<ProductSheet organizationId="org-100" open onClose={vi.fn()} />);
      fireEvent.change(screen.getByLabelText("Product name"), { target: { value: "Green Tea" } });
      fireEvent.change(screen.getByLabelText("Product code"), { target: { value: "TEA-001" } });
      fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "500" } });
      fireEvent.click(screen.getByRole("button", { name: "Create product" }));
      expect(await screen.findByText("Product code already exists")).toBeInTheDocument();
      expect(screen.getByLabelText("Product code")).toHaveAttribute("aria-invalid", "true");
    });

    it("prefills and updates an existing product", async () => {
      mockCatalog();
      vi.mocked(catalogApi.updateProduct).mockResolvedValue(mockProducts[0]);
      renderWithQueryClient(<ProductSheet organizationId="org-100" open onClose={vi.fn()} product={{ ...mockProducts[0], category_id: null }} />);
      expect(screen.getByLabelText("Selling price")).toHaveValue("450");
      expect(screen.queryByLabelText(/opening stock/i)).not.toBeInTheDocument();
      fireEvent.change(screen.getByLabelText("Selling price"), { target: { value: "480" } });
      fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
      await waitFor(() =>
        expect(catalogApi.updateProduct).toHaveBeenCalledWith("org-100", mockProducts[0].id, expect.objectContaining({ default_price_minor: 48000 }), undefined)
      );
    });
  });

  describe("CatalogView Component", () => {
    it("switches between Products and Categories with counts", async () => {
      mockCatalog();
      renderWithQueryClient(<CatalogView organizationId="org-100" userRole="owner" />);
      expect(await screen.findByRole("button", { name: /add product/i })).toBeInTheDocument();
      fireEvent.click(screen.getByRole("tab", { name: /categories/i }));
      expect(await screen.findByRole("button", { name: /new category/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /categories/i })).toHaveAttribute("aria-selected", "true");
    });

    it("hides create actions for Staff", async () => {
      mockCatalog();
      renderWithQueryClient(<CatalogView organizationId="org-100" userRole="staff" />);
      await screen.findByRole("tab", { name: /products/i });
      expect(screen.queryByRole("button", { name: /add product/i })).not.toBeInTheDocument();
    });
  });
});
