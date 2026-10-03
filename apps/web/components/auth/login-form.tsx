"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LoginSchema } from "@/lib/schemas/auth";
import { useAuth } from "@/hooks/use-auth";
import { Icon } from "@/components/ui/icon";
import { LoginBrandPanel } from "@/components/auth/auth-brand-panel";

interface LoginFormProps {
  onSuccess?: (orgId?: string) => void;
  /** Shown after the session expired and the user was signed out. */
  sessionExpired?: boolean;
}

/** Design canvas "02 · Login". */
export function LoginForm({ onSuccess, sessionExpired = false }: LoginFormProps) {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setServerError(null);

    const parseResult = LoginSchema.safeParse({ email, password });
    if (!parseResult.success) {
      setValidationError(parseResult.error.issues[0]?.message || "Invalid input");
      return;
    }

    setIsSubmitting(true);
    try {
      const { organizations } = await login({ email, password });
      if (onSuccess) {
        onSuccess(organizations[0]?.id);
      } else if (organizations.length === 1) {
        router.push(`/workspace/${organizations[0].id}`);
      } else {
        router.push("/workspaces");
      }
    } catch (err: unknown) {
      setServerError(err instanceof Error && err.message ? err.message : "Unable to sign in. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const credentialsInvalid = serverError !== null;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexWrap: "wrap", background: "var(--surface)" }}>
      <LoginBrandPanel />

      <main style={{ flex: "1 1 520px", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px", background: "var(--surface)" }}>
        <div className="page-in" style={{ width: "100%", maxWidth: 380, display: "flex", flexDirection: "column", gap: 28 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h1 className="t-h1">Welcome back</h1>
            <p className="t-body secondary">Sign in to your BizPilot workspace.</p>
          </div>

          {sessionExpired && !serverError && (
            <div className="alert a-info fade-in" role="status">
              <Icon name="info" />
              <div>
                <div className="a-t">Your session expired</div>
                For your security we signed you out. Sign in to continue where you left off.
              </div>
            </div>
          )}
          {(serverError || validationError) && (
            <div className="alert a-danger fade-in" role="alert">
              <Icon name="alert" />
              <div>
                <div className="a-t">{validationError ? "Check your details" : "Couldn’t sign you in"}</div>
                {validationError ?? serverError}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate style={{ display: "flex", flexDirection: "column", gap: 16 }} aria-label="Sign in">
            <div className="field">
              <label className="label" htmlFor="li-email">
                Email address
              </label>
              <input
                className={`input${credentialsInvalid ? " is-error" : ""}`}
                id="li-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={credentialsInvalid}
                disabled={isSubmitting}
                required
              />
            </div>
            <div className="field">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <label className="label" htmlFor="li-pw">
                  Password
                </label>
                <Link className="link t-body-sm" href="/forgot-password">
                  Forgot password?
                </Link>
              </div>
              <div className={`ig${credentialsInvalid ? " is-error" : ""}`}>
                <input
                  id="li-pw"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-invalid={credentialsInvalid}
                  disabled={isSubmitting}
                  required
                />
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ height: "100%", borderRadius: 0, borderLeft: "1px solid var(--border)" }}
                  onClick={() => setShowPassword((v) => !v)}
                  aria-pressed={showPassword}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            <button type="submit" className={`btn btn-primary btn-lg btn-block${isSubmitting ? " is-loading" : ""}`} disabled={isSubmitting} aria-busy={isSubmitting}>
              {isSubmitting ? (
                <>
                  <span className="spinner" />
                  Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          <div style={{ display: "flex", flexDirection: "column", gap: 16, alignItems: "center" }}>
            <p className="t-body-sm secondary">
              New to BizPilot?{" "}
              <Link className="link" href="/register">
                Create an account
              </Link>
            </p>
            <p className="t-caption" style={{ textAlign: "center" }}>
              Each business only ever sees its own records.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
