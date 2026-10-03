"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ResetPasswordSchema } from "@/lib/schemas/auth";
import { ApiError, resetPasswordSubmit } from "@/lib/api/auth";
import { Icon } from "@/components/ui/icon";
import { AuthCardShell } from "@/components/auth/auth-card-shell";
import { FieldError, PasswordChecklist, PASSWORD_MIN_LENGTH } from "@/components/auth/password-checks";

type Phase = "form" | "done" | "expired";

/** Design canvas "05 · Reset password": new password, updated, expired link. */
export function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const linkToken = searchParams?.get("token") || "";

  const [token, setToken] = useState(linkToken);
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("form");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const mismatch = confirm.length > 0 && confirm !== newPassword;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const parsed = ResetPasswordSchema.safeParse({ token: token.trim(), new_password: newPassword });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message || "Invalid input");
      return;
    }
    if (confirm !== newPassword) {
      setError("Passwords don’t match yet");
      return;
    }
    setIsSubmitting(true);
    try {
      await resetPasswordSubmit(parsed.data);
      setPhase("done");
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setPhase("expired");
      } else {
        setError(err instanceof Error && err.message ? err.message : "Unable to update your password. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (phase === "done") {
    return (
      <AuthCardShell>
        <span className="dlg-icon ok pop-in">
          <Icon name="check" size="lg" className="check-anim" style={{ strokeWidth: 2.2 }} />
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }} role="status">
          <h1 className="t-h2">Password updated</h1>
          <p className="t-body-sm secondary">You’ve been signed out of other devices. Use your new password to sign in.</p>
        </div>
        <Link className="btn btn-primary btn-block btn-lg" href="/login">
          Continue to sign in
        </Link>
      </AuthCardShell>
    );
  }

  if (phase === "expired") {
    return (
      <AuthCardShell>
        <span className="dlg-icon warn">
          <Icon name="alert" size="lg" />
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }} role="alert">
          <h1 className="t-h2">This link has expired</h1>
          <p className="t-body-sm secondary">Reset links expire after a short time and work only once. Request a new one to continue.</p>
        </div>
        <Link className="btn btn-primary btn-block btn-lg" href="/forgot-password">
          Request a new link
        </Link>
      </AuthCardShell>
    );
  }

  return (
    <AuthCardShell>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <h1 className="t-h2">Choose a new password</h1>
        <p className="t-body-sm secondary">Use at least {PASSWORD_MIN_LENGTH} characters you don’t use anywhere else.</p>
      </div>
      {error && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <div>{error}</div>
        </div>
      )}
      <form onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {!linkToken && (
          <div className="field">
            <label className="label" htmlFor="rp-token">
              Reset token
            </label>
            <input className="input mono" id="rp-token" value={token} onChange={(e) => setToken(e.target.value)} disabled={isSubmitting} required />
            <span className="hint">Paste the token from your recovery email, or open the link in that email.</span>
          </div>
        )}
        <div className="field">
          <label className="label" htmlFor="rp-1">
            New password
          </label>
          <input
            className="input"
            id="rp-1"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            aria-describedby="rp-req"
            disabled={isSubmitting}
            required
          />
          <PasswordChecklist id="rp-req" password={newPassword} />
        </div>
        <div className="field">
          <label className="label" htmlFor="rp-2">
            Confirm new password
          </label>
          <input
            className={`input${mismatch ? " is-error" : ""}`}
            id="rp-2"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            aria-invalid={mismatch}
            aria-describedby={mismatch ? "rp-2e" : undefined}
            disabled={isSubmitting}
            required
          />
          {mismatch && <FieldError id="rp-2e">Passwords don’t match yet</FieldError>}
        </div>
        <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={isSubmitting} aria-busy={isSubmitting}>
          {isSubmitting ? (
            <>
              <span className="spinner" />
              Updating…
            </>
          ) : (
            "Update password"
          )}
        </button>
      </form>
    </AuthCardShell>
  );
}
