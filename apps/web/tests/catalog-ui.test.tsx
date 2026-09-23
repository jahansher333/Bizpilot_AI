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
import { ProductModal } from "@/components/catalog/product-modal";
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
  describe("CategoryList Component", () => {
    it("renders categories table and mutation controls for Owner", async () => {
      vi.mocked(catalogApi.listCategories).mockResolvedValueOnce({
        items: mockCategories,
        total: 2,
        limit: 50,
        offset: 0,
      });

      renderWithQueryClient(
        <CategoryList organizationId="org-100" userRole="owner" />
      );

      // Loading state shown initially
      expect(screen.getByTestId("category-loading")).toBeInTheDocument();

      // Wait for table to render
      await waitFor(() => {
        expect(screen.getByText("Beverages")).toBeInTheDocument();
      });

      expect(screen.getByText("Old Category")).toBeInTheDocument();
      // Owner must see mutation controls
      expect(screen.getByRole("button", { name: "+ New Category" })).toBeInTheDocument();
      expect(screen.getByLabelText("Edit Beverages")).toBeInTheDocument();
      expect(screen.getByLabelText("Archive Beverages")).toBeInTheDocument();
    });

    it("renders categories in read-only mode for Staff (no mutation controls)", async () => {
      vi.mocked(catalogApi.listCategories).mockResolvedValueOnce({
        items: mockCategories,
        total: 2,
        limit: 50,
        offset: 0,
      });

      renderWithQueryClient(
        <CategoryList organizationId="org-100" userRole="staff" />
      );

      await waitFor(() => {
        expect(screen.getByText("Beverages")).toBeInTheDocument();
      });

      // Staff must NOT see mutation controls
      expect(screen.queryByRole("button", { name: "+ New Category" })).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Edit Beverages")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Archive Beverages")).not.toBeInTheDocument();
    });

    it("renders empty state when no categories are returned", async () => {
      vi.mocked(catalogApi.listCategories).mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      });

      renderWithQueryClient(
        <CategoryList organizationId="org-100" userRole="owner" />
      );

      await waitFor(() => {
        expect(screen.getByTestId("category-empty")).toBeInTheDocument();
      });
      expect(screen.getByText("No categories found")).toBeInTheDocument();
    });

    it("renders error state with retry button on API failure", async () => {
      vi.mocked(catalogApi.listCategories).mockRejectedValueOnce(
        new Error("Network connection error")
      );

      renderWithQueryClient(
        <CategoryList organizationId="org-100" userRole="owner" />
      );

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
      expect(screen.getByText("Failed to load categories")).toBeInTheDocument();
      expect(screen.getByText("Network connection error")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    });

    it("opens archive confirmation dialog when Archive is clicked", async () => {
      vi.mocked(catalogApi.listCategories).mockResolvedValue({
        items: [mockCategories[0]], // active category
        total: 1,
        limit: 50,
        offset: 0,
      });

      renderWithQueryClient(
        <CategoryList organizationId="org-100" userRole="manager" />
      );

      await waitFor(() => {
        expect(screen.getByText("Beverages")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByLabelText("Archive Beverages"));

      // Archive confirmation modal should appear
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Archive Category")).toBeInTheDocument();
      expect(
        screen.getByText(/Are you sure you want to archive/i)
      ).toBeInTheDocument();

      // Click Cancel closes dialog
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // 6. CategoryModal Component
  // ============================================================================
  describe("CategoryModal Component", () => {
    it("validates client input and submits create request", async () => {
      vi.mocked(catalogApi.createCategory).mockResolvedValueOnce({
        id: "new-cat-id",
        organization_id: "org-100",
        name: "Dairy",
        status: "active",
        created_by_user_id: "user-1",
        created_at: "2026-09-23T12:00:00Z",
        updated_at: "2026-09-23T12:00:00Z",
        archived_at: null,
      });

      const handleClose = vi.fn();
      renderWithQueryClient(
        <CategoryModal
          isOpen={true}
          onClose={handleClose}
          organizationId="org-100"
          category={null}
        />
      );

      expect(screen.getByRole("heading", { name: "New Category" })).toBeInTheDocument();

      const input = screen.getByLabelText(/Category Name/i);
      fireEvent.change(input, { target: { value: "Dairy" } });

      const submitBtn = screen.getByRole("button", { name: "Create Category" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(catalogApi.createCategory).toHaveBeenCalledWith(
          "org-100",
          { name: "Dairy" },
          undefined
        );
        expect(handleClose).toHaveBeenCalled();
      });
    });

    it("displays validation error when submitting too short name", async () => {
      renderWithQueryClient(
        <CategoryModal
          isOpen={true}
          onClose={vi.fn()}
          organizationId="org-100"
          category={null}
        />
      );

      const input = screen.getByLabelText(/Category Name/i);
      fireEvent.change(input, { target: { value: "A" } });

      const submitBtn = screen.getByRole("button", { name: "Create Category" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(
          screen.getByText("Category name must be at least 2 characters")
        ).toBeInTheDocument();
      });
      expect(catalogApi.createCategory).not.toHaveBeenCalled();
    });
  });

  // ============================================================================
  // 7. ProductList Component & Role Permissions
  // ============================================================================
  describe("ProductList Component", () => {
    it("renders products table with formatted PKR prices and controls for Owner", async () => {
      vi.mocked(catalogApi.listProducts).mockResolvedValueOnce({
        items: mockProducts,
        total: 2,
        limit: 50,
        offset: 0,
      });
      vi.mocked(catalogApi.listCategories).mockResolvedValueOnce({
        items: mockCategories,
        total: 2,
        limit: 200,
        offset: 0,
      });

      renderWithQueryClient(
        <ProductList organizationId="org-100" userRole="owner" />
      );

      await waitFor(() => {
        expect(screen.getByText("TEA-001")).toBeInTheDocument();
      });

      expect(screen.getByText("Black Tea 500g")).toBeInTheDocument();
      expect(screen.getByText("PKR 450.00")).toBeInTheDocument();
      expect(screen.getByText("WATER-01")).toBeInTheDocument();
      expect(screen.getByText("PKR 120.00")).toBeInTheDocument();

      // Owner controls
      expect(screen.getByRole("button", { name: "+ New Product" })).toBeInTheDocument();
      expect(screen.getByLabelText("Edit Black Tea 500g")).toBeInTheDocument();
      expect(screen.getByLabelText("Archive Black Tea 500g")).toBeInTheDocument();
    });

    it("renders products in read-only mode for Staff", async () => {
      vi.mocked(catalogApi.listProducts).mockResolvedValueOnce({
        items: mockProducts,
        total: 2,
        limit: 50,
        offset: 0,
      });
      vi.mocked(catalogApi.listCategories).mockResolvedValueOnce({
        items: mockCategories,
        total: 2,
        limit: 200,
        offset: 0,
      });

      renderWithQueryClient(
        <ProductList organizationId="org-100" userRole="staff" />
      );

      await waitFor(() => {
        expect(screen.getByText("TEA-001")).toBeInTheDocument();
      });

      // Staff must NOT see mutation controls
      expect(screen.queryByRole("button", { name: "+ New Product" })).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Edit Black Tea 500g")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Archive Black Tea 500g")).not.toBeInTheDocument();
    });

    it("renders empty state when no products match", async () => {
      vi.mocked(catalogApi.listProducts).mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      });
      vi.mocked(catalogApi.listCategories).mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 200,
        offset: 0,
      });

      renderWithQueryClient(
        <ProductList organizationId="org-100" userRole="owner" />
      );

      await waitFor(() => {
        expect(screen.getByTestId("product-empty")).toBeInTheDocument();
      });
      expect(screen.getByText("No products found")).toBeInTheDocument();
    });
  });

  // ============================================================================
  // 8. ProductModal Component
  // ============================================================================
  describe("ProductModal Component", () => {
    it("submits create product with major price parsed to minor units", async () => {
      vi.mocked(catalogApi.listCategories).mockResolvedValue({
        items: mockCategories,
        total: 2,
        limit: 100,
        offset: 0,
      });

      vi.mocked(catalogApi.createProduct).mockResolvedValueOnce({
        id: "prod-new",
        organization_id: "org-100",
        category_id: "cat-1111-1111-1111-111111111111",
        code: "COFFEE-01",
        name: "Coffee Beans 1kg",
        base_unit: "pack",
        default_price_minor: 250000,
        currency_code: "PKR",
        status: "active",
        created_by_user_id: "user-1",
        created_at: "2026-09-23T12:00:00Z",
        updated_at: "2026-09-23T12:00:00Z",
        archived_at: null,
      });

      const handleClose = vi.fn();
      renderWithQueryClient(
        <ProductModal
          isOpen={true}
          onClose={handleClose}
          organizationId="org-100"
          product={null}
        />
      );

      expect(screen.getByRole("heading", { name: "New Product" })).toBeInTheDocument();

      fireEvent.change(screen.getByLabelText(/Code \/ SKU/i), {
        target: { value: "COFFEE-01" },
      });
      fireEvent.change(screen.getByLabelText(/Product Name/i), {
        target: { value: "Coffee Beans 1kg" },
      });
      fireEvent.change(screen.getByLabelText(/Base Unit/i), {
        target: { value: "pack" },
      });
      fireEvent.change(screen.getByLabelText(/Default Price/i), {
        target: { value: "2500.00" },
      });

      fireEvent.click(screen.getByRole("button", { name: "Create Product" }));

      await waitFor(() => {
        expect(catalogApi.createProduct).toHaveBeenCalledWith(
          "org-100",
          {
            code: "COFFEE-01",
            name: "Coffee Beans 1kg",
            base_unit: "pack",
            default_price_minor: 250000,
            category_id: null,
          },
          undefined
        );
        expect(handleClose).toHaveBeenCalled();
      });
    });

    it("displays validation error when price is invalid", async () => {
      vi.mocked(catalogApi.listCategories).mockResolvedValue({
        items: [],
        total: 0,
        limit: 100,
        offset: 0,
      });

      renderWithQueryClient(
        <ProductModal
          isOpen={true}
          onClose={vi.fn()}
          organizationId="org-100"
          product={null}
        />
      );

      fireEvent.change(screen.getByLabelText(/Code \/ SKU/i), {
        target: { value: "P-1" },
      });
      fireEvent.change(screen.getByLabelText(/Product Name/i), {
        target: { value: "Product One" },
      });
      fireEvent.change(screen.getByLabelText(/Default Price/i), {
        target: { value: "invalid-price" },
      });

      fireEvent.click(screen.getByRole("button", { name: "Create Product" }));

      await waitFor(() => {
        expect(
          screen.getByText(/Invalid price format/i)
        ).toBeInTheDocument();
      });
      expect(catalogApi.createProduct).not.toHaveBeenCalled();
    });
  });

  // ============================================================================
  // 9. CatalogView Component (Tabs & Role Switcher)
  // ============================================================================
  describe("CatalogView Component", () => {
    it("switches tabs between Products and Categories", async () => {
      vi.mocked(catalogApi.listProducts).mockResolvedValue({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      });
      vi.mocked(catalogApi.listCategories).mockResolvedValue({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      });

      renderWithQueryClient(
        <CatalogView organizationId="org-100" initialRole="owner" />
      );

      expect(screen.getByText("Catalog Management")).toBeInTheDocument();

      // Initially on Products tab
      await waitFor(() => {
        expect(screen.getByTestId("product-empty")).toBeInTheDocument();
      });

      // Click Categories tab
      fireEvent.click(screen.getByRole("button", { name: "Categories" }));

      await waitFor(() => {
        expect(screen.getByTestId("category-empty")).toBeInTheDocument();
      });
    });
  });
});
