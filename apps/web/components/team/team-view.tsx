"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useOptionalAuth } from "@/hooks/use-auth";
import { useOrgRole } from "@/hooks/use-org-role";
import { useRevokeInvitation, useRevokeMember, useTeamInvitations, useTeamMembers, useUpdateMemberRole } from "@/hooks/use-team";
import { Invitation, MEMBER_ROLES, MemberRole, OrganizationMember } from "@/lib/schemas/organizations";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";
import { Modal } from "@/components/ui/modal";
import { ErrorState, RestrictedState, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { TeamInviteModal } from "@/components/team/team-invite-modal";

interface TeamViewProps {
  orgId: string;
}

const ROLE_LABEL: Record<string, string> = { owner: "Owner", manager: "Manager", staff: "Staff" };
const ROLE_BADGE: Record<string, string> = { owner: "b-brand", manager: "b-info", staff: "b-neutral" };
const STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "Active", cls: "b-success" },
  invited: { label: "Invited", cls: "b-warning" },
  revoked: { label: "Removed", cls: "b-neutral" },
};

/**
 * Mirrors the backend role → permission table (organizations/permissions.py), so the page never
 * promises something the server refuses. "Limited" = partly allowed, explained in the label.
 */
const CAPABILITIES: [string, string, string, string][] = [
  ["Create orders, add customers, record payments", "Yes", "Yes", "Yes"],
  ["Edit customers, products and categories; adjust stock", "Yes", "Yes", "—"],
  ["Correct orders, payments and expenses", "Yes", "Yes", "—"],
  ["Void orders, payments and expenses", "Yes", "—", "—"],
  ["See and record expenses", "Yes", "Yes", "—"],
  ["Dashboard financials (expenses, net cash)", "Yes", "Yes", "—"],
  ["Ask BizPilot AI (read-only; Staff without expenses or balances)", "Yes", "Yes", "Limited"],
  ["Invite members and change roles", "Yes", "—", "—"],
];
const CAP_COLOR: Record<string, string> = { Yes: "var(--success)", "—": "var(--text-muted)", Limited: "var(--warning)" };

/**
 * Pending invitations are addressed to emails, not accounts (SEC-P1 F5), so they show as "Invited"
 * rows with the email only: no name, and no hint whether the email already has an account.
 */
function invitationRow(invitation: Invitation): OrganizationMember {
  return {
    id: invitation.id,
    organization_id: invitation.organization_id,
    user_id: "",
    role: invitation.role,
    status: "invited",
    created_at: invitation.updated_at,
    email: invitation.email,
    display_name: "",
  };
}

function joined(iso: string) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
}

