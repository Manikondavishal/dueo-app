import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Shell from "../components/Shell";
import { EmptyState } from "../components/States";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";

function todayLabel() {
  return new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: "Asia/Kolkata" }).format(new Date());
}

export default function Today() {
  const navigate = useNavigate();
  const [ctx, setCtx] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.authenticated) { navigate("/login"); return; }
        if (!me.org || !me.org.settings?.setup_completed) { navigate("/setup"); return; }
        setCtx(me);
      } catch { navigate("/login"); }
      finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <Shell active="today" orgName="">
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <Skeleton w={220} h={60} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 20 }}>
            <Skeleton h={164} r={32} /><Skeleton h={164} r={32} /><Skeleton h={164} r={32} />
          </div>
          <Skeleton h={200} r={36} />
        </div>
      </Shell>
    );
  }

  const orgName = ctx?.org?.display_name || "Your business";

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <h1 className="disp" style={{ fontSize: "clamp(48px,8vw,72px)", lineHeight: .9 }}>Today</h1>
            <span style={{ display: "inline-flex", alignItems: "center", height: 36, padding: "0 16px", borderRadius: 999, background: "#fff", fontSize: 15, fontWeight: 600, marginTop: 12 }} data-testid="today-date">{todayLabel()}</span>
          </div>
          <button className="pill pill-k" onClick={() => navigate("/upload")} data-testid="add-invoice">Add invoice +</button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 20 }}>
          {[
            { label: "Outstanding", value: "\u20B90", sub: "0 invoices", bg: "var(--lilac)" },
            { label: "Needs you", value: "0", sub: "\u20B90", bg: "var(--coral)" },
            { label: "Promises due today", value: "0", sub: "\u20B90", bg: "var(--butter)" },
          ].map((c) => (
            <div key={c.label} style={{ height: 164, borderRadius: 32, background: c.bg, padding: 24, display: "flex", flexDirection: "column", justifyContent: "space-between" }} data-testid={`stat-${c.label.split(" ")[0].toLowerCase()}`}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{c.label}</div>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                <span className="disp num" style={{ fontSize: 52, lineHeight: 1 }}>{c.value}</span>
                <span className="num" style={{ fontSize: 14, color: "var(--ink-soft)" }}>{c.sub}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="panel" style={{ padding: 8 }}>
          <EmptyState line="Nothing for you to do." testid="today-empty" />
        </div>
      </div>
    </Shell>
  );
}
