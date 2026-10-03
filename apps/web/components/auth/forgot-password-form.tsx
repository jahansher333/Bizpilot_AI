"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ForgotPasswordSchema } from "@/lib/schemas/auth";
import { ApiError, forgotPasswordRequest } from "@/lib/api/auth";
import { Icon } from "@/components/ui/icon";
import { AuthCardShell } from "@/components/auth/auth-card-shell";

const RESEND_SECONDS = 60;

/** Design canvas "04 · Forgot password": request, sent (same message for every email), error. */
export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function send() {
    setValidationError(null);
    setServerError(null);
    const parsed = ForgotPasswordSchema.safeParse({ email });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message || "Enter a valid email address");
      return;
    }
    setIsSubmitting(true);
    try {
      await forgotPasswordRequest(parsed.data);
      setSentTo(parsed.data.email);
      setCooldown(RESEND_SECONDS);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 429) {
        setServerError(err.message);
      } else {
        setServerError("You’re offline or our server didn’t respond. Your email is kept — try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (sentTo) {
    const mins = Math.floor(cooldown / 60);
    const secs = String(cooldown % 60).padStart(2, "0");
    return (
      <AuthCardShell>
        <span className="dlg-icon ok pop-in">
          <Icon name="check" size="lg" className="check-anim" style={{ strokeWidth: 2.2 }} />
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }} role="status">
          <h1 className="t-h2">Check your email</h1>
          <p className="t-body-sm secondary">
            If an account exists for <b style={{ color: "var(--text-primary)", fontWeight: 500 }}>{sentTo}</b>, we’ve sent recovery
            instructions. The link expires soon and works once.
          </p>
        </div>
        <div className="well" style={{ padding: "12px 14px" }}>
          <p className="t-body-sm secondary">Nothing after a few minutes? Check your spam folder, or make sure you used the email you sign in with.</p>
        </div>
        <button type="button" className="btn btn-secondary btn-block" disabled={cooldown > 0 || isSubmitting} onClick={send}>
          {cooldown > 0 ? `Resend in ${mins}:${secs}` : "Resend instructions"}
        </button>
        {serverError && (
          <div className="alert a-danger" role="alert">
            <Icon name="alert" />
            <div>{serverError}</div>
          </div>
        )}
        <Link className="link t-body-sm" href="/login" style={{ alignSelf: "center" }}>
          Back to sign in
        </Link>
      </AuthCardShell>
    );
  }

  return (
    <AuthCardShell>
      <span className="dlg-icon neutral">
        <Icon name="lock" size="lg" />
      </span>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <h1 className="t-h2">Reset your password</h1>
        <p className="t-body-sm secondary">Enter the email you use for BizPilot. If an account exists, we’ll send recovery instructions.</p>
      </div>
      {serverError && (
        <div className="alert a-danger" role="alert">
          <Icon name="alert" />
          <div>
            <div className="a-t">We couldn’t send that request</div>
            {serverError}
          </div>
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
        noValidate
        style={{ display: "flex", flexDirection: "column", gap: 20 }}
      >
        <div className="field">
          <label className="label" htmlFor="fp-email">
            Email address
          </label>
          <input
            className={`input${validationError ? " is-error" : ""}`}
            id="fp-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={!!validationError}
            aria-describedby={validationError ? "fp-email-err" : undefined}
            disabled={isSubmitting}
            required
          />
          {validationError && (
            <span className="err" id="fp-email-err" role="alert">
              <Icon name="alert" size="sm" />
              {validationError}
            </span>
          )}
        </div>
        <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={isSubmitting} aria-busy={isSubmitting}>
          {isSubmitting ? (
            <>
              <span className="spinner" />
              Sending…
            </>
          ) : serverError ? (
            <>
              <Icon name="refresh" />
              Try again
            </>
          ) : (
            "Send recovery link"
          )}
        </button>
      </form>
      <Link className="link t-body-sm" href="/login" style={{ alignSelf: "center" }}>
        Back to sign in
      </Link>
    </AuthCardShell>
  );
}
