"use client";

import { useEffect, useState } from "react";
import { Product, parseMajorToMinor } from "@/lib/schemas/catalog";
import { useCategories, useCreateProduct, useUpdateProduct } from "@/hooks/use-catalog";

interface ProductModalProps {
  isOpen: boolean;
  onClose: () => void;
  organizationId: string;
  product?: Product | null;
  token?: string;
}

export function ProductModal({
  isOpen,
  onClose,
  organizationId,
  product,
  token,
}: ProductModalProps) {
  const isEditing = Boolean(product);

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [baseUnit, setBaseUnit] = useState("piece");
  const [priceMajor, setPriceMajor] = useState("");
  const [categoryId, setCategoryId] = useState<string>("");

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);

  // Fetch active categories for the dropdown
  const { data: categoriesData } = useCategories(
    organizationId,
    { status: "active", limit: 100 },
    token
  );
  // Also fetch all categories if editing to find name of an archived category
  const { data: allCategoriesData } = useCategories(
    organizationId,
    { status: "all", limit: 100 },
    token
  );

  const createMutation = useCreateProduct(organizationId, token);
  const updateMutation = useUpdateProduct(organizationId, token);
  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (product) {
      setCode(product.code);
      setName(product.name);
      setBaseUnit(product.base_unit || "piece");
      setPriceMajor((product.default_price_minor / 100).toFixed(2));
      setCategoryId(product.category_id || "");
    } else {
      setCode("");
      setName("");
      setBaseUnit("piece");
      setPriceMajor("");
      setCategoryId("");
    }
    setFieldErrors({});
    setApiError(null);
  }, [product, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});
    setApiError(null);

    const errors: Record<string, string> = {};

    const trimmedCode = code.trim();
    if (!trimmedCode) {
      errors.code = "Product code is required";
    } else if (trimmedCode.length > 64) {
      errors.code = "Product code must be at most 64 characters";
    }

    const trimmedName = name.trim();
    if (!trimmedName || trimmedName.length < 2) {
      errors.name = "Product name must be at least 2 characters";
    } else if (trimmedName.length > 255) {
      errors.name = "Product name must be at most 255 characters";
    }

    const trimmedUnit = baseUnit.trim();
    if (!trimmedUnit) {
      errors.baseUnit = "Base unit is required";
    } else if (trimmedUnit.length > 32) {
      errors.baseUnit = "Base unit must be at most 32 characters";
    }

    let minorUnits = 0;
    try {
      minorUnits = parseMajorToMinor(priceMajor);
    } catch (err: unknown) {
      errors.price = err instanceof Error ? err.message : "Invalid price";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    try {
      const selectedCatId = categoryId ? categoryId : null;

      if (isEditing && product) {
        await updateMutation.mutateAsync({
          productId: product.id,
          data: {
            code: trimmedCode,
            name: trimmedName,
            base_unit: trimmedUnit,
            default_price_minor: minorUnits,
            category_id: selectedCatId,
          },
        });
      } else {
        await createMutation.mutateAsync({
          code: trimmedCode,
          name: trimmedName,
          base_unit: trimmedUnit,
          default_price_minor: minorUnits,
          category_id: selectedCatId,
        });
      }
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setApiError(err.message);
      } else {
        setApiError("Failed to save product");
      }
    }
  };

  const activeCategories = categoriesData?.items || [];
  const currentCategory = product?.category_id
    ? allCategoriesData?.items.find((c) => c.id === product.category_id)
    : null;
  const isCurrentArchived = currentCategory && currentCategory.status === "archived";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="product-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
    >
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h2 id="product-modal-title" className="text-lg font-semibold text-slate-900">
            {isEditing ? "Edit Product" : "New Product"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 focus:outline-none"
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="product-code" className="block text-sm font-medium text-slate-700">
                Code / SKU <span className="text-red-500">*</span>
              </label>
              <input
                id="product-code"
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="e.g. PROD-001"
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                disabled={isPending}
                autoFocus
              />
              {fieldErrors.code && <p className="mt-1 text-xs text-red-600">{fieldErrors.code}</p>}
            </div>

            <div>
              <label htmlFor="product-unit" className="block text-sm font-medium text-slate-700">
                Base Unit <span className="text-red-500">*</span>
              </label>
              <input
                id="product-unit"
                type="text"
                value={baseUnit}
                onChange={(e) => setBaseUnit(e.target.value)}
                placeholder="e.g. piece, kg, box"
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                disabled={isPending}
              />
              {fieldErrors.baseUnit && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.baseUnit}</p>
              )}
            </div>
          </div>

          <div>
            <label htmlFor="product-name" className="block text-sm font-medium text-slate-700">
              Product Name <span className="text-red-500">*</span>
            </label>
            <input
              id="product-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Premium Basmati Rice 5kg"
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              disabled={isPending}
            />
            {fieldErrors.name && <p className="mt-1 text-xs text-red-600">{fieldErrors.name}</p>}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="product-price" className="block text-sm font-medium text-slate-700">
                Default Price (PKR) <span className="text-red-500">*</span>
              </label>
              <div className="relative mt-1">
                <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-xs text-slate-400">
                  Rs.
                </span>
                <input
                  id="product-price"
                  type="text"
                  value={priceMajor}
                  onChange={(e) => setPriceMajor(e.target.value)}
                  placeholder="0.00"
                  className="block w-full rounded-lg border border-slate-300 py-2 pr-3 pl-10 text-sm shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  disabled={isPending}
                />
              </div>
              {fieldErrors.price && <p className="mt-1 text-xs text-red-600">{fieldErrors.price}</p>}
            </div>

            <div>
              <label htmlFor="product-category" className="block text-sm font-medium text-slate-700">
                Category
              </label>
              <select
                id="product-category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                disabled={isPending}
              >
                <option value="">(None - Uncategorized)</option>
                {isCurrentArchived && currentCategory && (
                  <option value={currentCategory.id}>
                    {currentCategory.name} (Archived)
                  </option>
                )}
                {activeCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {apiError && (
            <div role="alert" className="rounded-md bg-red-50 p-3 text-xs text-red-700">
              {apiError}
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 focus:outline-none disabled:opacity-50"
            >
              {isPending ? "Saving..." : isEditing ? "Save Changes" : "Create Product"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
