import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TeamView } from "@/components/team/team-view";
import { PendingInvitations } from "@/components/team/pending-invitations";
import * as orgApi from "@/lib/api/organizations";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/onboarding",
}));

const authState = {
  user: { id: "user-owner", email: "owner@shop.pk", display_name: "Owner", status: "active" },
  activeRole: "owner" as string | null,
  isAuthenticated: true,
  refetchOrganizations: vi.fn().mockResolvedValue([]),
  selectOrg: vi.fn(),
};
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => authState,
}));

vi.mock("@/lib/api/organizations", () => ({
  listMembers: vi.fn(),
  inviteMember: vi.fn(),
  updateMemberRole: vi.fn(),
  revokeMember: vi.fn(),
  listMyInvitations: vi.fn(),
  acceptInvitation: vi.fn(),
}));

const members = [
  {
    id: "m-owner",
    organization_id: "org-1",
    user_id: "user-owner",
    role: "owner" as const,
    status: "active",
    created_at: "2026-10-01T00:00:00Z",
    email: "owner@shop.pk",
    display_name: "Owner",
  },
  {
    id: "m-staff",
    organization_id: "org-1",
    user_id: "user-staff",
    role: "staff" as const,
    status: "active",
    created_at: "2026-10-02T00:00:00Z",
    email: "staff@shop.pk",
    display_name: "Ali Staff",
  },
];

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("Team management (FIX-006)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.activeRole = "owner";
    vi.mocked(orgApi.listMembers).mockResolvedValue(members);
  });

  it("lists members with roles and statuses for owners", async () => {
    renderWithClient(<TeamView orgId="org-1" />);

    expect(await screen.findByText("Ali Staff")).toBeInTheDocument();
    expect(screen.getByText("staff@shop.pk")).toBeInTheDocument();
    expect(screen.getByText("(you)")).toBeInTheDocument();
    expect(screen.getByLabelText("Role for staff@shop.pk")).toHaveValue("staff");
    expect(orgApi.listMembers).toHaveBeenCalledWith("org-1", undefined);
  });

  it("does not offer revoke on the owner's own row", async () => {
    renderWithClient(<TeamView orgId="org-1" />);
    await screen.findByText("Ali Staff");
    expect(screen.getAllByRole("button", { name: "Revoke" })).toHaveLength(1);
  });

  it("validates and sends an invitation", async () => {
    vi.mocked(orgApi.inviteMember).mockResolvedValue({ ...members[1], status: "invited" });
    renderWithClient(<TeamView orgId="org-1" />);
    await screen.findByText("Ali Staff");

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/valid email/i);
    expect(orgApi.inviteMember).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@shop.pk" } });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "manager" } });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));

    await waitFor(() =>
      expect(orgApi.inviteMember).toHaveBeenCalledWith(
        "org-1",
        { email: "new@shop.pk", role: "manager" },
        undefined
      )
    );
    expect(await screen.findByRole("status")).toHaveTextContent("new@shop.pk");
  });

  it("shows the server error when an invitation fails", async () => {
    vi.mocked(orgApi.inviteMember).mockRejectedValue(
      new Error("No active BizPilot account was found for this email.")
    );
    renderWithClient(<TeamView orgId="org-1" />);
    await screen.findByText("Ali Staff");

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ghost@shop.pk" } });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No active BizPilot account");
  });

  it("changes a member role", async () => {
    vi.mocked(orgApi.updateMemberRole).mockResolvedValue({ ...members[1], role: "manager" });
    renderWithClient(<TeamView orgId="org-1" />);
    await screen.findByText("Ali Staff");

    fireEvent.change(screen.getByLabelText("Role for staff@shop.pk"), { target: { value: "manager" } });

    await waitFor(() =>
      expect(orgApi.updateMemberRole).toHaveBeenCalledWith("org-1", "m-staff", "manager", undefined)
    );
  });

  it("surfaces last-owner protection errors", async () => {
    vi.mocked(orgApi.updateMemberRole).mockRejectedValue(
      new Error("Cannot demote the last owner of the organization")
    );
    renderWithClient(<TeamView orgId="org-1" />);
    await screen.findByText("Ali Staff");

    fireEvent.change(screen.getByLabelText("Role for owner@shop.pk"), { target: { value: "staff" } });

    expect(await screen.findByRole("alert")).toHaveTextContent("last owner");
  });

  it("revokes a member after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(orgApi.revokeMember).mockResolvedValue({ ...members[1], status: "revoked" });
    renderWithClient(<TeamView orgId="org-1" />);
    await screen.findByText("Ali Staff");

    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));

    await waitFor(() => expect(orgApi.revokeMember).toHaveBeenCalledWith("org-1", "m-staff", undefined));
  });

  it("blocks non-owners and does not load members", () => {
    authState.activeRole = "manager";
    renderWithClient(<TeamView orgId="org-1" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Only workspace owners");
    expect(orgApi.listMembers).not.toHaveBeenCalled();
  });
});

describe("Pending invitations (FIX-006)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing without invitations", async () => {
    vi.mocked(orgApi.listMyInvitations).mockResolvedValue([]);
    const { container } = renderWithClient(<PendingInvitations />);
    await waitFor(() => expect(orgApi.listMyInvitations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("accepts an invitation and opens the workspace", async () => {
    vi.mocked(orgApi.listMyInvitations).mockResolvedValue([
      {
        membership_id: "m-1",
        organization_id: "org-9",
        organization_display_name: "Karachi Traders",
        role: "staff",
        invited_at: "2026-10-03T00:00:00Z",
      },
    ]);
    vi.mocked(orgApi.acceptInvitation).mockResolvedValue({ ...members[1], organization_id: "org-9" });

    renderWithClient(<PendingInvitations />);
    expect(await screen.findByText("Karachi Traders")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /accept invitation to karachi traders/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/workspace/org-9"));
    expect(orgApi.acceptInvitation).toHaveBeenCalledWith("org-9", undefined);
    expect(authState.refetchOrganizations).toHaveBeenCalled();
    expect(authState.selectOrg).toHaveBeenCalledWith("org-9");
  });
});
