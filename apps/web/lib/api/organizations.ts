import {
  CreateOrganizationInput,
  InviteMemberInput,
  Organization,
  OrganizationMember,
} from "@/lib/schemas/organizations";
import { authorizedFetch, getApiBaseUrl } from "@/lib/api/http";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const response = await authorizedFetch(
    `${getApiBaseUrl()}${endpoint}`,
    { ...options, headers },
    token
  );

  if (!response.ok) {
    let errorMessage = "An error occurred";
    try {
      const errorData = await response.json();
      errorMessage =
        errorData.error?.message || errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

export async function listOrganizations(token: string): Promise<Organization[]> {
  return request<Organization[]>("/api/organizations", { method: "GET" }, token);
}

export async function createOrganization(
  payload: CreateOrganizationInput,
  token: string
): Promise<Organization> {
  return request<Organization>(
    "/api/organizations",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

export async function getOrganization(
  orgId: string,
  token: string
): Promise<Organization> {
  return request<Organization>(
    `/api/organizations/${orgId}`,
    { method: "GET" },
    token
  );
}

export async function listMembers(
  orgId: string,
  token: string
): Promise<OrganizationMember[]> {
  return request<OrganizationMember[]>(
    `/api/organizations/${orgId}/members`,
    { method: "GET" },
    token
  );
}

export async function inviteMember(
  orgId: string,
  payload: InviteMemberInput,
  token: string
): Promise<OrganizationMember> {
  return request<OrganizationMember>(
    `/api/organizations/${orgId}/members`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}
