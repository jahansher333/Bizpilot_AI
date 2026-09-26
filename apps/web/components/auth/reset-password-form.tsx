"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ResetPasswordSchema } from "@/lib/schemas/auth";
import { resetPasswordSubmit } from "@/lib/api/auth";

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
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Set new password</h1>
        <p className="mt-2 text-sm text-slate-600">
          Enter your recovery token and choose a new secure password
        </p>
      </div>

      {successMessage && (
        <div
          role="status"
          className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"
        >
          {successMessage}{" "}
          <Link href="/login" className="font-semibold underline hover:text-emerald-950">
            Proceed to Sign in
          </Link>
        </div>
      )}

      {serverError && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
        >
          {serverError}
        </div>
      )}

      {validationError && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
        >
          {validationError}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="token" className="block text-sm font-medium text-slate-700">
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
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 disabled:bg-slate-50"
            placeholder="Paste reset token"
          />
        </div>

        <div>
          <label htmlFor="new_password" className="block text-sm font-medium text-slate-700">
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
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 disabled:bg-slate-50"
          />
          <p className="mt-1 text-xs text-slate-500">
            Must be at least 12 characters in length.
          </p>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-2 flex w-full items-center justify-center rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2 disabled:opacity-50"
        >
          {isSubmitting ? "Resetting password..." : "Update password"}
        </button>
      </form>

      <div className="mt-6 text-center text-sm text-slate-600">
        Back to{" "}
        <Link href="/login" className="font-semibold text-emerald-700 hover:text-emerald-800">
          Sign in
        </Link>
      </div>
    </div>
  );
}
