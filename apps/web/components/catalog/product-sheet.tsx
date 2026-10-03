"use client";

import React, { useEffect, useState } from "react";
import { Product, parseMajorToMinor, productCreateSchema } from "@/lib/schemas/catalog";
import { useCategories, useCreateProduct, useUpdateProduct } from "@/hooks/use-catalog";
import { useRecordOpeningStock } from "@/hooks/use-inventory";
import { ApiError } from "@/lib/api/catalog";
import { Sheet } from "@/components/ui/sheet";
import { Icon } from "@/components/ui/icon";
import { useToast } from "@/components/ui/toast";

interface ProductSheetProps {
  organizationId: string;
  open: boolean;
  onClose: () => void;
  product?: Product | null;
  initialName?: string;
  token?: string;
}

function majorString(minor: number): string {
  return minor % 100 === 0 ? String(minor / 100) : (minor / 100).toFixed(2);
}

/** Design "Add product" sheet. Opening stock (optional) is recorded right after the product is created. */
export function ProductSheet({ organizationId, open, onClose, product, initialName = "", token }: ProductSheetProps) {
  const isEdit = !!product;
  const { data: categories } = useCategories(organizationId, { status: "active", limit: 100 }, token);
  const createMutation = useCreateProduct(organizationId, token);
  const updateMutation = useUpdateProduct(organizationId, token);
  const openingMutation = useRecordOpeningStock(organizationId, token);
  const { notify } = useToast();

  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [baseUnit, setBaseUnit] = useState("piece");
  const [price, setPrice] = useState("");
  const [openingStock, setOpeningStock] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(product?.name ?? initialName);
    setCode(product?.code ?? "");
    setCategoryId(product?.category_id ?? "");
    setBaseUnit(product?.base_unit ?? "piece");
    setPrice(product ? majorString(product.default_price_minor) : "");
    setOpeningStock("");
    setFieldErrors({});
    setServerError(null);
  }, [open, product, initialName]);

  const isPending = createMutation.isPending || updateMutation.isPending || openingMutation.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    const parsed = productCreateSchema.safeParse({ code, name, base_unit: baseUnit, price_major: price, category_id: categoryId || null });
    const errors: Record<string, string> = {};
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        const key = String(issue.path[0] ?? "form");
        if (!errors[key]) errors[key] = issue.message;
      }
    }
    const openingQty = openingStock.trim() === "" ? 0 : Number(openingStock);
    if (!isEdit && openingStock.trim() !== "" && (!Number.isInteger(openingQty) || openingQty <= 0)) {
      errors.opening = "Enter a whole number above 0, or leave it empty";
    }
    setFieldErrors(errors);
    if (!parsed.success || Object.keys(errors).length > 0) return;

    const payload = {
      code: parsed.data.code,
      name: parsed.data.name,
      base_unit: parsed.data.base_unit,
      default_price_minor: parseMajorToMinor(parsed.data.price_major),
      category_id: parsed.data.category_id ?? null,
    };

    try {
      if (isEdit && product) {
        await updateMutation.mutateAsync({ productId: product.id, data: payload });
        notify({ title: "Product updated" });
        onClose();
        return;
      }
      const created = await createMutation.mutateAsync(payload);
      if (openingQty > 0) {
        try {
          await openingMutation.mutateAsync({ product_id: created.id, quantity: openingQty, reason: "Opening stock" });
        } catch (err) {
          notify({
            title: "Product created, opening stock not saved",
            description: err instanceof Error ? `${err.message} Set it from Inventory.` : "Set it from Inventory.",
            tone: "error",
          });
          onClose();
          return;
        }
      }
      notify({ title: "Product created", description: openingQty > 0 ? `Opening stock: ${openingQty} ${payload.base_unit}` : undefined });
      onClose();
    } catch (err) {
      const message = err instanceof Error && err.message ? err.message : "Couldn’t save the product.";
      if (err instanceof ApiError && err.status === 409) {
        setFieldErrors({ code: message });
      } else {
        setServerError(message);
      }
    }
  }

  const fieldError = (key: string, id: string) =>
    fieldErrors[key] ? (
      <span className="err" id={id}>
        <Icon name="alert" size="sm" />
        {fieldErrors[key]}
      </span>
    ) : null;

  return (
    <Sheet
      open={open}
      title={isEdit ? "Edit product" : "Add product"}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </button>
          <button type="submit" form="product-form" className="btn btn-primary" disabled={isPending} aria-busy={isPending}>
            {isPending && <span className="spinner" />}
            {isEdit ? "Save changes" : "Create product"}
          </button>
        </>
      }
    >
      <form id="product-form" onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {serverError && (
          <div className="alert a-danger" role="alert">
            <Icon name="alert" />
            <div>{serverError}</div>
          </div>
        )}
        <div className="field">
          <label className="label" htmlFor="ap-name">
            Product name
          </label>
          <input className={`input${fieldErrors.name ? " is-error" : ""}`} id="ap-name" value={name} onChange={(e) => setName(e.target.value)} aria-invalid={!!fieldErrors.name} aria-describedby="ap-name-e" />
          {fieldError("name", "ap-name-e")}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(160px, 100%), 1fr))", gap: 12 }}>
          <div className="field">
            <label className="label" htmlFor="ap-code">
              Product code
            </label>
            <input className={`input mono${fieldErrors.code ? " is-error" : ""}`} id="ap-code" value={code} onChange={(e) => setCode(e.target.value)} aria-invalid={!!fieldErrors.code} aria-describedby="ap-code-e" />
            {fieldError("code", "ap-code-e")}
          </div>
          <div className="field">
            <label className="label" htmlFor="ap-cat">
              Category <span className="opt">· optional</span>
            </label>
            <select className={`input${fieldErrors.category_id ? " is-error" : ""}`} id="ap-cat" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} aria-describedby="ap-cat-e">
              <option value="">No category</option>
              {(categories?.items ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {fieldError("category_id", "ap-cat-e")}
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(160px, 100%), 1fr))", gap: 12 }}>
          <div className="field">
            <label className="label" htmlFor="ap-price">
              Selling price
            </label>
            <div className={`ig${fieldErrors.price_major ? " is-error" : ""}`}>
              <span className="pre">PKR</span>
              <input id="ap-price" className="num" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} aria-invalid={!!fieldErrors.price_major} aria-describedby="ap-price-e" />
            </div>
            {fieldError("price_major", "ap-price-e")}
          </div>
          <div className="field">
            <label className="label" htmlFor="ap-unit">
              Unit
            </label>
            <input className={`input${fieldErrors.base_unit ? " is-error" : ""}`} id="ap-unit" value={baseUnit} onChange={(e) => setBaseUnit(e.target.value)} aria-describedby="ap-unit-e" placeholder="piece, kg, bag" />
            {fieldError("base_unit", "ap-unit-e")}
          </div>
        </div>
        {!isEdit && (
          <div className="field">
            <label className="label" htmlFor="ap-stock">
              Opening stock <span className="opt">· optional</span>
            </label>
            <div className={`ig${fieldErrors.opening ? " is-error" : ""}`}>
              <input id="ap-stock" className="num" inputMode="numeric" value={openingStock} onChange={(e) => setOpeningStock(e.target.value.replace(/[^0-9]/g, ""))} aria-describedby="ap-stock-h" />
              <span className="post">{baseUnit || "units"}</span>
            </div>
            {fieldErrors.opening ? (
              <span className="err" id="ap-stock-h">
                <Icon name="alert" size="sm" />
                {fieldErrors.opening}
              </span>
            ) : (
              <span className="hint" id="ap-stock-h">
                Recorded as the first entry in this product’s stock timeline.
              </span>
            )}
          </div>
        )}
        <div className="alert a-neutral">
          <Icon name="info" />
          <span>Your form stays filled until BizPilot confirms the product was saved.</span>
        </div>
      </form>
    </Sheet>
  );
}
