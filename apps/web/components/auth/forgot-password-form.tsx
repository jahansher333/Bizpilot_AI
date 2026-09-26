"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ForgotPasswordSchema } from "@/lib/schemas/auth";
import { forgotPasswordRequest } from "@/lib/api/auth";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setServerError(null);
    setSuccessMessage(null);

    const parseResult = ForgotPasswordSchema.safeParse({ email });
    if (!parseResult.success) {
      setValidationError(parseResult.error.issues[0]?.message || "Invalid email");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await forgotPasswordRequest({ email });
      setSuccessMessage(
        res.message ||
          "If an eligible account exists for this email, password recovery instructions have been sent."
      );
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "An unexpected error occurred. Please try again.";
      setServerError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Reset your password</h1>
        <p className="mt-2 text-sm text-slate-600">
          Enter your registered email and we&apos;ll send recovery instructions
        </p>
      </div>

      {successMessage && (
        <div
          role="status"
          className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"
        >
          {successMessage}
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
          <label htmlFor="email" className="block text-sm font-medium text-slate-700">
            Email address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isSubmitting}
            required
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 disabled:bg-slate-50"
            placeholder="founder@example.com"
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-2 flex w-full items-center justify-center rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2 disabled:opacity-50"
        >
          {isSubmitting ? "Sending instructions..." : "Send recovery link"}
        </button>
      </form>

      <div className="mt-6 text-center text-sm text-slate-600">
        Remember your password?{" "}
        <Link href="/login" className="font-semibold text-emerald-700 hover:text-emerald-800">
          Sign in
        </Link>
      </div>
    </div>
  );
}
