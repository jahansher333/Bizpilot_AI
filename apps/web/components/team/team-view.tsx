"use client";

import React, { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import {
  useInviteMember,
  useRevokeMember,
  useTeamMembers,
  useUpdateMemberRole,
} from "@/hooks/use-team";
import {
  InviteMemberSchema,
  MEMBER_ROLES,
  MemberRole,
  OrganizationMember,
} from "@/lib/schemas/organizations";

interface TeamViewProps {
  orgId: string;
}

const ROLE_LABELS: Record<MemberRole, string> = {
  owner: "Owner",
  manager: "Manager",
  staff: "Staff",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-tertiary-container/20 text-tertiary",
  invited: "bg-secondary-fixed text-on-secondary-fixed",
  revoked: "bg-surface-container-high text-outline",
};

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

export function TeamView({ orgId }: TeamViewProps) {
  const { user, activeRole } = useAuth();
  const isOwner = activeRole?.toLowerCase() === "owner";

  const { data: members, isLoading, error } = useTeamMembers(orgId, isOwner);
  const inviteMutation = useInviteMember(orgId);
  const roleMutation = useUpdateMemberRole(orgId);
  const revokeMutation = useRevokeMember(orgId);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"manager" | "staff">("staff");
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!isOwner) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div
          role="alert"
          className="rounded-xl border border-surface-container-high/60 bg-surface-container-lowest p-6 text-sm text-on-surface-variant"
        >
          Only workspace owners can manage team members.
        </div>
      </div>
    );
  }

  const handleInvite = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);
    setNotice(null);
    const parsed = InviteMemberSchema.safeParse({ email, role });
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message || "Invalid input");
      return;
    }
    try {
      await inviteMutation.mutateAsync(parsed.data);
      setNotice(
        `Invitation created for ${parsed.data.email}. They can accept it after signing in to BizPilot.`
      );
      setEmail("");
    } catch (err) {
      setFormError(errorMessage(err, "Unable to send invitation."));
    }
  };

  const handleRoleChange = async (member: OrganizationMember, nextRole: MemberRole) => {
    if (nextRole === member.role) return;
    setActionError(null);
    try {
      await roleMutation.mutateAsync({ memberId: member.id, role: nextRole });
    } catch (err) {
      setActionError(errorMessage(err, "Unable to change role."));
    }
  };

  const handleRevoke = async (member: OrganizationMember) => {
    const label = member.display_name || member.email;
    if (!window.confirm(`Remove ${label}'s access to this workspace?`)) return;
    setActionError(null);
    try {
      await revokeMutation.mutateAsync(member.id);
    } catch (err) {
      setActionError(errorMessage(err, "Unable to revoke access."));
    }
  };

  return (
    <div className="space-y-6 p-6 max-w-[1200px] mx-auto">
      <div>
        <h1 className="font-display-lg text-2xl lg:text-3xl font-semibold tracking-tight text-on-surface">
          Team Members
        </h1>
        <p className="font-body-md text-sm text-on-surface-variant max-w-3xl mt-1">
          Invite people who already have a BizPilot account, change their role, or remove their access.
        </p>
      </div>

      <section
        aria-labelledby="invite-heading"
        className="rounded-xl border border-surface-container-high/60 bg-surface-container-lowest p-5 shadow-xs"
      >
        <h2 id="invite-heading" className="font-body-md text-base font-semibold text-on-surface mb-3">
          Invite a team member
        </h2>
        <form onSubmit={handleInvite} className="flex flex-col gap-3 sm:flex-row sm:items-end" noValidate>
          <div className="flex-1">
            <label htmlFor="invite-email" className="block text-xs font-semibold uppercase text-on-surface-variant tracking-wider mb-1">
              Email
            </label>
            <input
              id="invite-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="staff@yourbusiness.pk"
              className="w-full rounded-lg border border-outline-variant/40 bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div>
            <label htmlFor="invite-role" className="block text-xs font-semibold uppercase text-on-surface-variant tracking-wider mb-1">
              Role
            </label>
            <select
              id="invite-role"
              value={role}
              onChange={(e) => setRole(e.target.value as "manager" | "staff")}
              className="rounded-lg border border-outline-variant/40 bg-surface px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="staff">Staff</option>
              <option value="manager">Manager</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={inviteMutation.isPending}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary shadow-sm hover:bg-primary-container disabled:opacity-60"
          >
            {inviteMutation.isPending ? "Inviting..." : "Send invitation"}
          </button>
        </form>
        {formError && (
          <p role="alert" className="mt-3 text-sm text-error">
            {formError}
          </p>
        )}
        {notice && (
          <p role="status" className="mt-3 text-sm text-tertiary">
            {notice}
          </p>
        )}
      </section>

      <section
        aria-labelledby="members-heading"
        className="rounded-xl border border-surface-container-high/60 bg-surface-container-lowest shadow-xs overflow-hidden"
      >
        <h2 id="members-heading" className="px-5 pt-5 pb-3 font-body-md text-base font-semibold text-on-surface">
          Members
        </h2>
        {actionError && (
          <p role="alert" className="px-5 pb-3 text-sm text-error">
            {actionError}
          </p>
        )}
        {isLoading && <p className="px-5 pb-5 text-sm text-on-surface-variant">Loading members...</p>}
        {error && (
          <p role="alert" className="px-5 pb-5 text-sm text-error">
            {errorMessage(error, "Unable to load team members.")}
          </p>
        )}
        {members && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-container-low text-left text-xs uppercase tracking-wider text-on-surface-variant">
                <tr>
                  <th scope="col" className="px-5 py-2 font-semibold">Member</th>
                  <th scope="col" className="px-5 py-2 font-semibold">Role</th>
                  <th scope="col" className="px-5 py-2 font-semibold">Status</th>
                  <th scope="col" className="px-5 py-2 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => {
                  const isSelf = member.user_id === user?.id;
                  const isRevoked = member.status === "revoked";
                  const busy = roleMutation.isPending || revokeMutation.isPending;
                  return (
                    <tr key={member.id} className="border-t border-surface-container-high/60">
                      <td className="px-5 py-3">
                        <div className="font-medium text-on-surface">
                          {member.display_name}
                          {isSelf && <span className="ml-2 text-xs text-outline">(you)</span>}
                        </div>
                        <div className="text-xs text-on-surface-variant">{member.email}</div>
                      </td>
                      <td className="px-5 py-3">
                        {isRevoked ? (
                          <span className="text-on-surface-variant">{ROLE_LABELS[member.role] ?? member.role}</span>
                        ) : (
                          <select
                            aria-label={`Role for ${member.email}`}
                            value={member.role}
                            disabled={busy}
                            onChange={(e) => handleRoleChange(member, e.target.value as MemberRole)}
                            className="rounded-lg border border-outline-variant/40 bg-surface px-2 py-1 text-sm text-on-surface"
                          >
                            {MEMBER_ROLES.map((r) => (
                              <option key={r} value={r}>
                                {ROLE_LABELS[r]}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs font-semibold capitalize ${
                            STATUS_STYLES[member.status] ?? STATUS_STYLES.revoked
                          }`}
                        >
                          {member.status}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right">
                        {!isRevoked && !isSelf && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => handleRevoke(member)}
                            className="rounded-lg px-2 py-1 text-sm font-medium text-error hover:bg-error-container/30 disabled:opacity-60"
                          >
                            {member.status === "invited" ? "Cancel invite" : "Revoke"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
