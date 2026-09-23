import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";

function formatRupees(paise) {
  if (paise === null || paise === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);
}

function daysFromNow(dueDate) {
  if (!dueDate) return null;
  const due = new Date(dueDate + "T00:00:00Z");
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  return Math.round((due - today) / 86400000);
}

function Kv({ k, v, testid }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }} data-testid={testid}>
      <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>{k}</span>
      <span className="disp" style={{ fontSize: 22, lineHeight: 1.15 }}>{v || "—"}</span>
    </div>
  );
}

export default function Preview() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ctx, setCtx] = useState(null);
  const [hub, setHub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.authenticated) { navigate("/login"); return; }
        if (!me.org || !me.org.settings?.setup_completed) { navigate("/setup"); return; }
        setCtx(me);
        const { hub: h } = await api.getHub(id);
        setHub(h);
      } catch (e) {
        if (e?.response?.status === 404) setErr("This hub doesn't exist or isn't yours.");
        else navigate("/login");
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const orgName = ctx?.org?.display_name || "";

  if (loading) return <Shell active="today" orgName=""><Skeleton h={420} r={32} /></Shell>;
  if (err) return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <h1 className="disp" style={{ fontSize: 40 }}>Hmm.</h1>
        <p style={{ color: "var(--ink-soft)" }}>{err}</p>
        <button className="pill pill-k" onClick={() => navigate("/upload")} style={{ height: 52, width: 220 }} data-testid="preview-back">Upload an invoice</button>
      </div>
    </Shell>
  );

  const dfn = daysFromNow(hub.due_date);
  const statusPill =
    dfn === null ? { text: "Due date not set", bg: "var(--line)", dot: "#999" } :
    dfn < 0 ? { text: `${Math.abs(dfn)} days overdue`, bg: "var(--coral)", dot: "#B94A2F" } :
    dfn === 0 ? { text: "Due today", bg: "var(--butter)", dot: "#B08A00" } :
    { text: `Due in ${dfn} days`, bg: "var(--mint)", dot: "#2F8A5A" };

  const missing = !hub.invoice_number || !hub.client_name || !hub.amount_paise || !hub.due_date || !hub.business_payment_details;

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 28, maxWidth: 960 }} data-testid="preview-page">
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <h1 className="disp" style={{ fontSize: "clamp(40px,6vw,64px)", lineHeight: .95 }}>Ready to <span className="serif">chase.</span></h1>
          <DueoCharacter shape="squircle" mood="cheer" tone="sky" size={80} />
        </div>
        <p style={{ fontSize: 18, lineHeight: 1.5, color: "var(--ink-soft)", maxWidth: 640 }}>
          This is the invoice Dueo will follow up on. Nothing goes out yet — the next step
          asks how you want to handle sending.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 24, alignItems: "start" }}>
          {/* Case summary */}
          <div style={{ background: "#fff", borderRadius: 32, padding: 32, display: "flex", flexDirection: "column", gap: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <span data-testid="preview-status-pill" style={{ display: "inline-flex", alignItems: "center", gap: 8, height: 32, padding: "0 14px", borderRadius: 999, background: statusPill.bg, fontSize: 13, fontWeight: 700 }}>
                <span className="dot" style={{ background: statusPill.dot }} />
                {statusPill.text}
              </span>
              <span className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>Draft · {hub.id.slice(0, 8)}</span>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <span className="disp num" style={{ fontSize: "clamp(56px,10vw,104px)", lineHeight: 1 }} data-testid="preview-amount">{formatRupees(hub.amount_paise)}</span>
              <span className="disp" style={{ fontSize: 22 }} data-testid="preview-client">{hub.client_name || "Client name missing"}</span>
            </div>
            <div style={{ height: 1, background: "var(--line-soft)" }} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 20 }}>
              <Kv k="Invoice #" v={hub.invoice_number} testid="preview-invoice-number" />
              <Kv k="Due" v={hub.due_date} testid="preview-due-date" />
              <Kv k="Currency" v={hub.currency} testid="preview-currency" />
              <Kv k="LLM" v={hub.llm_status} testid="preview-llm-status" />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>How you get paid</span>
              <div style={{ background: "var(--cream)", borderRadius: 20, padding: "16px 18px", whiteSpace: "pre-wrap", fontSize: 15, lineHeight: 1.5 }} data-testid="preview-payment-details">
                {hub.business_payment_details || <span style={{ color: "var(--coral)", fontWeight: 600 }}>Add your payment details on the review step.</span>}
              </div>
            </div>
          </div>

          {/* Client-side preview */}
          <div style={{ background: "var(--lilac)", borderRadius: 32, padding: 28, display: "flex", flexDirection: "column", gap: 20 }} data-testid="preview-client-card">
            <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, fontWeight: 700, color: "#3B31A8" }}>
              <span className="dot" style={{ background: "#A9A0F0" }} />
              What {hub.client_name || "your client"} will see
            </div>
            <div style={{ background: "#fff", borderRadius: 22, padding: "16px 16px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Hey {(hub.client_name || "").split(" ")[0] || "there"},</span>
              <span style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.35 }}>
                Invoice {hub.invoice_number || "—"} · {formatRupees(hub.amount_paise)} is due {hub.due_date || "soon"}.
              </span>
              {["Pay now", "Confirm payment date", "There's an issue"].map((t) => (
                <span key={t} style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 36, borderRadius: 12, border: "1.5px solid var(--line)", fontSize: 13, fontWeight: 600, color: "#3B31A8" }}>{t}</span>
              ))}
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>Preview only. Copy will vary by tone (Section 4).</div>
          </div>
        </div>

        {missing && (
          <div style={{ background: "var(--butter)", borderRadius: 20, padding: "14px 18px", fontSize: 14, fontWeight: 600 }} data-testid="preview-missing-warning">
            Some fields are still empty. Fix them in Review before continuing.
          </div>
        )}

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <button
            className="pill pill-k"
            disabled={missing}
            onClick={() => navigate(`/hub/${id}/proceed`)}
            data-testid="preview-continue"
            style={{ height: 60, padding: "0 32px", fontSize: 17, opacity: missing ? .5 : 1 }}
          >
            How should we send this? →
          </button>
          <button className="pill pill-w" onClick={() => navigate(`/hub/${id}/review`)} data-testid="preview-edit" style={{ height: 60 }}>
            Edit details
          </button>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>Nothing sends until you approve on the next step.</span>
        </div>
      </div>
    </Shell>
  );
}
