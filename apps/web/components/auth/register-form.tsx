"use client";

import React, { useState } from "react";
import Link from "next/link";
import { RegisterSchema } from "@/lib/schemas/auth";
import { useAuth } from "@/hooks/use-auth";

interface RegisterFormProps {
  onSuccess?: () => void;
}

export function RegisterForm({ onSuccess }: RegisterFormProps) {
  const { register } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setServerError(null);
    setSuccessMessage(null);

    const parseResult = RegisterSchema.safeParse({
      display_name: displayName,
      email,
      password,
    });

    if (!parseResult.success) {
      setValidationError(parseResult.error.issues[0]?.message || "Invalid input");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await register({
        display_name: displayName,
        email,
        password,
      });
      setSuccessMessage(res.message || "Account created successfully. Please sign in.");
      if (onSuccess) {
        onSuccess();
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unable to register. Please try again.";
      setServerError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Create your account</h1>
        <p className="mt-2 text-sm text-slate-600">
          Get started with BizPilot AI for your business
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
          <label htmlFor="display_name" className="block text-sm font-medium text-slate-700">
            Full name / Business contact
          </label>
          <input
            id="display_name"
            name="display_name"
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            disabled={isSubmitting}
            required
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 disabled:bg-slate-50"
            placeholder="Asad Khan"
          />
        </div>

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
            placeholder="asad@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-700">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
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
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <svg
                className="h-4 w-4 animate-spin text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v8H4z"
                />
              </svg>
              Creating account...
            </span>
          ) : (
            "Create account"
          )}
        </button>
      </form>

      <div className="mt-6 text-center text-sm text-slate-600">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-emerald-700 hover:text-emerald-800">
          Sign in
        </Link>
      </div>
    </div>
  );
}
