"use client";

import React, { useState } from "react";
import Link from "next/link";
import { CreateOrganizationSchema, Organization } from "@/lib/schemas/organizations";
import { useAuth } from "@/hooks/use-auth";
import { Icon } from "@/components/ui/icon";
import { Logo } from "@/components/ui/logo";
import { Money } from "@/components/ui/money";

interface OrganizationSetupProps {
  onOrgSelected?: (org: Organization) => void;
  /** Start at a given step (tests and deep links). */
  initialStep?: 1 | 2 | 3;
}

const STEP_LABELS = ["Welcome", "Business", "Defaults", "Done"] as const;

/** Design canvas "06 · Organization onboarding": a four-step setup wizard. */
export function OrganizationSetup({ onOrgSelected, initialStep = 1 }: OrganizationSetupProps) {
  const { user, createOrg } = useAuth();

  const [step, setStep] = useState<number>(initialStep);
  const [displayName, setDisplayName] = useState("");
  const [touched, setTouched] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [created, setCreated] = useState<Organization | null>(null);

  const trimmed = displayName.trim();
  const nameError = trimmed.length === 0 ? "Enter a business name to continue" : trimmed.length < 2 ? "Use at least 2 characters" : null;
  const firstName = (user?.display_name || "").trim().split(/\s+/)[0];
  const pct = Math.round(((step - 1) / 3) * 100);

  async function handleCreate() {
    setServerError(null);
    const parsed = CreateOrganizationSchema.safeParse({ display_name: displayName, currency_code: "PKR", timezone: "Asia/Karachi" });
    if (!parsed.success) {
      setStep(2);
      setTouched(true);
      return;
    }
    setIsSubmitting(true);
    try {
      const org = await createOrg(parsed.data);
      setCreated(org);
      setStep(4);
      onOrgSelected?.(org);
    } catch (err: unknown) {
      setServerError(err instanceof Error && err.message ? err.message : "Unable to create your workspace. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const preview = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Karachi",
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", display: "flex", flexDirection: "column" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "20px 32px", flexWrap: "wrap" }}>
        <Logo />
        <ol aria-label="Setup progress" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {STEP_LABELS.map((label, i) => {
            const n = i + 1;
            const done = n < step;
            const current = n === step;
            return (
              <li key={label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  aria-current={current ? "step" : undefined}
                  style={{ display: "inline-flex", alignItems: "center", gap: 8, font: "500 13px var(--font)", color: current || done ? "var(--text-primary)" : "var(--text-muted)" }}
                >
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      font: "600 11px var(--font)",
                      border: `1px solid ${current || done ? "var(--brand)" : "var(--border-strong)"}`,
                      background: done ? "var(--brand)" : current ? "var(--brand-tint)" : "var(--surface)",
                      color: done ? "var(--on-brand)" : current ? "var(--brand-text)" : "var(--text-muted)",
                      transition: "all 200ms",
                    }}
                  >
                    {done ? <Icon name="check" size="sm" style={{ strokeWidth: 2.6 }} /> : n}
                  </span>
                  <span className="hide-sm">{label}</span>
                </span>
                {n < 4 && <span className="hide-sm" style={{ width: 28, height: 1, background: "var(--border-strong)" }} />}
              </li>
            );
          })}
        </ol>
        <span className="t-caption">Step {step} of 4</span>
      </header>
      <div
        className="progress"
        style={{ borderRadius: 0, borderLeft: 0, borderRight: 0, height: 3 }}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label="Setup progress"
      >
        <span style={{ width: `${pct}%`, borderRadius: 0 }} />
      </div>

      <main style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "48px 16px" }}>
        <div className="card" style={{ width: "100%", maxWidth: 520, padding: "clamp(24px, 5vw, 40px)", boxShadow: "var(--shadow-md)" }}>
          {step === 1 && (
            <div className="reveal" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <span className="orb lg pulse" />
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <h1 className="t-h1">Welcome to BizPilot{firstName ? `, ${firstName}` : ""}</h1>
                <p className="t-body-lg secondary">Let’s set up your business workspace. It takes about a minute, and you can invite your team afterwards.</p>
              </div>
              <ul style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {["Sales, stock and payments in one place", "Roles for owners, managers and staff", "An AI copilot that only reads your own data"].map((line) => (
                  <li key={line} className="t-body" style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <Icon name="check" style={{ color: "var(--brand-text)" }} />
                    {line}
                  </li>
                ))}
              </ul>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="btn btn-primary btn-lg" onClick={() => setStep(2)}>
                  Get started
                  <Icon name="arrowRight" />
                </button>
                <Link className="btn btn-ghost btn-lg" href="/workspaces">
                  Back to workspaces
                </Link>
              </div>
            </div>
          )}

          {step === 2 && (
            <form
              className="reveal"
              style={{ display: "flex", flexDirection: "column", gap: 24 }}
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                setTouched(true);
                if (!nameError) setStep(3);
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <span className="t-over">Business information</span>
                <h1 className="t-h1">What’s your business called?</h1>
                <p className="t-body secondary">This name appears on your workspace and to your team.</p>
              </div>
              <div className="field">
                <label className="label" htmlFor="display_name">
                  Business name
                </label>
                <input
                  className={`input${touched && nameError ? " is-error" : ""}`}
                  id="display_name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  onBlur={() => setTouched(true)}
                  placeholder="e.g. Khan Traders"
                  aria-invalid={touched && !!nameError}
                  aria-describedby="ob-name-h"
                  style={{ height: 46, fontSize: 16 }}
                  autoFocus
                />
                {touched && nameError ? (
                  <span className="err" id="ob-name-h">
                    <Icon name="alert" size="sm" />
                    {nameError}
                  </span>
                ) : (
                  <span className="hint" id="ob-name-h">
                    Use the name your customers and team know.
                  </span>
                )}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <button type="button" className="btn btn-ghost" onClick={() => setStep(1)}>
                  Back
                </button>
                <button type="submit" className="btn btn-primary">
                  Continue
                </button>
              </div>
            </form>
          )}

          {step === 3 && (
            <div className="reveal" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <span className="t-over">Business defaults</span>
                <h1 className="t-h1">Currency and time zone</h1>
                <p className="t-body secondary">Set for businesses in Pakistan. All amounts, reports and AI answers use these.</p>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(200px, 100%), 1fr))", gap: 16 }}>
                <div className="field">
                  <span className="label" id="ob-cur">
                    Currency
                  </span>
                  <div className="select is-locked" aria-labelledby="ob-cur">
                    <span className="badge b-neutral square">PKR</span>
                    Pakistani Rupee
                    <Icon name="lock" className="chev" />
                  </div>
                </div>
                <div className="field">
                  <span className="label" id="ob-tz">
                    Time zone
                  </span>
                  <div className="select is-locked" aria-labelledby="ob-tz">
                    Asia/Karachi · UTC+5
                    <Icon name="lock" className="chev" />
                  </div>
                </div>
              </div>
              <div className="well" style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="t-label secondary">Preview</span>
                <span className="t-body">
                  <Money amountMinor={12500000} className="strong" /> · {preview}
                </span>
              </div>
              {serverError && (
                <div className="alert a-danger" role="alert">
                  <Icon name="alert" />
                  <div>{serverError}</div>
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <button type="button" className="btn btn-ghost" onClick={() => setStep(2)} disabled={isSubmitting}>
                  Back
                </button>
                <button type="button" className="btn btn-primary" onClick={handleCreate} disabled={isSubmitting} aria-busy={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <span className="spinner" />
                      Creating workspace…
                    </>
                  ) : (
                    "Create workspace"
                  )}
                </button>
              </div>
            </div>
          )}

          {step === 4 && created && (
            <div className="reveal" style={{ display: "flex", flexDirection: "column", gap: 24, alignItems: "flex-start" }} role="status">
              <span className="dlg-icon ok pop-in" style={{ width: 52, height: 52 }}>
                <Icon name="check" size="xl" className="check-anim" style={{ strokeWidth: 2.2 }} />
              </span>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <h1 className="t-h1">{created.display_name} is ready</h1>
                <p className="t-body-lg secondary">You’re the Owner of this workspace. Next, add your products so you can take your first order.</p>
              </div>
              <div className="well" style={{ padding: "4px 16px", width: "100%" }}>
                <div className="t-body-sm" style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
                  <span className="secondary">Workspace</span>
                  <span className="strong">{created.display_name}</span>
                </div>
                <div className="t-body-sm" style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
                  <span className="secondary">Your role</span>
                  <span className="badge b-brand square">Owner</span>
                </div>
                <div className="t-body-sm" style={{ display: "flex", justifyContent: "space-between", padding: "10px 0" }}>
                  <span className="secondary">Defaults</span>
                  <span>
                    {created.currency_code} · {created.timezone}
                  </span>
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Link className="btn btn-primary btn-lg" href={`/workspace/${created.id}`}>
                  Go to dashboard
                  <Icon name="arrowRight" />
                </Link>
                <Link className="btn btn-secondary btn-lg" href={`/workspace/${created.id}/catalog`}>
                  Add products
                </Link>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
