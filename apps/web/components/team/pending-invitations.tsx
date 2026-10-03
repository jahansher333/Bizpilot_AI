"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useAcceptInvitation, useMyInvitations } from "@/hooks/use-team";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";

/**
 * Lists invitations addressed to the signed-in user and lets them join (FIX-006).
 * Renders nothing when there are no pending invitations.
 */
export function PendingInvitations() {
  const router = useRouter();
  const { isAuthenticated, refetchOrganizations, selectOrg } = useAuth();
  const { data: invitations } = useMyInvitations(isAuthenticated);
  const acceptMutation = useAcceptInvitation();
  const [error, setError] = useState<string | null>(null);

  if (!invitations || invitations.length === 0) return null;

  const handleAccept = async (orgId: string) => {
    setError(null);
    try {
      await acceptMutation.mutateAsync(orgId);
      await refetchOrganizations();
      selectOrg(orgId);
      router.push(`/workspace/${orgId}`);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Unable to accept invitation.");
    }
  };

  return (
    <section aria-labelledby="pending-invitations-heading" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <h2 id="pending-invitations-heading" className="t-h3">
        Pending invitations
      </h2>
      <ul className="card stagger" style={{ overflow: "hidden", borderColor: "var(--brand-border)" }}>
        {invitations.map((invite, i) => (
          <li
            key={invite.membership_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              padding: "14px 18px",
              borderBottom: i < invitations.length - 1 ? "1px solid var(--border)" : 0,
              flexWrap: "wrap",
              background: "var(--brand-tint)",
            }}
          >
            <span className="ws-mark" style={{ width: 40, height: 40, fontSize: 14 }}>
              {initials(invite.organization_display_name)}
            </span>
            <div style={{ flex: 1, minWidth: 180, display: "flex", flexDirection: "column", gap: 2 }}>
              <span className="t-h4">{invite.organization_display_name}</span>
              <span className="t-caption" style={{ textTransform: "capitalize" }}>
                Invited as {invite.role}
              </span>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              disabled={acceptMutation.isPending}
              onClick={() => handleAccept(invite.organization_id)}
              aria-label={`Accept invitation to ${invite.organization_display_name}`}
            >
              <Icon name="check" />
              Accept
            </button>
          </li>
        ))}
      </ul>
      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <div>{error}</div>
        </div>
      )}
    </section>
  );
}
