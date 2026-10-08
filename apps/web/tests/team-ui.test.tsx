import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TeamView } from "@/components/team/team-view";
import { SettingsView } from "@/components/settings/settings-view";
import { PendingInvitations } from "@/components/team/pending-invitations";
import * as orgApi from "@/lib/api/organizations";
import * as authApi from "@/lib/api/auth";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/onboarding",
}));

const authState = {
  user: { id: "user-owner", email: "owner@shop.pk", display_name: "Owner Khan", status: "active" },
  token: "access-1",
  organizations: [{ id: "org-1", display_name: "Khan Traders", currency_code: "PKR", timezone: "Asia/Karachi", status: "active", created_at: "", role: "owner" }],
  isAuthenticated: true,
  logout: vi.fn().mockResolvedValue(undefined),
  refetchOrganizations: vi.fn().mockResolvedValue([]),
  selectOrg: vi.fn(),
};
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => authState,
  useOptionalAuth: () => authState,
}));

vi.mock("@/lib/api/organizations", () => ({
  listMembers: vi.fn(),
  listInvitations: vi.fn(),
  revokeInvitation: vi.fn(),
  inviteMember: vi.fn(),
  updateMemberRole: vi.fn(),
  revokeMember: vi.fn(),
  listMyInvitations: vi.fn(),
  acceptInvitation: vi.fn(),
}));
vi.mock("@/lib/api/auth", () => ({ logoutAllSessions: vi.fn() }));

const member = (overrides: Record<string, unknown>) => ({
  organization_id: "org-1",
  created_at: "2026-10-01T00:00:00Z",
  ...overrides,
});
const members = [
  member({ id: "m-owner", user_id: "user-owner", role: "owner", status: "active", email: "owner@shop.pk", display_name: "Owner Khan" }),
  member({ id: "m-staff", user_id: "user-staff", role: "staff", status: "active", email: "staff@shop.pk", display_name: "Ali Staff", created_at: "2026-10-02T00:00:00Z" }),
] as any[];
// Invitations are addressed to emails (SEC-P1 F5): no account, name or user ID.
const invitations = [
  { id: "inv-1", organization_id: "org-1", email: "sana@shop.pk", role: "manager", status: "pending", created_at: "2026-10-03T00:00:00Z", updated_at: "2026-10-03T00:00:00Z" },
] as any[];

