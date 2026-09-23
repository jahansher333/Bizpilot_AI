import {
  Category,
  CategoryListResponse,
  CategoryCreateInput,
  CategoryUpdateInput,
  Product,
  ProductListResponse,
} from "@/lib/schemas/catalog";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const getApiBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "";
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
};

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `Request failed with status ${res.status}`;
    let errorCode: string | undefined;

    try {
      const data = await res.json();
      if (data.error && data.error.message) {
        errorMsg = data.error.message;
        errorCode = data.error.code;
      } else if (data.detail) {
        errorMsg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // Fallback to status text
      errorMsg = res.statusText || errorMsg;
    }

    throw new ApiError(errorMsg, res.status, errorCode);
  }
  return (await res.json()) as T;
}

function getHeaders(token?: string): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// ==============================================================================
// Category API Functions
// ==============================================================================

export async function listCategories(
  organizationId: string,
  params?: { status?: string; limit?: number; offset?: number },
  token?: string
): Promise<CategoryListResponse> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== "all") {
    query.set("status", params.status);
  }
  if (params?.limit !== undefined) {
    query.set("limit", params.limit.toString());
  }
  if (params?.offset !== undefined) {
    query.set("offset", params.offset.toString());
  }

  const qs = query.toString() ? `?${query.toString()}` : "";
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/categories${qs}`;

  const res = await fetch(url, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<CategoryListResponse>(res);
}

export async function createCategory(
  organizationId: string,
  data: CategoryCreateInput,
  token?: string
): Promise<Category> {
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/categories`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<Category>(res);
}

export async function updateCategory(
  organizationId: string,
  categoryId: string,
  data: CategoryUpdateInput,
  token?: string
): Promise<Category> {
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/categories/${categoryId}`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: getHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<Category>(res);
}

export async function archiveCategory(
  organizationId: string,
  categoryId: string,
  token?: string
): Promise<Category> {
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/categories/${categoryId}/archive`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token),
  });
  return handleResponse<Category>(res);
}

// ==============================================================================
// Product API Functions
// ==============================================================================

export interface ProductCreateApiPayload {
  code: string;
  name: string;
  base_unit: string;
  default_price_minor: number;
  category_id?: string | null;
}

export interface ProductUpdateApiPayload {
  code?: string;
  name?: string;
  base_unit?: string;
  default_price_minor?: number;
  category_id?: string | null;
}

export async function listProducts(
  organizationId: string,
  params?: { status?: string; category_id?: string; limit?: number; offset?: number },
  token?: string
): Promise<ProductListResponse> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== "all") {
    query.set("status", params.status);
  }
  if (params?.category_id) {
    query.set("category_id", params.category_id);
  }
  if (params?.limit !== undefined) {
    query.set("limit", params.limit.toString());
  }
  if (params?.offset !== undefined) {
    query.set("offset", params.offset.toString());
  }

  const qs = query.toString() ? `?${query.toString()}` : "";
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/products${qs}`;

  const res = await fetch(url, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<ProductListResponse>(res);
}

export async function getProduct(
  organizationId: string,
  productId: string,
  token?: string
): Promise<Product> {
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/products/${productId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: getHeaders(token),
  });
  return handleResponse<Product>(res);
}

export async function createProduct(
  organizationId: string,
  data: ProductCreateApiPayload,
  token?: string
): Promise<Product> {
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/products`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<Product>(res);
}

export async function updateProduct(
  organizationId: string,
  productId: string,
  data: ProductUpdateApiPayload,
  token?: string
): Promise<Product> {
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/products/${productId}`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: getHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<Product>(res);
}

export async function archiveProduct(
  organizationId: string,
  productId: string,
  token?: string
): Promise<Product> {
  const url = `${getApiBaseUrl()}/api/organizations/${organizationId}/products/${productId}/archive`;
  const res = await fetch(url, {
    method: "POST",
    headers: getHeaders(token),
  });
  return handleResponse<Product>(res);
}
