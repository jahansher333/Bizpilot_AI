"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptInvitation,
  inviteMember,
  listInvitations,
  listMembers,
  listMyInvitations,
  revokeInvitation,
  revokeMember,
  updateMemberRole,
} from "@/lib/api/organizations";
import { InviteMemberInput, MemberRole } from "@/lib/schemas/organizations";

export const teamQueryKeys = {
  members: (orgId: string) => ["team", orgId, "members"] as const,
  invitations: (orgId: string) => ["team", orgId, "invitations"] as const,
  myInvitations: () => ["team", "my-invitations"] as const,
};

export function useTeamMembers(orgId: string, enabled = true, token?: string) {
  return useQuery({
    queryKey: teamQueryKeys.members(orgId),
    queryFn: () => listMembers(orgId, token),
    enabled: !!orgId && enabled,
  });
}

export function useInviteMember(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InviteMemberInput) => inviteMember(orgId, payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamQueryKeys.invitations(orgId) });
    },
  });
}

/** Pending invitations, addressed to emails (SEC-P1 F5). Owner-only on the backend. */
export function useTeamInvitations(orgId: string, enabled = true, token?: string) {
  return useQuery({
    queryKey: teamQueryKeys.invitations(orgId),
    queryFn: () => listInvitations(orgId, token),
    enabled: !!orgId && enabled,
  });
}

export function useRevokeInvitation(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => revokeInvitation(orgId, invitationId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamQueryKeys.invitations(orgId) });
    },
  });
}

export function useUpdateMemberRole(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: MemberRole }) =>
      updateMemberRole(orgId, memberId, role, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamQueryKeys.members(orgId) });
    },
  });
}

export function useRevokeMember(orgId: string, token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) => revokeMember(orgId, memberId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamQueryKeys.members(orgId) });
    },
  });
}

export function useMyInvitations(enabled = true, token?: string) {
  return useQuery({
    queryKey: teamQueryKeys.myInvitations(),
    queryFn: () => listMyInvitations(token),
    enabled,
  });
}

export function useAcceptInvitation(token?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orgId: string) => acceptInvitation(orgId, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: teamQueryKeys.myInvitations() });
    },
  });
}
