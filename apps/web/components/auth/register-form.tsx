"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { RegisterSchema } from "@/lib/schemas/auth";
import { useAuth } from "@/hooks/use-auth";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

interface RegisterFormProps {
  onSuccess?: () => void;
}

export function RegisterForm({ onSuccess }: RegisterFormProps) {
  const { register } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [businessModel, setBusinessModel] = useState<string>("retail");
  const [termsAgreed, setTermsAgreed] = useState(true);

  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Password rules & scoring
  const passwordStats = useMemo(() => {
    const hasLength = password.length >= 12;
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasDigit = /[0-9]/.test(password);
    const hasSymbol = /[^A-Za-z0-9]/.test(password);

    let score = 0;
    if (password.length > 0) score++;
    if (hasLength) score++;
    if (hasUpper && hasLower) score++;
    if (hasDigit && hasSymbol) score++;

    return { hasLength, hasUpper, hasLower, hasDigit, hasSymbol, score };
  }, [password]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setServerError(null);
    setSuccessMessage(null);

    if (!termsAgreed) {
      setValidationError("You must agree to the Terms of Service to create an account.");
      return;
    }

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
    <div className="w-full max-w-[1440px] mx-auto min-w-0">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
        {/* Left Column: Registration Card Container (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          <div className="bg-white shadow-sm rounded-3xl p-6 sm:p-8 md:p-10 border border-slate-200/80 relative overflow-hidden">
            {/* Accent Micro-Layer */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-600 via-sky-500 to-emerald-500" />

            {/* Top Brand Badge */}
            <div className="flex items-center justify-between gap-3 mb-6">
              <div className="flex items-center gap-3">
                <BizPilotLogo className="w-10 h-10 rounded-xl shadow-sm" size={40} />
                <div className="flex flex-col">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    New account
                  </span>
                  <span className="text-base font-bold text-slate-900 leading-tight">
                    BizPilot AI
                  </span>
                </div>
              </div>
            </div>

            {/* Main Header */}
            <div className="flex flex-col gap-1 mb-6">
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                Create your account
              </h1>
              <p className="text-sm text-slate-500 max-w-xl">
                Create your login, then set up your business workspace to record sales, stock, payments and expenses.
              </p>
            </div>

            {/* Success Alert */}
            {successMessage && (
              <div
                role="status"
                className="mb-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
              >
                <div className="font-semibold">{successMessage}</div>
                <Link
                  href="/login"
                  className="mt-2 inline-flex items-center gap-1 font-bold text-emerald-900 underline hover:text-emerald-950"
                >
                  Proceed to Sign in →
                </Link>
              </div>
            )}

            {/* Server Error Alert */}
            {serverError && (
              <div
                role="alert"
                className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 flex items-center gap-2"
              >
                <span className="font-bold">⚠️</span>
                <span>{serverError}</span>
              </div>
            )}

            {/* Validation Error Alert */}
            {validationError && (
              <div
                role="alert"
                className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 flex items-center gap-2"
              >
                <span className="font-bold">⚠️</span>
                <span>{validationError}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
              {/* Full Name & Email */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="flex flex-col gap-1">
                  <label htmlFor="display_name" className="text-xs font-semibold text-slate-800">
                    Full Name / Contact Person *
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">
                      👤
                    </span>
                    <input
                      id="display_name"
                      name="display_name"
                      type="text"
                      autoComplete="name"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      disabled={isSubmitting}
                      required
                      placeholder="e.g. Jansher Khan"
                      className="w-full h-10 pl-9 pr-3 bg-slate-50 focus:bg-white text-slate-900 placeholder:text-slate-400 text-sm rounded-xl border border-slate-200 focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 focus:outline-none transition-all"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <label htmlFor="email" className="text-xs font-semibold text-slate-800">
                    Business Email Address *
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">
                      ✉️
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
                      placeholder="name@company.com"
                      className="w-full h-10 pl-9 pr-3 bg-slate-50 focus:bg-white text-slate-900 placeholder:text-slate-400 text-sm rounded-xl border border-slate-200 focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 focus:outline-none transition-all"
                    />
                  </div>
                </div>
              </div>

              {/* Business Model Selector */}
              <div className="flex flex-col gap-1.5 mt-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-800">
                    Business Operating Model
                  </label>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { id: "retail", label: "Retail & POS", icon: "🏪" },
                    { id: "wholesale", label: "Wholesale & Dist.", icon: "📦" },
                    { id: "ecommerce", label: "Online seller", icon: "🛍️" },
                    { id: "services", label: "Services & Other", icon: "💼" },
                  ].map((model) => (
                    <button
                      key={model.id}
                      type="button"
                      onClick={() => setBusinessModel(model.id)}
                      className={`h-10 px-2 rounded-xl flex items-center justify-center gap-1.5 text-xs font-semibold transition-all border ${
                        businessModel === model.id
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                          : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                      }`}
                    >
                      <span>{model.icon}</span>
                      <span className="truncate">{model.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Password & Live Strength Meter */}
              <div className="flex flex-col gap-1 mt-1">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className="text-xs font-semibold text-slate-800">
                    Create Master Password *
                  </label>
                  <span className="text-[11px] font-mono font-semibold uppercase text-slate-500">
                    {passwordStats.score <= 1
                      ? "Too weak"
                      : passwordStats.score === 2
                      ? "Moderate"
                      : passwordStats.score === 3
                      ? "Good"
                      : "Enterprise Grade"}
                  </span>
                </div>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">
                    🔒
                  </span>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isSubmitting}
                    required
                    placeholder="Must be at least 12 characters"
                    className="w-full h-10 pl-9 pr-12 bg-slate-50 focus:bg-white text-slate-900 placeholder:text-slate-400 text-sm font-mono rounded-xl border border-slate-200 focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 focus:outline-none transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 text-xs font-semibold px-1"
                  >
                    {showPassword ? "HIDE" : "SHOW"}
                  </button>
                </div>

                {/* 4-Segment Strength Bars */}
                <div className="grid grid-cols-4 gap-1.5 mt-1">
                  <div
                    className={`h-1 rounded-full transition-colors ${
                      passwordStats.score >= 1 ? "bg-rose-500" : "bg-slate-200"
                    }`}
                  />
                  <div
                    className={`h-1 rounded-full transition-colors ${
                      passwordStats.score >= 2 ? "bg-amber-500" : "bg-slate-200"
                    }`}
                  />
                  <div
                    className={`h-1 rounded-full transition-colors ${
                      passwordStats.score >= 3 ? "bg-indigo-500" : "bg-slate-200"
                    }`}
                  />
                  <div
                    className={`h-1 rounded-full transition-colors ${
                      passwordStats.score >= 4 ? "bg-emerald-500" : "bg-slate-200"
                    }`}
                  />
                </div>

                {/* Password Requirements Pills */}
                <div className="flex flex-wrap items-center gap-3 mt-1 text-[11px]">
                  <span
                    className={
                      passwordStats.hasLength
                        ? "text-emerald-600 font-semibold"
                        : "text-slate-400"
                    }
                  >
                    {passwordStats.hasLength ? "✓" : "○"} Min 12 characters
                  </span>
                  <span
                    className={
                      passwordStats.hasUpper && passwordStats.hasLower
                        ? "text-emerald-600 font-semibold"
                        : "text-slate-400"
                    }
                  >
                    {passwordStats.hasUpper && passwordStats.hasLower ? "✓" : "○"} Upper & lower case
                  </span>
                  <span
                    className={
                      passwordStats.hasDigit && passwordStats.hasSymbol
                        ? "text-emerald-600 font-semibold"
                        : "text-slate-400"
                    }
                  >
                    {passwordStats.hasDigit && passwordStats.hasSymbol ? "✓" : "○"} Numbers & symbols
                  </span>
                </div>
              </div>

              {/* Agreement Checkbox */}
              <div className="flex items-start gap-2.5 mt-2 p-3 bg-slate-50 rounded-xl border border-slate-100">
                <input
                  id="terms-agree"
                  type="checkbox"
                  checked={termsAgreed}
                  onChange={(e) => setTermsAgreed(e.target.checked)}
                  required
                  className="mt-0.5 w-4 h-4 rounded text-indigo-600 border-slate-300 focus:ring-indigo-500 accent-indigo-600 cursor-pointer flex-shrink-0"
                />
                <label
                  htmlFor="terms-agree"
                  className="text-xs text-slate-600 leading-relaxed cursor-pointer select-none"
                >
                  I agree to the BizPilot AI{" "}
                  <span className="text-indigo-600 font-semibold hover:underline">
                    Terms of Service
                  </span>{" "}
                  and{" "}
                  <span className="text-indigo-600 font-semibold hover:underline">
                    Privacy Policy
                  </span>
                  , with strict PostgreSQL tenant isolation.
                </label>
              </div>

              {/* Submit CTA */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full h-11 mt-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold shadow-md shadow-indigo-600/20 hover:shadow-lg transition-all flex items-center justify-center gap-2 active:scale-[0.99] disabled:opacity-50"
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
                  <>
                    <span>Create account</span>
                    <span>→</span>
                  </>
                )}
              </button>

              {/* Switch to Sign In */}
              <div className="flex items-center justify-center gap-1.5 mt-2 text-center text-xs text-slate-500">
                <span>Already have an account?</span>
                <Link
                  href="/login"
                  className="font-semibold text-indigo-600 hover:text-indigo-700 hover:underline"
                >
                  Sign In →
                </Link>
              </div>
            </form>
          </div>
        </div>

        {/* Right Column: what P0 does */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="bg-white shadow-sm rounded-3xl p-6 sm:p-8 border border-slate-200/80 flex flex-col gap-4">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight leading-snug">
              What you can do with BizPilot
            </h2>
            <ul className="space-y-3 text-sm text-slate-600">
              <li><strong className="text-slate-900">Products and stock:</strong> opening stock, adjustments with a reason, and low-stock alerts.</li>
              <li><strong className="text-slate-900">Orders:</strong> record sales for a named or walk-in customer; stock is deducted once.</li>
              <li><strong className="text-slate-900">Payments and expenses:</strong> record money received and spent in PKR.</li>
              <li><strong className="text-slate-900">Dashboard:</strong> totals for a selected day or period, with links to the source records.</li>
              <li><strong className="text-slate-900">AI assistant (read-only):</strong> answers questions from your own records and never changes them.</li>
            </ul>
            <p className="text-xs text-slate-400">
              BizPilot records what you enter. It is not an accounting, tax or banking system.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
