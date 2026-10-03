import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { Logo } from "@/components/ui/logo";

/** Design canvas "01 · Landing / Entry". The product preview is labelled as an example. */
export default function HomePage() {
  const metrics = [
    ["Sales", "84,500"],
    ["Collected", "61,200"],
    ["Expenses", "12,350"],
    ["Net cash flow", "48,850"],
  ];
  return (
    <div style={{ minHeight: "100vh", background: "var(--surface)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <header style={{ width: "100%", maxWidth: 1200, margin: "0 auto", padding: "22px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
        <Logo />
        <Link className="btn btn-ghost" href="/login">
          Sign in
        </Link>
      </header>

      <main style={{ width: "100%", maxWidth: 1200, margin: "0 auto", padding: "56px 24px 0", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 28 }}>
        <span className="badge b-brand page-in">
          <span className="orb sm" style={{ width: 12, height: 12 }} />
          For shops, wholesalers and distributors in Pakistan
        </span>
        <h1 className="page-in" style={{ font: "600 clamp(38px, 6vw, 64px)/1.06 var(--font)", letterSpacing: "-0.035em", maxWidth: 820, textWrap: "balance" }}>
          Run your business.
          <br />
          <span style={{ color: "var(--text-muted)" }}>Understand your business.</span>
          <br />
          Grow with AI.
        </h1>
        <p className="t-body-lg secondary page-in" style={{ maxWidth: 560 }}>
          Orders, stock, customer payments and expenses in one calm workspace — with an AI copilot that answers from your own records, in rupees.
        </p>
        <div className="page-in" style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
          <Link className="btn btn-primary btn-lg" href="/register">
            Start using BizPilot
            <Icon name="arrowRight" />
          </Link>
          <Link className="btn btn-secondary btn-lg" href="/login">
            Sign in
          </Link>
        </div>

        <figure
          className="reveal"
          aria-label="Example of a BizPilot workspace"
          style={{
            width: "100%",
            maxWidth: 1040,
            marginTop: 28,
            border: "1px solid var(--border)",
            borderBottom: 0,
            borderRadius: "14px 14px 0 0",
            background: "var(--bg)",
            boxShadow: "0 -10px 60px -20px rgba(14,110,78,.25)",
            padding: "10px 10px 0",
            textAlign: "left",
          }}
        >
          <div style={{ display: "flex", border: "1px solid var(--border)", borderBottom: 0, borderRadius: "8px 8px 0 0", overflow: "hidden", background: "var(--surface)", minHeight: 380 }} aria-hidden="true">
            <div className="hide-sm" style={{ width: 190, borderRight: "1px solid var(--border)", padding: "14px 10px", display: "flex", flexDirection: "column", gap: 4, flex: "none" }}>
              <span className="ws" style={{ padding: 6, marginBottom: 8 }}>
                <span className="ws-mark" style={{ width: 24, height: 24, fontSize: 10 }}>
                  KT
                </span>
                <span className="t-body-sm strong">Khan Traders</span>
              </span>
              {["Dashboard", "Orders", "Products", "Inventory", "Payments", "BizPilot AI"].map((item, i) => (
                <span key={item} className={`nav-item${i === 0 ? " is-active" : ""}`} style={{ height: 30, fontSize: 12.5 }}>
                  {item}
                </span>
              ))}
            </div>
            <div style={{ flex: 1, minWidth: 0, padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <div className="t-h3">Good morning, Asad</div>
                <div className="t-caption">Example workspace · Here’s what’s happening today.</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(150px, 100%), 1fr))", gap: 10 }}>
                {metrics.map(([label, value]) => (
                  <div key={label} className="card metric" style={{ padding: "12px 14px" }}>
                    <span className="metric-l" style={{ fontSize: 12 }}>
                      {label}
                    </span>
                    <span className="money" style={{ font: "600 20px/26px var(--font)" }}>
                      <span className="cur">PKR</span>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(260px, 100%), 1fr))", gap: 10 }}>
                <div className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                  <span className="t-h4">Inventory health</span>
                  <div className="dist">
                    <span className="seg-healthy" style={{ width: "90%" }} />
                    <span className="seg-low" style={{ width: "7%" }} />
                    <span className="seg-out" style={{ width: "3%" }} />
                  </div>
                  <span className="t-caption">118 healthy · 9 low · 4 out of stock</span>
                </div>
                <div className="card" style={{ padding: 14, display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span className="orb sm pulse" />
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <span className="t-body-sm">“Which products are low on stock?”</span>
                    <span className="prov verified" style={{ alignSelf: "flex-start" }}>
                      Verified from <b>Inventory</b>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </figure>
      </main>
    </div>
  );
}
