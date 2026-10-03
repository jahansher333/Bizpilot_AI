import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useOrgRole } from "@/hooks/use-org-role";

const authState = { organizations: [] as Array<{ id: string; role: string }> };
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => authState,
}));

describe("useOrgRole (FIX-008)", () => {
  beforeEach(() => {
    authState.organizations = [
      { id: "org-owner", role: "owner" },
      { id: "org-manager", role: "Manager" },
      { id: "org-staff", role: "staff" },
    ];
  });

  it("returns the membership role for the requested workspace", () => {
    expect(renderHook(() => useOrgRole("org-owner")).result.current).toBe("owner");
    expect(renderHook(() => useOrgRole("org-manager")).result.current).toBe("manager");
    expect(renderHook(() => useOrgRole("org-staff")).result.current).toBe("staff");
  });

  it("falls back to staff for unknown workspaces or while memberships load", () => {
    expect(renderHook(() => useOrgRole("org-other")).result.current).toBe("staff");
    authState.organizations = [];
    expect(renderHook(() => useOrgRole("org-owner")).result.current).toBe("staff");
  });
});
