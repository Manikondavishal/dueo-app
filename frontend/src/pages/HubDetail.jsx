import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";
import client from "../lib/api";

function formatRupees(paise) {
  if (paise === null || paise === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);
}
function niceTs(iso) { try { return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); } catch { return iso; } }

export default function HubDetail() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ctx, setCtx] = useState(null);
  const [hub, setHub] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [thread, setThread] = useState([]);
  const [tab, setTab] = useState("conversation");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [marking, setMarking] = useState(false);
  const [markErr, setMarkErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.authenticated) { navigate("/login"); return; }
        setCtx(me);
        const { hub: h } = await api.getHub(id);
        setHub(h);
        const { contacts: cs } = await api.getHubContacts(id);
        setContacts(cs);
        const conv = await client.get(`/app/hubs/${id}/conversation`).then((r) => r.data);
        setThread(conv.thread);
      } catch (e) {
        if (e?.response?.status === 404) setErr("This hub doesn't exist or isn't yours.");
        else navigate("/login");
      } finally { setLoading(false); }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const orgName = ctx?.org?.display_name || "";
  const poc = useMemo(() => contacts.find((c) => c.role === "poc"), [contacts]);

  async function onMarkPaid() {
    if (!hub || hub.status === "paid") return;
    if (!window.confirm(`Mark invoice ${hub.invoice_number || ""} as paid? This cancels every scheduled follow-up.`)) return;
    setMarking(true); setMarkErr("");
    try {
      const { hub: updated } = await api.markHubPaid(id);
      setHub(updated);
    } catch (e) {
      setMarkErr(e?.response?.data?.detail || "Could not mark as paid.");
    } finally {
      setMarking(false);
    }
  }

  if (loading) return <Shell active="today" orgName=""><Skeleton h={420} r={32} /></Shell>;
  if (err) return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <h1 className="disp" style={{ fontSize: 40 }}>Hmm.</h1>
        <p style={{ color: "var(--ink-soft)" }}>{err}</p>
        <button className="pill pill-k" onClick={() => navigate("/dashboard")} style={{ height: 52, width: 220 }} data-testid="detail-back">Back to dashboard</button>
      </div>
    </Shell>
  );

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 960 }} data-testid="detail-page">
        <button onClick={() => navigate("/dashboard")} style={{ alignSelf: "flex-start", background: "transparent", border: "none", cursor: "pointer", color: "var(--ink-soft)", fontSize: 14 }} data-testid="detail-back-link">← Dashboard</button>

        <div style={{ background: "#fff", borderRadius: 32, padding: 32, display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>Invoice {hub.invoice_number || "—"}</span>
              <h1 className="disp" style={{ fontSize: "clamp(38px,5vw,56px)", lineHeight: 1 }} data-testid="detail-client">{hub.client_name || "Client"}</h1>
            </div>
            <DueoCharacter shape="squircle" mood="focus" tone={hub.status === "disputed" ? "coral" : "sky"} size={72} />
          </div>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <span className="disp num" style={{ fontSize: "clamp(48px,8vw,80px)", lineHeight: 1 }} data-testid="detail-amount">{formatRupees(hub.amount_paise)}</span>
            <span style={{ fontSize: 15, color: "var(--ink-soft)" }}>Due {hub.due_date || "—"} · Status <strong data-testid="detail-status">{hub.status}</strong></span>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            {hub.status !== "paid" ? (
              <button
                onClick={onMarkPaid}
                disabled={marking}
                data-testid="mark-paid-btn"
                style={{
                  height: 48, padding: "0 22px", borderRadius: 999,
                  border: "none", background: "var(--mint)", color: "var(--ink)",
                  fontWeight: 700, cursor: marking ? "wait" : "pointer",
                  opacity: marking ? 0.7 : 1,
                }}
              >{marking ? "Marking…" : "Mark as paid"}</button>
            ) : (
              <span data-testid="mark-paid-badge" style={{ height: 40, padding: "0 18px", borderRadius: 999, background: "var(--mint)", color: "var(--ink)", fontWeight: 700, display: "inline-flex", alignItems: "center" }}>Paid on {hub.paid_at?.slice(0,10) || "—"}</span>
            )}
            {markErr && <span data-testid="mark-paid-err" style={{ color: "var(--coral-ink,#7a2d2d)", fontSize: 13 }}>{markErr}</span>}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8 }} data-testid="detail-tabs">
          {[["conversation","Conversation"],["details","Details"],["activity","Activity"]].map(([k,l]) => (
            <button key={k} onClick={() => setTab(k)} aria-pressed={tab===k}
              data-testid={`tab-${k}`}
              style={{ height: 40, padding: "0 18px", borderRadius: 999, border: "1.5px solid var(--line)",
                background: tab===k ? "var(--ink)" : "#fff", color: tab===k ? "var(--cream)" : "var(--ink)",
                fontWeight: 600, cursor: "pointer" }}>{l}</button>
          ))}
        </div>

        {tab === "conversation" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }} data-testid="pane-conversation">
            {thread.length === 0 && <p style={{ color: "var(--ink-soft)" }}>No messages yet.</p>}
            {thread.map((m, i) => {
              const isDueo = m.sender === "Dueo";
              const isBiz  = m.sender === orgName && m.kind === "self_share";
              const align = isDueo || isBiz ? "flex-start" : "flex-end";
              const bg = isDueo ? "#fff" : isBiz ? "var(--butter)" : "var(--mint)";
              return (
                <div key={i} style={{ display: "flex", justifyContent: align }} data-testid={`msg-${i}`}>
                  <div style={{ maxWidth: 560, background: bg, borderRadius: 20, padding: "14px 16px", display: "flex", flexDirection: "column", gap: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>{m.sender} · {m.channel || "—"}{m.status ? ` · ${m.status}` : ""}</span>
                    <span style={{ fontSize: 15, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{m.body}</span>
                    {isDueo && m.email_to && (
                      <span data-testid={`msg-${i}-email`} style={{ fontSize: 11, color: "var(--muted)", borderTop: "1px solid rgba(0,0,0,.07)", paddingTop: 6 }}>
                        Also emailed to {m.email_to} ·{" "}
                        <b style={{ color: m.email_status === "sent" ? "var(--ink)" : m.email_status ? "#b3261e" : "var(--muted)" }}>
                          {m.email_status === "sent" ? "delivered" : m.email_status === "failed" ? "email failed" : m.status === "sent" ? "no email record" : "pending"}
                        </b>
                      </span>
                    )}
                    <span className="mono" style={{ fontSize: 11, color: "var(--muted)" }}>{niceTs(m.at)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {tab === "details" && (
          <div style={{ background: "#fff", borderRadius: 28, padding: 28, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 20 }} data-testid="pane-details">
            {[
              ["Invoice #", hub.invoice_number],
              ["Client", hub.client_name],
              ["Amount", formatRupees(hub.amount_paise)],
              ["Currency", hub.currency],
              ["Due date", hub.due_date],
              ["Status", hub.status],
              ["Handling", hub.handling_mode || "—"],
              ["Primary contact", poc ? `${poc.name} · ${poc.phone}` : "—"],
            ].map(([k, v]) => (
              <div key={k} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>{k}</span>
                <span className="disp" style={{ fontSize: 20, lineHeight: 1.1 }}>{v || "—"}</span>
              </div>
            ))}
          </div>
        )}

        {tab === "activity" && (
          <div style={{ background: "#fff", borderRadius: 28, padding: 24, display: "flex", flexDirection: "column", gap: 10 }} data-testid="pane-activity">
            <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>Timestamps</span>
            {[
              ["Created", hub.created_at],
              ["Updated", hub.updated_at],
              ["Viewed by client", hub.viewed_at],
              ["Client response", hub.client_response ? `${hub.client_response.kind} @ ${hub.client_response.submitted_at}` : null],
            ].filter(([, v]) => v).map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--line-soft)" }}>
                <span style={{ fontWeight: 600 }}>{k}</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>{v}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Shell>
  );
}
