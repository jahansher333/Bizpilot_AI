"use client";

import { useAuth } from "@/hooks/use-auth";

export type OrgRole = "owner" | "manager" | "staff";

/**
 * The signed-in user's role in the given workspace, from their verified memberships (FIX-008).
 * Falls back to the least-privileged role until memberships load. This only shapes the UI;
 * the backend enforces every permission independently.
 */
export function useOrgRole(orgId: string): OrgRole {
  const { organizations } = useAuth();
  const role = organizations.find((org) => org.id === orgId)?.role?.toLowerCase();
  return role === "owner" || role === "manager" ? role : "staff";
}
