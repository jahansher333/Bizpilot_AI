"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { CreateOrganizationSchema, Organization } from "@/lib/schemas/organizations";
import { useAuth } from "@/hooks/use-auth";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

interface OrganizationSetupProps {
  onOrgSelected?: (org: Organization) => void;
}

export function OrganizationSetup({ onOrgSelected }: OrganizationSetupProps) {
  const router = useRouter();
  const { user, organizations, createOrg, selectOrg, logout } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [currencyCode] = useState("PKR");
  const [timezone] = useState("Asia/Karachi");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setServerError(null);

    const parseResult = CreateOrganizationSchema.safeParse({
      display_name: displayName,
      currency_code: currencyCode,
      timezone,
    });

    if (!parseResult.success) {
      setValidationError(parseResult.error.issues[0]?.message || "Invalid input");
      return;
    }

    setIsSubmitting(true);
    try {
      const createdOrg = await createOrg({
        display_name: displayName,
        currency_code: currencyCode,
        timezone,
      });

      if (onOrgSelected) {
        onOrgSelected(createdOrg);
      } else {
        router.push(`/workspace/${createdOrg.id}`);
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unable to create organization workspace.";
      setServerError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSelectExisting(org: Organization) {
    selectOrg(org.id);
    if (onOrgSelected) {
      onOrgSelected(org);
    } else {
      router.push(`/workspace/${org.id}`);
    }
  }

  return (
    <div className="w-full max-w-3xl bg-surface-container-lowest rounded-2xl border border-surface-container-high/60 shadow-sm p-6 sm:p-8 md:p-10 relative overflow-hidden">
      {/* Accent Micro-Layer */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary via-secondary to-tertiary" />

      {/* Header */}
      <div className="flex items-center justify-between border-b border-surface-container-low pb-5">
        <div className="flex items-center gap-3">
          <BizPilotLogo size="md" />
          <div>
            <h1 className="font-headline-md text-lg font-bold tracking-tight text-on-surface">
              Business Workspaces
            </h1>
            <p className="font-body-sm text-xs text-on-surface-variant">
              Authenticated operator:{" "}
              <span className="font-semibold text-on-surface">{user?.email || "User"}</span>
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => logout().then(() => router.push("/login"))}
          className="rounded-lg border border-outline-variant/40 px-3 py-1.5 font-body-sm text-xs font-medium text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors"
        >
          Sign out
        </button>
      </div>

      {/* Progress Stepper Bar */}
      <div className="mt-5 p-4 rounded-xl bg-surface-container-low border border-surface-container-high/60">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-tertiary-container text-on-tertiary-container flex items-center justify-center text-xs font-bold">
              ✓
            </div>
            <span className="text-xs font-semibold text-tertiary hidden sm:inline">01 Profile</span>
          </div>
          <div className="h-0.5 flex-1 bg-tertiary/40"></div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-primary text-on-primary flex items-center justify-center text-xs font-bold">
              02
            </div>
            <span className="text-xs font-semibold text-primary">02 Workspace</span>
          </div>
          <div className="h-0.5 flex-1 bg-surface-container-high"></div>
          <div className="flex items-center gap-2 opacity-50">
            <div className="w-6 h-6 rounded-full bg-surface-container-high text-on-surface-variant flex items-center justify-center text-xs font-bold">
              03
            </div>
            <span className="text-xs text-outline hidden sm:inline">03 Team</span>
          </div>
          <div className="h-0.5 flex-1 bg-surface-container-high"></div>
          <div className="flex items-center gap-2 opacity-50">
            <div className="w-6 h-6 rounded-full bg-surface-container-high text-on-surface-variant flex items-center justify-center text-xs font-bold">
              04
            </div>
            <span className="text-xs text-outline hidden sm:inline">04 Launch</span>
          </div>
        </div>
      </div>

      {serverError && (
        <div
          role="alert"
          className="mt-4 rounded-xl border border-error/20 bg-error-container/15 p-3 text-xs text-error font-medium flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[16px]">error</span>
          <span>{serverError}</span>
        </div>
      )}

      {validationError && (
        <div
          role="alert"
          className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 font-medium flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[16px]">warning</span>
          <span>{validationError}</span>
        </div>
      )}

      {/* Existing Organizations List */}
      {organizations.length > 0 && (
        <div className="mt-6">
          <h2 className="font-label-caps text-xs font-semibold text-outline uppercase tracking-wider">
            Your existing workspaces
          </h2>
          <div className="mt-3 space-y-2.5">
            {organizations.map((org) => (
              <div
                key={org.id}
                className="flex items-center justify-between rounded-xl border border-surface-container-high/60 p-4 transition-all hover:border-primary/40 hover:bg-surface-container-low"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-on-surface">{org.display_name}</span>
                    <span className="rounded-full bg-primary-fixed text-on-primary-fixed px-2 py-0.5 font-data-badge text-[10px] font-semibold uppercase">
                      {org.role}
                    </span>
                  </div>
                  <p className="mt-1 font-data-badge text-xs text-outline">
                    Currency: {org.currency_code} • Zone: {org.timezone}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleSelectExisting(org)}
                  className="rounded-lg bg-primary px-3.5 py-2 font-body-sm text-xs font-semibold text-on-primary shadow-sm hover:bg-primary-container active:scale-[0.99] transition-all"
                >
                  Enter Workspace →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create New Workspace Form */}
      <div className={organizations.length > 0 ? "mt-8 border-t border-surface-container-low pt-6" : "mt-6"}>
        <div className="space-y-1 mb-4">
          <h2 className="font-headline-sm text-base font-bold text-on-surface">
            {organizations.length > 0
              ? "Or establish a new business workspace"
              : "Set up your business workspace"}
          </h2>
          <p className="font-body-sm text-xs text-on-surface-variant">
            Each workspace keeps its own products, stock, orders, payments and expenses separate from other businesses.
          </p>
        </div>

        <form onSubmit={handleCreateOrg} className="space-y-4" noValidate>
          <div>
            <label htmlFor="display_name" className="block font-label-caps text-xs font-semibold uppercase text-on-surface-variant tracking-wider">
              Registered Business Name *
            </label>
            <div className="relative mt-1.5">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]">
                storefront
              </span>
              <input
                id="display_name"
                name="display_name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={isSubmitting}
                required
                className="w-full h-11 pl-9 pr-3 bg-surface-container-lowest text-on-surface placeholder:text-outline text-sm rounded-lg border border-outline-variant/40 focus:border-primary focus:ring-2 focus:ring-primary/10 focus:outline-none transition-all disabled:opacity-50 font-body-sm shadow-xs"
                placeholder="e.g. Khan Traders & Wholesale Co."
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="currency_code" className="block font-label-caps text-xs font-semibold uppercase text-on-surface-variant tracking-wider">
                Operating Currency
              </label>
              <div className="mt-1.5 flex items-center justify-between w-full h-11 px-3 bg-surface-container-low rounded-lg border border-surface-container-high/60 text-sm font-data-cell text-on-surface">
                <span>{currencyCode}</span>
                <span className="font-data-badge text-[10px] uppercase font-bold text-tertiary bg-tertiary-container/20 px-1.5 py-0.5 rounded">
                  P0 Standard
                </span>
              </div>
              <p className="mt-1 text-[11px] text-outline">All money stored in minor integer units</p>
            </div>

            <div>
              <label htmlFor="timezone" className="block font-label-caps text-xs font-semibold uppercase text-on-surface-variant tracking-wider">
                Operating Timezone
              </label>
              <div className="mt-1.5 flex items-center justify-between w-full h-11 px-3 bg-surface-container-low rounded-lg border border-surface-container-high/60 text-sm font-data-cell text-on-surface">
                <span>{timezone}</span>
                <span className="font-data-badge text-[10px] uppercase font-bold text-outline bg-surface-container-high px-1.5 py-0.5 rounded">
                  PKT (UTC+5)
                </span>
              </div>
              <p className="mt-1 text-[11px] text-outline">Fiscal timestamps &amp; daily closures</p>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full h-11 mt-2 bg-primary hover:bg-primary-container text-on-primary rounded-lg text-sm font-semibold shadow-sm transition-all flex items-center justify-center gap-2 active:scale-[0.99] disabled:opacity-50"
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
                Creating workspace...
              </span>
            ) : (
              <>
                <span>Create Workspace</span>
                <span>→</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