/** Design canvas "27 · Team". Owner-only (backend org:members:*). */
export function TeamView({ orgId }: TeamViewProps) {
  const auth = useOptionalAuth();
  const role = useOrgRole(orgId);
  const isOwner = role === "owner";
  const orgName = auth?.organizations.find((o) => o.id === orgId)?.display_name;
  const currentUserId = auth?.user?.id;

  const membersQuery = useTeamMembers(orgId, isOwner);
  const invitationsQuery = useTeamInvitations(orgId, isOwner);
  const isLoading = membersQuery.isLoading || invitationsQuery.isLoading;
  const error = membersQuery.error || invitationsQuery.error;
  const refetch = () => Promise.all([membersQuery.refetch(), invitationsQuery.refetch()]);
  const members =
    membersQuery.data && invitationsQuery.data
      ? [...membersQuery.data.filter((m) => m.status !== "invited"), ...invitationsQuery.data.map(invitationRow)]
      : undefined;
  const roleMutation = useUpdateMemberRole(orgId);
  const revokeMemberMutation = useRevokeMember(orgId);
  const revokeInvitationMutation = useRevokeInvitation(orgId);
  const revokeMutation = { isPending: revokeMemberMutation.isPending || revokeInvitationMutation.isPending };
  const { notify } = useToast();

  const [inviteOpen, setInviteOpen] = useState(false);
  const [removing, setRemoving] = useState<OrganizationMember | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!isOwner) {
    return (
      <div className="main page-in">
        <RestrictedState
          title="Only Owners can manage the team"
          description="Ask an Owner of this workspace to invite people or change roles."
          action={
            <Link className="btn btn-primary" href={`/workspace/${orgId}`}>
              Back to dashboard
            </Link>
          }
        />
      </div>
    );
  }

  async function changeRole(member: OrganizationMember, next: MemberRole) {
    if (next === member.role) return;
    setActionError(null);
    try {
      await roleMutation.mutateAsync({ memberId: member.id, role: next });
      notify({ title: `${member.display_name || member.email} is now ${ROLE_LABEL[next]}` });
    } catch (err) {
      setActionError(err instanceof Error && err.message ? err.message : "Couldn’t change the role.");
    }
  }

  async function confirmRemove() {
    if (!removing) return;
    setActionError(null);
    try {
      if (removing.status === "invited") await revokeInvitationMutation.mutateAsync(removing.id);
      else await revokeMemberMutation.mutateAsync(removing.id);
      notify({ title: removing.status === "invited" ? "Invitation revoked" : `${removing.display_name || removing.email} removed` });
      setRemoving(null);
    } catch (err) {
      setRemoving(null);
      setActionError(err instanceof Error && err.message ? err.message : "Couldn’t remove access.");
    }
  }

  const sorted = [...(members ?? [])].sort((a, b) => {
    const order = { active: 0, invited: 1, revoked: 2 } as Record<string, number>;
    return (order[a.status] ?? 3) - (order[b.status] ?? 3) || a.created_at.localeCompare(b.created_at);
  });
  const busy = roleMutation.isPending || revokeMutation.isPending;

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Team</h1>
          <p className="t-body secondary">People who can use {orgName ? `the ${orgName}` : "this"} workspace, and what each can do.</p>
        </div>
        <div className="ph-a">
          <button type="button" className="btn btn-primary" onClick={() => setInviteOpen(true)}>
            <Icon name="plus" />
            Invite member
          </button>
        </div>
      </div>

      {error && <ErrorState title="Couldn’t load the team" onRetry={() => void refetch()} />}
      {actionError && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <span>{actionError}</span>
        </div>
      )}

      {isLoading && (
        <div className="tbl-wrap" aria-busy="true" aria-label="Loading team" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <Skeleton width={28} height={28} radius={14} />
              <Skeleton width={200} height={12} />
            </div>
          ))}
        </div>
      )}

      {members && (
        <div className="tbl-wrap fade-in">
          <table className="tbl">
            <thead>
              <tr>
                <th>Member</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th className="r">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((m) => {
                const you = m.user_id === currentUserId;
                const name = m.display_name || m.email;
                const status = STATUS[m.status] ?? { label: m.status, cls: "b-neutral" };
                return (
                  <tr key={m.id} className={m.status === "revoked" ? "is-void" : ""}>
                    <td>
                      <div className="cell-main">
                        <span className={`av${m.status === "active" ? "" : " n"}`}>{initials(name)}</span>
                        <span className="t" style={m.status === "active" ? undefined : { color: "var(--text-muted)" }}>
                          {name}
                          {you && (
                            <span className="muted" style={{ fontWeight: 400 }}>
                              {" "}
                              (you)
                            </span>
                          )}
                        </span>
                      </div>
                    </td>
                    <td className="secondary">{m.email}</td>
                    <td>
                      {m.status === "active" && !you ? (
                        <select className="input" aria-label={`Role for ${name}`} value={m.role} disabled={busy} onChange={(e) => void changeRole(m, e.target.value as MemberRole)} style={{ height: 32, width: 130 }}>
                          {MEMBER_ROLES.map((r) => (
                            <option key={r} value={r}>
                              {ROLE_LABEL[r]}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className={`badge square ${ROLE_BADGE[m.role] ?? "b-neutral"}`}>{ROLE_LABEL[m.role] ?? m.role}</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${status.cls}`}>{status.label}</span>
                    </td>
                    <td className="muted">{m.status === "invited" ? `Invited ${joined(m.created_at)}` : joined(m.created_at)}</td>
                    <td className="r">
                      {!you && m.status !== "revoked" && (
                        <span className="row-actions">
                          <button type="button" className="btn btn-ghost btn-sm" style={m.status === "active" ? { color: "var(--danger)" } : undefined} disabled={busy} onClick={() => setRemoving(m)} aria-label={`${m.status === "invited" ? "Revoke invitation for" : "Remove"} ${name}`}>
                            {m.status === "invited" ? "Revoke" : "Remove"}
                          </button>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <section className="card" aria-labelledby="perm-h" style={{ overflow: "hidden" }}>
        <div className="card-h">
          <h2 className="t-h3" id="perm-h">
            What each role can do
          </h2>
          <span className="t-caption">BizPilot checks every action on the server; hidden buttons are just a convenience.</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Capability</th>
                <th className="c">Owner</th>
                <th className="c">Manager</th>
                <th className="c">Staff</th>
              </tr>
            </thead>
            <tbody>
              {CAPABILITIES.map(([label, ...cells]) => (
                <tr key={label}>
                  <td>{label}</td>
                  {cells.map((v, i) => (
                    <td key={i} className="c">
                      <span style={{ color: CAP_COLOR[v], fontSize: 12.5 }}>{v === "—" ? <span aria-label="No">—</span> : v}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <TeamInviteModal isOpen={inviteOpen} onClose={() => setInviteOpen(false)} orgId={orgId} orgName={orgName} />
      <Modal
        open={!!removing}
        tone="danger"
        title={removing?.status === "invited" ? `Revoke the invitation for ${removing?.email}?` : `Remove ${removing?.display_name || removing?.email}?`}
        description={removing?.status === "invited" ? "They won’t be able to join with this invitation." : "They’ll lose access to this workspace straight away. Their past records stay."}
        onClose={() => setRemoving(null)}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setRemoving(null)} disabled={revokeMutation.isPending}>
              Cancel
            </button>
            <button type="button" className="btn btn-danger" onClick={() => void confirmRemove()} disabled={revokeMutation.isPending} aria-busy={revokeMutation.isPending}>
              {revokeMutation.isPending && <span className="spinner" />}
              {removing?.status === "invited" ? "Revoke invitation" : "Remove access"}
            </button>
          </>
        }
      />
    </div>
  );
}
