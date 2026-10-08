"use client";

import React, { useEffect, useState } from "react";
import { useInviteMember } from "@/hooks/use-team";
import { InviteMemberSchema } from "@/lib/schemas/organizations";
import { Icon } from "@/components/ui/icon";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

interface TeamInviteModalProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string;
  orgName?: string;
}

const ROLES = [
  { id: "manager" as const, name: "Manager", desc: "Runs day-to-day operations — orders, stock, payments, expenses and corrections. Can’t void records or manage the team." },
  { id: "staff" as const, name: "Staff", desc: "Creates orders, adds customers and records payments. No expenses, corrections or financial totals." },
];

/** Design "27 · Invite member". Owner-only (backend org:members:invite). */
export function TeamInviteModal({ isOpen, onClose, orgId, orgName }: TeamInviteModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"manager" | "staff">("staff");
  const [error, setError] = useState<string | null>(null);
  const invite = useInviteMember(orgId);
  const { notify } = useToast();

  useEffect(() => {
    if (!isOpen) return;
    setEmail("");
    setRole("staff");
    setError(null);
  }, [isOpen]);

  const valid = InviteMemberSchema.safeParse({ email, role }).success;

  async function send() {
    setError(null);
    const parsed = InviteMemberSchema.safeParse({ email, role });
    if (!parsed.success) return setError(parsed.error.issues[0]?.message ?? "Check the email address.");
    try {
      await invite.mutateAsync(parsed.data);
      notify({ title: `Invitation created for ${parsed.data.email}`, description: "They’ll see it after signing in to BizPilot." });
      onClose();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t send the invitation.");
    }
  }

  return (
    <Modal
      open={isOpen}
      title="Invite member"
      description={`They’ll see the invitation to join ${orgName ?? "this workspace"} when they sign in to BizPilot.`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={invite.isPending}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void send()} disabled={!valid || invite.isPending} aria-busy={invite.isPending}>
            {invite.isPending && <span className="spinner" />}
            Send invite
          </button>
        </>
      }
    >
      <div className="field">
        <label className="label" htmlFor="inv-email">
          Email
        </label>
        <input id="inv-email" className="input" type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@business.pk" />
        <span className="hint">They can accept after signing in to BizPilot with this email — or creating an account with it.</span>
      </div>
      <fieldset style={{ border: 0, margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        <legend className="label" style={{ marginBottom: 6 }}>
          Role
        </legend>
        {ROLES.map((r) => (
          <label
            key={r.id}
            style={{ display: "flex", gap: 12, padding: "12px 14px", border: `1px solid ${role === r.id ? "var(--brand)" : "var(--border)"}`, borderRadius: 8, background: role === r.id ? "var(--brand-tint)" : "var(--surface)", cursor: "pointer" }}
          >
            <input type="radio" name="inv-role" value={r.id} checked={role === r.id} onChange={() => setRole(r.id)} style={{ marginTop: 3, accentColor: "var(--brand)" }} />
            <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span className="t-h4">{r.name}</span>
              <span className="t-body-sm secondary">{r.desc}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <p className="t-caption">Owners can’t be invited, and ownership transfer isn’t available in this version.</p>
      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <span>{error}</span>
        </div>
      )}
    </Modal>
  );
}
