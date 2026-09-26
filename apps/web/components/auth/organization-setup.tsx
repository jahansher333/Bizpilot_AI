"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { CreateOrganizationSchema, Organization } from "@/lib/schemas/organizations";
import { useAuth } from "@/hooks/use-auth";

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
    <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Business Workspaces
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Logged in as <span className="font-semibold text-slate-800">{user?.email || "User"}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => logout().then(() => router.push("/login"))}
          className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          Sign out
        </button>
      </div>

      {serverError && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
        >
          {serverError}
        </div>
      )}

      {validationError && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
        >
          {validationError}
        </div>
      )}

      {/* Existing Organizations List */}
      {organizations.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-slate-800">Your existing workspaces</h2>
          <div className="mt-3 space-y-2">
            {organizations.map((org) => (
              <div
                key={org.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 p-4 transition-colors hover:border-emerald-300 hover:bg-emerald-50/30"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{org.display_name}</span>
                    <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold capitalize text-emerald-800">
                      {org.role}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    Currency: {org.currency_code} • Timezone: {org.timezone}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleSelectExisting(org)}
                  className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-800"
                >
                  Enter Workspace
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create New Workspace Form */}
      <div className={organizations.length > 0 ? "mt-8 border-t border-slate-100 pt-6" : "mt-6"}>
        <h2 className="text-sm font-semibold text-slate-800">
          {organizations.length > 0 ? "Or create a new business workspace" : "Create your first business workspace"}
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Workspaces isolate your business catalog, inventory, orders, and financial data.
        </p>

        <form onSubmit={handleCreateOrg} className="mt-4 space-y-4" noValidate>
          <div>
            <label htmlFor="display_name" className="block text-sm font-medium text-slate-700">
              Business name
            </label>
            <input
              id="display_name"
              name="display_name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              disabled={isSubmitting}
              required
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 disabled:bg-slate-50"
              placeholder="e.g. Khan Traders"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="currency_code" className="block text-sm font-medium text-slate-700">
                Currency
              </label>
              <input
                id="currency_code"
                name="currency_code"
                type="text"
                value={currencyCode}
                readOnly
                disabled
                className="mt-1 block w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-600 shadow-sm"
              />
              <p className="mt-1 text-xs text-slate-400">P0 baseline currency (PKR)</p>
            </div>

            <div>
              <label htmlFor="timezone" className="block text-sm font-medium text-slate-700">
                Timezone
              </label>
              <input
                id="timezone"
                name="timezone"
                type="text"
                value={timezone}
                readOnly
                disabled
                className="mt-1 block w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-600 shadow-sm"
              />
              <p className="mt-1 text-xs text-slate-400">Operating timezone</p>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2 disabled:opacity-50"
          >
            {isSubmitting ? "Creating workspace..." : "Create Workspace"}
          </button>
        </form>
      </div>
    </div>
  );
}
