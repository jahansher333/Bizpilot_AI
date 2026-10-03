"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ForgotPasswordSchema } from "@/lib/schemas/auth";
import { forgotPasswordRequest } from "@/lib/api/auth";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

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
    <div className="w-full max-w-md rounded-2xl border border-surface-container-high/60 bg-surface-container-lowest p-6 sm:p-8 shadow-sm relative overflow-hidden">
      {/* Accent Micro-Layer */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary via-secondary to-tertiary" />

      <div className="mb-6 text-center">
        <div className="flex justify-center mb-3">
          <BizPilotLogo size="lg" />
        </div>
        <h1 className="font-headline-lg text-2xl font-bold tracking-tight text-on-surface">Reset your password</h1>
        <p className="mt-1 font-body-sm text-xs text-on-surface-variant">
          Enter your registered email and we&apos;ll send recovery instructions
        </p>
      </div>

      {successMessage && (
        <div
          role="status"
          className="mb-5 rounded-xl border border-tertiary/20 bg-tertiary-container/15 p-4 text-xs text-tertiary font-medium flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[16px]">check_circle</span>
          <span>{successMessage}</span>
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
          <label htmlFor="email" className="block font-label-caps text-xs font-semibold uppercase text-on-surface-variant tracking-wider">
            Business Email Address *
          </label>
          <div className="relative mt-1.5">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]">
              mail
            </span>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              required
              className="w-full h-11 pl-9 pr-3 bg-surface-container-lowest text-on-surface placeholder:text-outline text-sm rounded-lg border border-outline-variant/40 focus:border-primary focus:ring-2 focus:ring-primary/10 focus:outline-none transition-all disabled:opacity-50 font-body-sm shadow-xs"
              placeholder="e.g. jahansherkhan9876@gmail.com"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full h-11 bg-primary hover:bg-primary-container text-on-primary rounded-lg text-sm font-semibold shadow-sm transition-all flex items-center justify-center gap-2 active:scale-[0.99] disabled:opacity-50 font-body-sm"
        >
          {isSubmitting ? "Sending instructions..." : "Send recovery link →"}
        </button>
      </form>

      <div className="mt-6 text-center font-body-sm text-xs text-on-surface-variant">
        Remember your password?{" "}
        <Link href="/login" className="font-semibold text-primary hover:text-primary-container hover:underline">
          Sign in
        </Link>
      </div>
    </div>
  );
}
