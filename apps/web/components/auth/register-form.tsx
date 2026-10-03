"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RegisterSchema } from "@/lib/schemas/auth";
import { useAuth } from "@/hooks/use-auth";
import { Icon } from "@/components/ui/icon";
import { RegisterBrandPanel } from "@/components/auth/auth-brand-panel";
import { FieldError, PasswordChecklist, PASSWORD_MIN_LENGTH } from "@/components/auth/password-checks";

/** Design canvas "03 · Register". Registration is non-enumerating, then we sign in and open setup. */
export function RegisterForm() {
  const router = useRouter();
  const { register, login } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const mismatch = confirm.length > 0 && confirm !== password;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);

    const parsed = RegisterSchema.safeParse({ email, display_name: displayName, password });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message || "Invalid input");
      return;
    }
    if (confirm !== password) {
      setError("Passwords don’t match yet");
      return;
    }

    setIsSubmitting(true);
    try {
      await register(parsed.data);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Unable to create your account. Please try again.");
      setIsSubmitting(false);
      return;
    }

    try {
      const { organizations } = await login({ email: parsed.data.email, password });
      router.push(organizations.length > 0 ? "/workspaces" : "/onboarding");
    } catch {
      // The backend never reveals whether an email was already registered.
      setNotice("Your request was received. If this email is new, your account is ready — sign in to continue.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexWrap: "wrap", background: "var(--surface)" }}>
      <RegisterBrandPanel />

      <main style={{ flex: "1 1 520px", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px", background: "var(--surface)" }}>
        <div className="page-in" style={{ width: "100%", maxWidth: 400, display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h1 className="t-h1">Create your account</h1>
            <p className="t-body secondary">You’ll set up your business in the next step.</p>
          </div>

          {error && (
            <div className="alert a-danger fade-in" role="alert">
              <Icon name="alert" />
              <div>{error}</div>
            </div>
          )}
          {notice && (
            <div className="alert a-info fade-in" role="status">
              <Icon name="info" />
              <div>
                {notice}{" "}
                <Link className="link" href="/login">
                  Sign in
                </Link>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: 16 }} aria-label="Create account">
            <div className="field">
              <label className="label" htmlFor="rg-name">
                Full name
              </label>
              <input className="input" id="rg-name" autoComplete="name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} disabled={isSubmitting} required />
            </div>
            <div className="field">
              <label className="label" htmlFor="rg-email">
                Email address
              </label>
              <input className="input" id="rg-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={isSubmitting} required />
            </div>
            <div className="field">
              <label className="label" htmlFor="rg-pw">
                Password
              </label>
              <input
                className="input"
                id="rg-pw"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-describedby="rg-req"
                disabled={isSubmitting}
                required
              />
              <PasswordChecklist id="rg-req" password={password} avoid={[email, displayName]} />
              <span className="hint">Required: at least {PASSWORD_MIN_LENGTH} characters. The other checks make it stronger.</span>
            </div>
            <div className="field">
              <label className="label" htmlFor="rg-pw2">
                Confirm password
              </label>
              <input
                className={`input${mismatch ? " is-error" : ""}`}
                id="rg-pw2"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                aria-invalid={mismatch}
                aria-describedby={mismatch ? "rg-pw2-err" : undefined}
                disabled={isSubmitting}
                required
              />
              {mismatch && <FieldError id="rg-pw2-err">Passwords don’t match yet</FieldError>}
            </div>
            <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={isSubmitting} aria-busy={isSubmitting}>
              {isSubmitting ? (
                <>
                  <span className="spinner" />
                  Creating account…
                </>
              ) : (
                <>
                  Create account
                  <Icon name="arrowRight" />
                </>
              )}
            </button>
          </form>
          <p className="t-body-sm secondary" style={{ textAlign: "center" }}>
            Already have an account?{" "}
            <Link className="link" href="/login">
              Sign in
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
