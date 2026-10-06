"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useOptionalAuth } from "@/hooks/use-auth";
import { useOrgRole } from "@/hooks/use-org-role";
import { logoutAllSessions } from "@/lib/api/auth";
import { THEME_EVENT, ThemePreference, readThemePreference, setThemePreference } from "@/lib/theme";
import { Icon } from "@/components/ui/icon";
import { initials } from "@/components/ui/logo";
import { Modal } from "@/components/ui/modal";

interface SettingsViewProps {
  orgId: string;
}

type Section = "profile" | "security" | "account";

const CURRENCY_NAME: Record<string, string> = { PKR: "Pakistani Rupee" };

/**
 * Design canvas "28–29 · Settings". The backend has no endpoints yet to rename the business or edit
 * a profile, so those fields are read-only. Business details: Owner/Manager (org:settings:read).
 */
export function SettingsView({ orgId }: SettingsViewProps) {
  const auth = useOptionalAuth();
  const role = useOrgRole(orgId);
  const canSeeBusiness = role === "owner" || role === "manager";
  const org = auth?.organizations.find((o) => o.id === orgId);
  const user = auth?.user;

  const sections: { key: Section; label: string }[] = [
    ...(canSeeBusiness ? [{ key: "profile" as const, label: "Business profile" }] : []),
    { key: "security", label: "Security" },
    { key: "account", label: "Your account" },
  ];
  const [section, setSection] = useState<Section>(canSeeBusiness ? "profile" : "security");
  const current = sections.some((s) => s.key === section) ? section : sections[0].key;

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signOutEverywhere() {
    if (!auth?.token) return;
    setSigningOut(true);
    setError(null);
    try {
      await logoutAllSessions(auth.token);
      await auth.logout();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn’t sign out your other devices.");
      setSigningOut(false);
      setConfirmOpen(false);
    }
  }

  return (
    <div className="main page-in">
      <div className="ph">
        <div className="ph-t">
          <h1 className="t-h1">Settings</h1>
          <p className="t-body secondary">{org ? `Settings for ${org.display_name}.` : "Workspace and account settings."}</p>
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 32, alignItems: "flex-start" }}>
        <nav aria-label="Settings sections" style={{ flex: "0 1 200px", display: "flex", flexDirection: "column", gap: 2 }}>
          {sections.map((s) => (
            <button key={s.key} type="button" className={`nav-item${current === s.key ? " is-active" : ""}`} aria-current={current === s.key ? "page" : undefined} onClick={() => setSection(s.key)}>
              {s.label}
            </button>
          ))}
          {role === "owner" && (
            <Link className="nav-item" href={`/workspace/${orgId}/team`}>
              Team
              <Icon name="arrowRight" size="sm" className="trail" />
            </Link>
          )}
        </nav>

        <div style={{ flex: "1 1 520px", minWidth: 0, maxWidth: 720, display: "flex", flexDirection: "column", gap: 20 }}>
          {current === "profile" && org && (
            <>
              <section className="card fade-in" aria-labelledby="bp-h">
                <div className="card-h">
                  <div>
                    <h2 className="t-h3" id="bp-h">
                      Business profile
                    </h2>
                    <span className="t-caption">Shown to your team and on order records.</span>
                  </div>
                </div>
                <div className="card-b" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                  <div className="field">
                    <label className="label" htmlFor="st-name">
                      Business name
                    </label>
                    <input className="input" id="st-name" value={org.display_name} readOnly aria-describedby="st-name-h" />
                    <span className="hint" id="st-name-h">
                      Renaming a workspace isn’t available yet.
                    </span>
                  </div>
                </div>
              </section>
              <section className="card fade-in" aria-labelledby="wd-h">
                <div className="card-h">
                  <div>
                    <h2 className="t-h3" id="wd-h">
                      Workspace defaults
                    </h2>
                    <span className="t-caption">Set at creation. Used for amounts, reports and AI answers.</span>
                  </div>
                  <span className="badge b-neutral square">
                    <Icon name="lock" />
                    Fixed
                  </span>
                </div>
                <dl style={{ margin: 0, padding: "4px 18px 8px" }}>
                  <div className="t-body" style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                    <dt className="secondary">Currency</dt>
                    <dd style={{ margin: 0 }} className="strong">
                      {org.currency_code}
                      {CURRENCY_NAME[org.currency_code] ? ` · ${CURRENCY_NAME[org.currency_code]}` : ""}
                    </dd>
                  </div>
                  <div className="t-body" style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "12px 0" }}>
                    <dt className="secondary">Time zone</dt>
                    <dd style={{ margin: 0 }} className="strong">
                      {org.timezone}
                    </dd>
                  </div>
                </dl>
              </section>
            </>
          )}

          {current === "security" && (
            <section className="card fade-in" aria-labelledby="sec-h">
              <div className="card-h">
                <h2 className="t-h3" id="sec-h">
                  Security
                </h2>
              </div>
              <div className="card-b" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                  <div>
                    <div className="t-h4">Password</div>
                    <div className="t-body-sm secondary">We’ll email you a secure link to set a new one.</div>
                  </div>
                  <Link className="btn btn-secondary btn-sm" href="/forgot-password">
                    Reset password
                  </Link>
                </div>
                <div className="divider" />
                <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                  <div>
                    <div className="t-h4">Signed-in devices</div>
                    <div className="t-body-sm secondary">Signs you out everywhere, including this browser.</div>
                  </div>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setConfirmOpen(true)}>
                    Sign out of all devices
                  </button>
                </div>
                {error && (
                  <div className="alert a-danger" role="alert">
                    <Icon name="alert" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            </section>
          )}

          {current === "account" && <AppearanceCard />}

          {current === "account" && user && (
            <section className="card fade-in" aria-labelledby="acc-h">
              <div className="card-h">
                <h2 className="t-h3" id="acc-h">
                  Your profile
                </h2>
              </div>
              <div className="card-b" style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
                <span className="av xl">{initials(user.display_name || user.email)}</span>
                <div style={{ flex: 1, minWidth: 240, display: "flex", flexDirection: "column", gap: 14 }}>
                  <div className="field">
                    <label className="label" htmlFor="ac-n">
                      Full name
                    </label>
                    <input className="input" id="ac-n" value={user.display_name} readOnly />
                  </div>
                  <div className="field">
                    <label className="label" htmlFor="ac-e">
                      Email
                    </label>
                    <input className="input" id="ac-e" value={user.email} readOnly aria-describedby="ac-e-h" />
                    <span className="hint" id="ac-e-h">
                      Editing your profile isn’t available yet. Your sign-in email can’t be changed here.
                    </span>
                  </div>
                  <div className="t-body-sm secondary">
                    Your role here: <b>{role.charAt(0).toUpperCase() + role.slice(1)}</b>
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>

      <Modal
        open={confirmOpen}
        tone="warning"
        title="Sign out of all devices?"
        description="Every device signed in to your BizPilot account — including this one — will need to sign in again."
        onClose={() => setConfirmOpen(false)}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setConfirmOpen(false)} disabled={signingOut}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void signOutEverywhere()} disabled={signingOut} aria-busy={signingOut}>
              {signingOut && <span className="spinner" />}
              Sign out everywhere
            </button>
          </>
        }
      />
    </div>
  );
}

