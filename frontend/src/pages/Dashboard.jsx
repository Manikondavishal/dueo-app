import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";
import client from "../lib/api";

function formatRupees(paise) {
  if (paise === null || paise === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);
}

function StatusChip({ status }) {
  const styles = {
    draft:    { bg: "var(--line)",   dot: "#666" },
    active:   { bg: "var(--mint)",   dot: "#2F8A5A" },
    disputed: { bg: "var(--coral)",  dot: "#B94A2F" },
    paid:     { bg: "var(--butter)", dot: "#B08A00" },
  };
  const s = styles[status] || styles.draft;
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 26, padding: "0 10px", borderRadius: 999, background: s.bg, fontSize: 12, fontWeight: 700 }}><span className="dot" style={{ background: s.dot }} />{status || "—"}</span>;
}

function CountCard({ label, value, tone, dotColor, testid }) {
  return (
    <div style={{ background: tone, borderRadius: 24, padding: 20, display: "flex", flexDirection: "column", gap: 6 }} data-testid={testid}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>
        <span className="dot" style={{ background: dotColor }} />{label}
      </span>
      <span className="disp num" style={{ fontSize: 42, lineHeight: 1 }}>{value}</span>
    </div>
  );
}

function greet() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.authenticated) { navigate("/login"); return; }
        if (!me.org || !me.org.settings?.setup_completed) { navigate("/setup"); return; }
        const d = await client.get("/app/dashboard").then((r) => r.data);
        setData(d);
      } catch { navigate("/login"); }
      finally { setLoading(false); }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) return <Shell active="today" orgName=""><Skeleton h={420} r={32} /></Shell>;
  const firstName = (data?.user?.full_name || "").split(" ")[0] || "friend";

  return (
    <Shell active="today" orgName={data?.org?.display_name || ""}>
      <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 1080 }} data-testid="dashboard-page">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <h1 className="disp" style={{ fontSize: "clamp(36px,5vw,52px)", lineHeight: 1 }}>{greet()}, <span className="serif">{firstName}.</span></h1>
            <DueoCharacter shape="flower" mood="cheer" tone="mint" size={68} />
          </div>
          <button className="pill pill-k" onClick={() => navigate("/upload")} style={{ height: 52, padding: "0 22px" }} data-testid="dash-add">Add invoice +</button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 16 }} data-testid="counts-row">
          <CountCard label="Active" value={data.counts.active} tone="var(--mint)"   dotColor="#2F8A5A" testid="count-active" />
          <CountCard label="Promises due" value={data.counts.promises_due} tone="var(--butter)" dotColor="#B08A00" testid="count-promises" />
          <CountCard label="Needs attention" value={data.counts.needs_attention} tone="var(--coral)" dotColor="#B94A2F" testid="count-attention" />
          <CountCard label="Paid this month" value={data.counts.paid_this_month} tone="var(--lilac)" dotColor="#3B31A8" testid="count-paid" />
        </div>

        <div style={{ background: "#fff", borderRadius: 28, padding: 4, overflow: "hidden" }} data-testid="hubs-table">
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr 1fr .6fr", gap: 12, padding: "16px 20px", fontSize: 12, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)", fontWeight: 700 }}>
            <span>Client</span><span>Invoice</span><span style={{ textAlign: "right" }}>Amount</span><span>Due</span><span>Status</span>
          </div>
          {data.hubs.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--ink-soft)" }} data-testid="hubs-empty">No invoices yet. Add one to see it here.</div>
          )}
          {data.hubs.map((h) => (
            <button key={h.id} onClick={() => navigate(`/hub/${h.id}/detail`)} data-testid={`hub-row-${h.id.slice(0,8)}`}
              style={{ width: "100%", textAlign: "left", background: "transparent", border: "none", borderTop: "1px solid var(--line-soft)", padding: "16px 20px", cursor: "pointer", display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr 1fr .6fr", gap: 12, alignItems: "center" }}>
              <span style={{ fontWeight: 600 }}>{h.client_name || "—"}</span>
              <span className="mono" style={{ fontSize: 13, color: "var(--ink-soft)" }}>{h.invoice_number || "—"}</span>
              <span className="disp num" style={{ textAlign: "right" }}>{formatRupees(h.amount_paise)}</span>
              <span style={{ fontSize: 14, color: "var(--ink-soft)" }}>{h.due_date || "—"}</span>
              <span><StatusChip status={h.status} /></span>
            </button>
          ))}
        </div>
      </div>
    </Shell>
  );
}
