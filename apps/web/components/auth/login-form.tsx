"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LoginSchema } from "@/lib/schemas/auth";
import { useAuth } from "@/hooks/use-auth";

interface LoginFormProps {
  onSuccess?: (orgId?: string) => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberDevice, setRememberDevice] = useState(true);
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
      } else if (organizations.length > 0) {
        router.push(`/workspace/${organizations[0].id}`);
      } else {
        router.push("/onboarding");
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unable to sign in. Please verify your credentials.";
      setServerError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-[1440px] mx-auto min-w-0">
      <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-stretch">
        {/* Left Column: Sign-in Form */}
        <div className="lg:col-span-7 xl:col-span-7 flex flex-col justify-center py-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 md:p-10 shadow-sm border border-slate-200/80 flex flex-col justify-between max-w-[620px] w-full mx-auto relative overflow-hidden">
            {/* Subtle Gradient Glow */}
            <div className="absolute top-0 right-0 w-72 h-72 bg-gradient-to-bl from-indigo-100/50 via-sky-50/30 to-transparent rounded-full blur-2xl pointer-events-none -mr-16 -mt-16" />

            <div className="relative z-10">
              {/* Header Badge */}
              <div className="flex items-center justify-between gap-3 mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                    ⚡
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="font-semibold text-slate-900 tracking-tight text-lg">
                      BizPilot <span className="text-indigo-600">OS</span>
                    </span>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      AI-Powered Business Operating System
                    </span>
                  </div>
                </div>
                <div className="inline-flex items-center gap-1.5 bg-slate-100 px-3 py-1 rounded-full text-sky-700 text-xs font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>Enterprise Ready</span>
                </div>
              </div>

              {/* Title */}
              <div className="space-y-1 mb-6">
                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
                  Sign in to BizPilot
                </h1>
                <p className="text-sm text-slate-500">
                  Access your dashboard, stock records and AI assistant.
                </p>
              </div>

              {/* Fast-Pass Options */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
                <button
                  type="button"
                  onClick={() => {
                    setEmail("jahansherkhan9876@gmail.com");
                  }}
                  className="w-full flex items-center justify-center gap-2 bg-slate-50 hover:bg-slate-100 text-slate-700 py-2.5 px-3 rounded-xl text-xs font-semibold border border-slate-200 transition-colors"
                >
                  <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24">
                    <path
                      d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.4 1 3.5 3.6 1.6 7.4l3.7 2.9C6.2 7.3 8.8 5 12 5z"
                      fill="#EA4335"
                    />
                    <path
                      d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"
                      fill="#4285F4"
                    />
                    <path
                      d="M5.3 14.7c-.2-.7-.4-1.5-.4-2.7s.1-2 .4-2.7L1.6 6.4C.6 8.3 0 10.1 0 12s.6 3.7 1.6 5.6l3.7-2.9z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3.2 0-5.8-2.3-6.7-5.3L1.6 16c1.9 3.8 5.8 7 10.4 7z"
                      fill="#34A853"
                    />
                  </svg>
                  <span className="truncate">Fill Saved Credentials</span>
                </button>
                <div className="w-full flex items-center justify-center gap-2 bg-slate-50 text-slate-700 py-2.5 px-3 rounded-xl text-xs font-semibold border border-slate-200">
                  <span className="text-emerald-600 font-bold">🇵🇰</span>
                  <span className="truncate">Pakistan SME Optimized</span>
                </div>
              </div>

              {/* Divider */}
              <div className="flex items-center gap-3 mb-6">
                <div className="h-px bg-slate-200 flex-1" />
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  continue with email
                </span>
                <div className="h-px bg-slate-200 flex-1" />
              </div>

              {/* Alerts */}
              {serverError && (
                <div
                  role="alert"
                  className="mb-5 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 flex items-center gap-2"
                >
                  <span className="font-bold">⚠️</span>
                  <span>{serverError}</span>
                </div>
              )}

              {validationError && (
                <div
                  role="alert"
                  className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 flex items-center gap-2"
                >
                  <span className="font-bold">⚠️</span>
                  <span>{validationError}</span>
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label htmlFor="email" className="text-xs font-semibold text-slate-800">
                      Email address
                    </label>
                    <span className="text-[10px] font-mono font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                      SECURE ID
                    </span>
                  </div>
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
                      className="w-full h-11 pl-9 pr-3 bg-slate-50 focus:bg-white text-slate-900 placeholder:text-slate-400 text-sm rounded-xl border border-slate-200 focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 focus:outline-none transition-all disabled:opacity-50"
                      placeholder="e.g. jahansherkhan9876@gmail.com"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label htmlFor="password" className="text-xs font-semibold text-slate-800">
                      Password
                    </label>
                    <Link
                      href="/forgot-password"
                      className="text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">
                      🔒
                    </span>
                    <input
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      disabled={isSubmitting}
                      required
                      className="w-full h-11 pl-9 pr-10 bg-slate-50 focus:bg-white text-slate-900 placeholder:text-slate-400 text-sm font-mono rounded-xl border border-slate-200 focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 focus:outline-none transition-all disabled:opacity-50"
                      placeholder="••••••••••••"
                    />
                    <button
                      type="button"
                      aria-label="Toggle visibility"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 text-xs font-semibold px-1"
                    >
                      {showPassword ? "HIDE" : "SHOW"}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={rememberDevice}
                      onChange={(e) => setRememberDevice(e.target.checked)}
                      className="w-4 h-4 rounded text-indigo-600 border-slate-300 focus:ring-indigo-500 accent-indigo-600 cursor-pointer"
                    />
                    <span className="text-xs text-slate-600">Remember this session</span>
                  </label>
                  <div className="flex items-center gap-1 text-emerald-700 text-xs font-medium">
                    <span>🛡️</span>
                    <span>256-bit Encrypted</span>
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full h-11 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold shadow-md shadow-indigo-600/20 hover:shadow-lg transition-all flex items-center justify-center gap-2 active:scale-[0.99] disabled:opacity-50"
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
                        Authenticating...
                      </span>
                    ) : (
                      <>
                        <span>Sign in</span>
                        <span className="text-indigo-200">→</span>
                      </>
                    )}
                  </button>
                </div>
              </form>

              {/* Security Tag */}
              <div className="mt-5 p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-2.5 text-xs text-slate-500">
                <span className="text-indigo-600 text-sm mt-0.5">✓</span>
                <p className="leading-relaxed">
                  <strong className="text-slate-700 font-semibold">
                    Your data stays in your workspace.
                  </strong>{" "}
                  Each business can only see its own records.
                </p>
              </div>

              {/* Footer Switch */}
              <div className="mt-6 text-center text-sm text-slate-500">
                Don&apos;t have an account yet?{" "}
                <Link
                  href="/register"
                  className="font-semibold text-indigo-600 hover:text-indigo-700 hover:underline"
                >
                  Create business account →
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Stitch Operations Showcase & Pakistan SME Trust */}
        <div className="lg:col-span-5 xl:col-span-5 flex flex-col justify-between py-4">
          <div className="bg-gradient-to-br from-indigo-900 via-slate-900 to-indigo-950 text-white rounded-3xl p-6 sm:p-8 md:p-10 flex flex-col justify-between h-full relative overflow-hidden shadow-lg border border-indigo-800/40">
            {/* Ambient Background Aura */}
            <div className="absolute -bottom-20 -right-20 w-80 h-80 bg-sky-500/20 rounded-full blur-3xl pointer-events-none" />

            <div className="space-y-6">
              <div className="inline-flex items-center gap-1.5 bg-white/10 px-3 py-1 rounded-full text-xs font-semibold text-emerald-300">
                <span>Built for Pakistani small businesses</span>
              </div>

              <div className="space-y-3">
                <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white leading-snug">
                  Your daily business records in one place.
                </h2>
                <p className="text-sm text-slate-300 leading-relaxed">
                  Record what happens in your business by hand and see it clearly. BizPilot does not
                  connect to banks, file taxes or replace your accountant.
                </p>
              </div>

              <ul className="space-y-2 text-sm text-slate-200">
                <li className="flex gap-2"><span className="text-emerald-400">✓</span> Products, categories and stock levels with low-stock alerts</li>
                <li className="flex gap-2"><span className="text-emerald-400">✓</span> Orders, payments received and expenses in PKR</li>
                <li className="flex gap-2"><span className="text-emerald-400">✓</span> A simple dashboard for any day or period</li>
                <li className="flex gap-2"><span className="text-emerald-400">✓</span> Owner, Manager and Staff roles for your team</li>
                <li className="flex gap-2"><span className="text-emerald-400">✓</span> An AI assistant that answers from your own records, read-only</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