function setRole(role: string) {
  authState.organizations = [{ ...authState.organizations[0], role }];
}

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("Team (R9)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setRole("owner");
    vi.mocked(orgApi.listMembers).mockResolvedValue(members);
    vi.mocked(orgApi.listInvitations).mockResolvedValue(invitations);
  });

  it("lists members with role, status, join date and marks you", async () => {
    renderWithClient(<TeamView orgId="org-1" />);
    await screen.findByLabelText("Role for Ali Staff");
    const table = screen.getAllByRole("table")[0];
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByText("(you)")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Owner")).toBeInTheDocument();
    expect(within(rows[1]).queryByRole("button")).not.toBeInTheDocument();
    expect(within(rows[2]).getByLabelText("Role for Ali Staff")).toHaveValue("staff");
    expect(within(rows[2]).getByText("Active")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Invited")).toBeInTheDocument();
    expect(within(rows[3]).getByRole("button", { name: "Revoke invitation for sana@shop.pk" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /resend/i })).not.toBeInTheDocument();
  });

  it("shows the role table built from backend permissions", () => {
    renderWithClient(<TeamView orgId="org-1" />);
    const card = screen.getByRole("region", { name: "What each role can do" });
    const voidRow = within(card).getByText("Void orders, payments and expenses").closest("tr")!;
    expect(within(voidRow).getAllByRole("cell").map((c) => c.textContent)).toEqual(["Void orders, payments and expenses", "Yes", "—", "—"]);
    const teamRow = within(card).getByText("Invite members and change roles").closest("tr")!;
    expect(within(teamRow).getAllByRole("cell").map((c) => c.textContent)).toEqual(["Invite members and change roles", "Yes", "—", "—"]);
  });

  it("invites a member with a chosen role", async () => {
    vi.mocked(orgApi.inviteMember).mockResolvedValue(invitations[0]);
    renderWithClient(<TeamView orgId="org-1" />);
    fireEvent.click(screen.getByRole("button", { name: /invite member/i }));
    const dialog = screen.getByRole("dialog", { name: "Invite member" });
    const send = within(dialog).getByRole("button", { name: "Send invite" });
    expect(send).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Email"), { target: { value: "sana@shop.pk" } });
    fireEvent.click(within(dialog).getByRole("radio", { name: /Manager/ }));
    fireEvent.click(send);
    await waitFor(() => expect(orgApi.inviteMember).toHaveBeenCalledWith("org-1", { email: "sana@shop.pk", role: "manager" }, undefined));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows the server error when an invitation fails", async () => {
    vi.mocked(orgApi.inviteMember).mockRejectedValue(new Error("Unable to invite this email address."));
    renderWithClient(<TeamView orgId="org-1" />);
    fireEvent.click(screen.getByRole("button", { name: /invite member/i }));
    const dialog = screen.getByRole("dialog", { name: "Invite member" });
    fireEvent.change(within(dialog).getByLabelText("Email"), { target: { value: "nobody@shop.pk" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Send invite" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Unable to invite this email address.");
  });

  it("changes a member's role and surfaces last-owner protection errors", async () => {
    vi.mocked(orgApi.updateMemberRole).mockResolvedValueOnce({ ...members[1], role: "manager" });
    renderWithClient(<TeamView orgId="org-1" />);
    fireEvent.change(await screen.findByLabelText("Role for Ali Staff"), { target: { value: "manager" } });
    await waitFor(() => expect(orgApi.updateMemberRole).toHaveBeenCalledWith("org-1", "m-staff", "manager", undefined));

    vi.mocked(orgApi.updateMemberRole).mockRejectedValueOnce(new Error("Cannot demote the last owner"));
    fireEvent.change(screen.getByLabelText("Role for Ali Staff"), { target: { value: "owner" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot demote the last owner");
  });

  it("shows a pending invitation by email only and revokes it through the invitation endpoint", async () => {
    vi.mocked(orgApi.revokeInvitation).mockResolvedValue({ ...invitations[0], status: "revoked" });
    renderWithClient(<TeamView orgId="org-1" />);
    const revoke = await screen.findByRole("button", { name: "Revoke invitation for sana@shop.pk" });
    const row = revoke.closest("tr")!;
    expect(within(row).getAllByText("sana@shop.pk")).toHaveLength(2);
    expect(within(row).queryByRole("combobox")).not.toBeInTheDocument();
    fireEvent.click(revoke);
    const dialog = screen.getByRole("alertdialog", { name: "Revoke the invitation for sana@shop.pk?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke invitation" }));
    await waitFor(() => expect(orgApi.revokeInvitation).toHaveBeenCalledWith("org-1", "inv-1", undefined));
    expect(orgApi.revokeMember).not.toHaveBeenCalled();
  });

  it("removes a member after confirming in a dialog", async () => {
    vi.mocked(orgApi.revokeMember).mockResolvedValue({ ...members[1], status: "revoked" });
    renderWithClient(<TeamView orgId="org-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove Ali Staff" }));
    const dialog = screen.getByRole("alertdialog", { name: "Remove Ali Staff?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove access" }));
    await waitFor(() => expect(orgApi.revokeMember).toHaveBeenCalledWith("org-1", "m-staff", undefined));
  });

  it("uses the role in this workspace: Managers see a restricted page and no members are loaded", () => {
    setRole("manager");
    renderWithClient(<TeamView orgId="org-1" />);
    expect(screen.getByRole("heading", { name: "Only Owners can manage the team" })).toBeInTheDocument();
    expect(orgApi.listMembers).not.toHaveBeenCalled();
    expect(orgApi.listInvitations).not.toHaveBeenCalled();
  });
});

describe("Settings (R9)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setRole("owner");
  });

  it("shows the business profile read-only to Owners and Managers", () => {
    renderWithClient(<SettingsView orgId="org-1" />);
    expect(screen.getByLabelText("Business name")).toHaveValue("Khan Traders");
    expect(screen.getByLabelText("Business name")).toHaveAttribute("readonly");
    expect(screen.getByText("PKR · Pakistani Rupee")).toBeInTheDocument();
    expect(screen.getByText("Asia/Karachi")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /team/i })).toHaveAttribute("href", "/workspace/org-1/team");
    expect(screen.queryByText(/danger zone/i)).not.toBeInTheDocument();
  });

  it("hides the business profile from Staff but keeps security and account", () => {
    setRole("staff");
    renderWithClient(<SettingsView orgId="org-1" />);
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    expect(within(nav).queryByRole("button", { name: "Business profile" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: /team/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Security" })).toBeInTheDocument();
    fireEvent.click(within(nav).getByRole("button", { name: "Your account" }));
    expect(screen.getByLabelText("Email")).toHaveValue("owner@shop.pk");
    expect(screen.getByText("Staff")).toBeInTheDocument();
  });

  it("signs out of all devices after confirmation", async () => {
    vi.mocked(authApi.logoutAllSessions).mockResolvedValue({ message: "ok" } as any);
    renderWithClient(<SettingsView orgId="org-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Security" }));
    expect(screen.getByRole("link", { name: "Reset password" })).toHaveAttribute("href", "/forgot-password");
    fireEvent.click(screen.getByRole("button", { name: "Sign out of all devices" }));
    const dialog = screen.getByRole("alertdialog", { name: "Sign out of all devices?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Sign out everywhere" }));
    await waitFor(() => expect(authApi.logoutAllSessions).toHaveBeenCalledWith("access-1"));
    await waitFor(() => expect(authState.logout).toHaveBeenCalled());
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
        invitation_id: "inv-9",
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
