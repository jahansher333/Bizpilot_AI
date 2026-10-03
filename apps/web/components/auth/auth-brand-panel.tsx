import React from "react";
import { Icon } from "@/components/ui/icon";

const PANEL: React.CSSProperties = {
  flex: "1 1 520px",
  minHeight: "100vh",
  background: "#0C1714",
  color: "#E6EFEA",
  padding: "40px 56px",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  gap: 40,
  position: "relative",
  overflow: "hidden",
};
const GRID: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  backgroundImage:
    "linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)",
  backgroundSize: "32px 32px",
  pointerEvents: "none",
};
const TILE: React.CSSProperties = { background: "#141F1B", border: "1px solid #23302B", borderRadius: 10 };
const MUTED = "#9FB2A9";

function PanelLogo() {
  return (
    <span className="logo" style={{ color: "#E6EFEA", position: "relative" }}>
      <span className="logo-mark" style={{ background: "#2FA47A", color: "#04130D" }}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 17L17 7" />
          <path d="M9 7h8v8" />
        </svg>
      </span>
      BizPilot <span style={{ color: "#74D3AA" }}>AI</span>
    </span>
  );
}

/** Dark brand panel for sign-in (design 02 · Login). Figures are labelled as an example. */
export function LoginBrandPanel() {
  return (
    <aside className="hide-sm" style={PANEL}>
      <div style={GRID} />
      <PanelLogo />
      <div className="stagger" style={{ position: "relative", display: "flex", flexDirection: "column", gap: 12, maxWidth: 420 }} aria-hidden="true">
        <span style={{ font: "500 11px/16px var(--font)", letterSpacing: ".07em", textTransform: "uppercase", color: MUTED }}>Example workspace</span>
        <div style={{ ...TILE, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ font: "500 12.5px/18px var(--font)", color: MUTED }}>Sales · Today</span>
          <span className="money" style={{ font: "600 28px/34px var(--font)", letterSpacing: "-0.02em", color: "#F2F6F4" }}>
            <span className="cur" style={{ color: MUTED }}>PKR</span>84,500
          </span>
          <span style={{ font: "400 12.5px/18px var(--font)", color: MUTED }}>24 completed orders</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
          {[
            ["Healthy", "118", MUTED],
            ["Low stock", "9", "#E8B45E"],
            ["Out", "4", "#F18B80"],
          ].map(([label, value, color]) => (
            <div key={label} style={{ ...TILE, padding: "12px 14px" }}>
              <div style={{ font: "500 11.5px var(--font)", color }}>{label}</div>
              <div className="num" style={{ font: "600 18px/26px var(--font)" }}>{value}</div>
            </div>
          ))}
        </div>
        <div style={{ ...TILE, padding: "14px 16px", display: "flex", gap: 12, alignItems: "flex-start" }}>
          <span className="orb sm pulse" style={{ marginTop: 2 }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span style={{ font: "400 13.5px/20px var(--font)", color: "#D6E2DC" }}>
              You collected <b style={{ color: "#F2F6F4" }}>PKR 61,200</b> today across 15 payments.
            </span>
            <span style={{ display: "inline-flex", gap: 6, alignItems: "center", font: "500 11.5px var(--font)", color: "#74D3AA" }}>
              <Icon name="check" size="sm" />
              Verified from Payments · Today
            </span>
          </div>
        </div>
      </div>
      <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 8 }}>
        <p style={{ font: "600 26px/34px var(--font)", letterSpacing: "-0.02em", color: "#F2F6F4", maxWidth: 440 }}>
          Run your business. Understand it. Grow with AI.
        </p>
        <p style={{ font: "400 14px/22px var(--font)", color: MUTED, maxWidth: 420 }}>
          Orders, stock, payments and expenses in one calm workspace — with answers grounded in your own records.
        </p>
      </div>
    </aside>
  );
}

/** Dark brand panel for registration (design 03 · Register): the three setup steps. */
export function RegisterBrandPanel() {
  const steps = [
    ["Create your account", "Takes under a minute.", true],
    ["Name your business", "PKR and Asia/Karachi are set for you.", false],
    ["Record your first sale", "Add products, then open the POS.", false],
  ] as const;
  return (
    <aside className="hide-sm" style={PANEL}>
      <div style={GRID} />
      <PanelLogo />
      <ol className="stagger" style={{ position: "relative", display: "flex", flexDirection: "column", gap: 18, maxWidth: 420 }}>
        {steps.map(([title, sub, current], i) => (
          <li key={title} style={{ display: "flex", gap: 14 }}>
            <span
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                border: `1px solid ${current ? "#2FA47A" : "#2E3D37"}`,
                color: current ? "#74D3AA" : MUTED,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                font: "600 12px var(--font)",
                flex: "none",
              }}
            >
              {i + 1}
            </span>
            <div>
              <div style={{ font: "600 15px/22px var(--font)" }}>{title}</div>
              <div style={{ font: "400 13.5px/20px var(--font)", color: MUTED }}>{sub}</div>
            </div>
          </li>
        ))}
      </ol>
      <p style={{ position: "relative", font: "600 26px/34px var(--font)", letterSpacing: "-0.02em", color: "#F2F6F4", maxWidth: 440 }}>
        One workspace for everything your shop does each day.
      </p>
    </aside>
  );
}
