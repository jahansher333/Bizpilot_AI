"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useAcceptInvitation, useMyInvitations } from "@/hooks/use-team";

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
    <section
      aria-labelledby="pending-invitations-heading"
      className="w-full max-w-xl mb-6 rounded-xl border border-surface-container-high/60 bg-surface-container-lowest p-5 shadow-xs"
    >
      <h2 id="pending-invitations-heading" className="font-body-md text-base font-semibold text-on-surface mb-3">
        Pending invitations
      </h2>
      <ul className="space-y-2">
        {invitations.map((invite) => (
          <li
            key={invite.membership_id}
            className="flex items-center justify-between gap-3 rounded-lg bg-surface-container-low px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-on-surface">{invite.organization_display_name}</p>
              <p className="text-xs capitalize text-on-surface-variant">Role: {invite.role}</p>
            </div>
            <button
              type="button"
              disabled={acceptMutation.isPending}
              onClick={() => handleAccept(invite.organization_id)}
              className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-on-primary hover:bg-primary-container disabled:opacity-60"
            >
              Accept
            </button>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="mt-3 text-sm text-error">
          {error}
        </p>
      )}
    </section>
  );
}
