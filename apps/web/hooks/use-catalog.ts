"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listCategories,
  createCategory,
  updateCategory,
  archiveCategory,
  listProducts,
  getProduct,
  createProduct,
  updateProduct,
  archiveProduct,
  ProductCreateApiPayload,
  ProductUpdateApiPayload,
} from "@/lib/api/catalog";
import { CategoryCreateInput, CategoryUpdateInput } from "@/lib/schemas/catalog";

// ==============================================================================
// Query Key Factory (Strictly Tenant-Scoped)
// ==============================================================================

export const catalogQueryKeys = {
  all: (organizationId: string) => ["catalog", organizationId] as const,
  categories: (organizationId: string, filters?: Record<string, unknown>) =>
    ["catalog", organizationId, "categories", filters ?? {}] as const,
  products: (organizationId: string, filters?: Record<string, unknown>) =>
    ["catalog", organizationId, "products", filters ?? {}] as const,
  productDetail: (organizationId: string, productId: string) =>
    ["catalog", organizationId, "product", productId] as const,
};

// ==============================================================================
// Category Hooks
// ==============================================================================

export function useCategories(
  organizationId: string,
  params?: { status?: string; limit?: number; offset?: number },
  token?: string
) {
  return useQuery({
    queryKey: catalogQueryKeys.categories(organizationId, params),
    queryFn: () => listCategories(organizationId, params, token),
    enabled: Boolean(organizationId),
  });
}

export function useCreateCategory(organizationId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CategoryCreateInput) => createCategory(organizationId, data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "categories"],
      });
    },
  });
}

export function useUpdateCategory(organizationId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ categoryId, data }: { categoryId: string; data: CategoryUpdateInput }) =>
      updateCategory(organizationId, categoryId, data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "categories"],
      });
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "products"],
      });
    },
  });
}

export function useArchiveCategory(organizationId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (categoryId: string) => archiveCategory(organizationId, categoryId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "categories"],
      });
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "products"],
      });
    },
  });
}

// ==============================================================================
// Product Hooks
// ==============================================================================

export function useProducts(
  organizationId: string,
  params?: { status?: string; category_id?: string; limit?: number; offset?: number },
  token?: string
) {
  return useQuery({
    queryKey: catalogQueryKeys.products(organizationId, params),
    queryFn: () => listProducts(organizationId, params, token),
    enabled: Boolean(organizationId),
  });
}

export function useProduct(organizationId: string, productId: string, token?: string) {
  return useQuery({
    queryKey: catalogQueryKeys.productDetail(organizationId, productId),
    queryFn: () => getProduct(organizationId, productId, token),
    enabled: Boolean(organizationId && productId),
  });
}

export function useCreateProduct(organizationId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProductCreateApiPayload) => createProduct(organizationId, data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "products"],
      });
    },
  });
}

export function useUpdateProduct(organizationId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ productId, data }: { productId: string; data: ProductUpdateApiPayload }) =>
      updateProduct(organizationId, productId, data, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "products"],
      });
    },
  });
}

export function useArchiveProduct(organizationId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (productId: string) => archiveProduct(organizationId, productId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["catalog", organizationId, "products"],
      });
    },
  });
}
