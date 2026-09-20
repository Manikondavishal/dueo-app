import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";

const NAV = [
  { key: "today", label: "Today", to: "/today", built: true },
  { key: "invoices", label: "Invoices", to: "#", built: false },
  { key: "clients", label: "Clients", to: "#", built: false },
  { key: "shield", label: "Shield", to: "#", built: false },
];

function Icon({ name }) {
  const common = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };
  if (name === "today") return (<svg {...common}><rect x="3" y="5" width="18" height="16" rx="4" /><path d="M8 3v4M16 3v4M3 10h18" /></svg>);
  if (name === "invoices") return (<svg {...common}><path d="M6 3h9l4 4v14H6z" /><path d="M9 12h7M9 16h5" /></svg>);
  if (name === "clients") return (<svg {...common}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c0-4 3-6 6.5-6s6.5 2 6.5 6" /><circle cx="17.5" cy="9" r="2.5" /></svg>);
  return (<svg {...common}><path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z" /></svg>);
}

function ChannelRow({ label, connected }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
      <span style={{ width: 10, height: 10, borderRadius: "50%", background: connected ? "#7FD0A3" : "#CFC8B6", flexShrink: 0 }} />
      <span style={{ flexGrow: 1 }}>{label}</span>
      <span style={{ color: "#57524A", fontSize: 13 }} data-testid={`channel-${label.toLowerCase()}-state`}>{connected ? "Connected" : "Not connected"}</span>
    </div>
  );
}

export default function Shell({ active, orgName, children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const initial = (orgName || "D").trim().charAt(0).toUpperCase();

  const doLogout = async () => {
    await api.logout();
    navigate("/login");
  };

  const railInner = (
    <>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <a href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }} style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 8px" }} data-testid="rail-logo">
          <span className="logo" /><span className="disp" style={{ fontSize: 28 }}>dueo</span>
        </a>
        <div style={{ display: "flex", alignItems: "center", gap: 10, height: 52, padding: "0 14px", borderRadius: 999, background: "#fff" }} data-testid="rail-org-name">
          <span className="disp" style={{ width: 30, height: 30, borderRadius: "50%", background: "#DDD9FA", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>{initial}</span>
          <span style={{ fontSize: 15, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{orgName || "Your business"}</span>
        </div>
        <nav aria-label="Main" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {NAV.map((n) => (
            <button
              key={n.key}
              className={`nav ${active === n.key ? "nav-on" : ""}`}
              data-testid={`nav-${n.key}`}
              aria-current={active === n.key ? "page" : undefined}
              onClick={() => (n.built ? navigate(n.to) : toast("Coming next", { description: `${n.label} is coming next.` }))}
            >
              <Icon name={n.key} />
              <span style={{ flexGrow: 1, textAlign: "left" }}>{n.label}</span>
              {!n.built && <span style={{ fontSize: 12, color: active === n.key ? "#fff" : "#57524A" }}>Coming next</span>}
            </button>
          ))}
        </nav>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ background: "#fff", borderRadius: 28, padding: 18, display: "flex", flexDirection: "column", gap: 12 }} data-testid="channels-card">
          <div style={{ fontSize: 13, fontWeight: 700 }}>Channels</div>
          <ChannelRow label="Email" connected={false} />
          <ChannelRow label="WhatsApp" connected={false} />
          <ChannelRow label="Phone" connected={false} />
        </div>
        <button className="nav" onClick={doLogout} data-testid="logout-btn" style={{ justifyContent: "flex-start" }}>Log out</button>
      </div>
    </>
  );

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--cream)" }}>
      <aside className="dueo-rail" style={{ width: 260, flexShrink: 0, padding: "28px 20px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
        {railInner}
      </aside>
      <main style={{ flexGrow: 1, minWidth: 0, padding: "36px 48px 48px 24px" }} className="dueo-main">
        <div style={{ width: "100%", maxWidth: 1100, margin: "0 auto" }}>{children}</div>
      </main>
      <style>{`
        @media (max-width: 900px){
          .dueo-rail{ position: fixed; z-index: 40; height: 100vh; transform: translateX(-100%); transition: transform .2s; background: var(--cream); box-shadow: 0 0 40px rgba(0,0,0,.15);}
          .dueo-main{ padding: 20px 12px !important; }
        }
      `}</style>
    </div>
  );
}