const APPEARANCE: { value: ThemePreference; label: string; hint: string }[] = [
  { value: "system", label: "System", hint: "Match this device’s light or dark setting" },
  { value: "light", label: "Light", hint: "Always light" },
  { value: "dark", label: "Dark", hint: "Always dark — easier on the eyes at night" },
];

/** Per-device display preference (stored on this device only, like any browser setting). */
function AppearanceCard() {
  const [pref, setPref] = useState<ThemePreference>("system");
  useEffect(() => {
    setPref(readThemePreference());
    const onChange = (e: Event) => setPref((e as CustomEvent<ThemePreference>).detail);
    window.addEventListener(THEME_EVENT, onChange);
    return () => window.removeEventListener(THEME_EVENT, onChange);
  }, []);

  return (
    <section className="card fade-in" aria-labelledby="ap-h">
      <div className="card-h">
        <div>
          <h2 className="t-h3" id="ap-h">
            Appearance
          </h2>
          <span className="t-caption">Saved on this device only.</span>
        </div>
      </div>
      <div className="card-b">
        <fieldset style={{ border: 0, margin: 0, padding: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(180px, 100%), 1fr))", gap: 8 }}>
          <legend className="sr-only">Theme</legend>
          {APPEARANCE.map((o) => (
            <label
              key={o.value}
              style={{ display: "flex", gap: 10, padding: "12px 14px", minHeight: 44, border: `1px solid ${pref === o.value ? "var(--brand)" : "var(--border)"}`, borderRadius: 8, background: pref === o.value ? "var(--brand-tint)" : "var(--surface)", cursor: "pointer" }}
            >
              <input
                type="radio"
                name="appearance"
                value={o.value}
                checked={pref === o.value}
                onChange={() => {
                  setPref(o.value);
                  setThemePreference(o.value);
                }}
                style={{ marginTop: 3, accentColor: "var(--brand)" }}
              />
              <span style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span className="t-h4">{o.label}</span>
                <span className="t-body-sm secondary">{o.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
      </div>
    </section>
  );
}
