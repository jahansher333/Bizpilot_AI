"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ResetPasswordSchema } from "@/lib/schemas/auth";
import { resetPasswordSubmit } from "@/lib/api/auth";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

export function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const initialToken = searchParams?.get("token") || "";

  const [token, setToken] = useState(initialToken);
  const [newPassword, setNewPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setServerError(null);
    setSuccessMessage(null);

    const parseResult = ResetPasswordSchema.safeParse({
      token,
      new_password: newPassword,
    });

    if (!parseResult.success) {
      setValidationError(parseResult.error.issues[0]?.message || "Invalid input");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await resetPasswordSubmit({
        token,
        new_password: newPassword,
      });
      setSuccessMessage(
        res.message || "Password reset successfully. Please log in with your new password."
      );
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unable to reset password. Please check your token.";
      setServerError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-2xl border border-surface-container-high/60 bg-surface-container-lowest p-6 sm:p-8 shadow-sm relative overflow-hidden">
      {/* Accent Micro-Layer */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary via-secondary to-tertiary" />

      <div className="mb-6 text-center">
        <div className="flex justify-center mb-3">
          <BizPilotLogo size="lg" />
        </div>
        <h1 className="font-headline-lg text-2xl font-bold tracking-tight text-on-surface">Set new password</h1>
        <p className="mt-1 font-body-sm text-xs text-on-surface-variant">
          Enter your recovery token and choose a new secure password
        </p>
      </div>

      {successMessage && (
        <div
          role="status"
          className="mb-5 rounded-xl border border-tertiary/20 bg-tertiary-container/15 p-4 text-xs text-tertiary font-medium flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[16px]">check_circle</span>
          <span>
            {successMessage}{" "}
            <Link href="/login" className="font-semibold underline hover:text-tertiary-fixed-dim">
              Proceed to Sign in
            </Link>
          </span>
        </div>
      )}

      {serverError && (
        <div
          role="alert"
          className="mb-5 rounded-xl border border-error/20 bg-error-container/15 p-3 text-xs text-error font-medium flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[16px]">error</span>
          <span>{serverError}</span>
        </div>
      )}

      {validationError && (
        <div
          role="alert"
          className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 font-medium flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[16px]">warning</span>
          <span>{validationError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="token" className="block font-label-caps text-xs font-semibold uppercase text-on-surface-variant tracking-wider">
            Reset token
          </label>
          <input
            id="token"
            name="token"
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            disabled={isSubmitting}
            required
            className="mt-1.5 block w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-2 text-sm font-mono text-on-surface shadow-xs focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 disabled:bg-surface-container-low transition-all font-data-cell"
            placeholder="Paste reset token"
          />
        </div>

        <div>
          <label htmlFor="new_password" className="block font-label-caps text-xs font-semibold uppercase text-on-surface-variant tracking-wider">
            New password
          </label>
          <input
            id="new_password"
            name="new_password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={isSubmitting}
            required
            className="mt-1.5 block w-full rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface shadow-xs focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 disabled:bg-surface-container-low transition-all"
          />
          <p className="mt-1 font-body-sm text-xs text-outline">
            Must be at least 12 characters in length.
          </p>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary px-4 py-2.5 font-body-sm text-sm font-semibold text-on-primary shadow-sm hover:bg-primary-container active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50 transition-all"
        >
          {isSubmitting ? "Resetting password..." : "Update password"}
        </button>
      </form>

      <div className="mt-6 text-center font-body-sm text-xs text-on-surface-variant">
        <Link href="/login" className="font-semibold text-primary hover:text-primary-container hover:underline">
          Return to Sign in
        </Link>
      </div>
    </div>
  );
}
