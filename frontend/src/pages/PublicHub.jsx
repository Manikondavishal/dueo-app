import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import { DueoCharacter } from "../components/DueoCharacter";

const BASE = process.env.REACT_APP_BACKEND_URL;
const pub = axios.create({ baseURL: `${BASE}/api/public/hub` });

function formatRupees(paise) {
  if (paise === null || paise === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);
}

function daysFromNow(due) {
  if (!due) return null;
  const d = new Date(due + "T00:00:00Z"); const t = new Date(); t.setUTCHours(0, 0, 0, 0);
  return Math.round((d - t) / 86400000);
}

function StatusPill({ hub }) {
  if (hub.status === "disputed") return <span data-testid="pub-status-pill" style={{ display: "inline-flex", alignItems: "center", gap: 8, height: 34, padding: "0 16px", borderRadius: 999, background: "var(--coral)", fontSize: 14, fontWeight: 700 }}><span className="dot" style={{ background: "#B94A2F" }} />Issue flagged</span>;
  const d = daysFromNow(hub.due_date);
  const p = d === null ? { t: "No due date", bg: "var(--line)", dot: "#999" }
    : d < 0 ? { t: `${Math.abs(d)} days overdue`, bg: "var(--coral)", dot: "#B94A2F" }
    : d === 0 ? { t: "Due today", bg: "var(--butter)", dot: "#B08A00" }
    : { t: `Due in ${d} days`, bg: "var(--mint)", dot: "#2F8A5A" };
  return <span data-testid="pub-status-pill" style={{ display: "inline-flex", alignItems: "center", gap: 8, height: 34, padding: "0 16px", borderRadius: 999, background: p.bg, fontSize: 14, fontWeight: 700 }}><span className="dot" style={{ background: p.dot }} />{p.t}</span>;
}

function TimelineDot({ kind }) {
  const color = { payment_due: "#B94A2F", follow_up_sent: "#3B31A8", viewed: "#B08A00", client_reply: "#2F8A5A", confirmed: "#2F8A5A", issue: "#B94A2F" }[kind] || "#999";
  return <span style={{ width: 12, height: 12, borderRadius: 999, background: color, marginTop: 6, flexShrink: 0 }} />;
}

function niceDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
}

export default function PublicHub() {
  const { token } = useParams();
  const [hub, setHub] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [issueOpen, setIssueOpen] = useState(false);
  const [payDate, setPayDate] = useState("");
  const [issueNote, setIssueNote] = useState("");
  const [saving, setSaving] = useState(false);

  async function refresh() {
    try {
      const { data } = await pub.get(`/${token}`);
      setHub(data.hub); setTimeline(data.timeline);
    } catch (e) {
      if (e?.response?.status === 404) setNotFound(true);
    } finally { setLoading(false); }
  }

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [token]);

  const firstName = useMemo(() => (hub?.client_name || "").split(" ")[0] || "there", [hub]);

  async function submitConfirm() {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(payDate)) { toast.error("Pick a valid date."); return; }
    setSaving(true);
    try { await pub.post(`/${token}/confirm`, { payment_date: payDate }); toast.success("Thanks — we've told them."); setDateOpen(false); await refresh(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Save failed."); }
    finally { setSaving(false); }
  }
  async function submitIssue() {
    if (issueNote.trim().length < 4) { toast.error("Tell us a bit more."); return; }
    setSaving(true);
    try { await pub.post(`/${token}/issue`, { note: issueNote.trim() }); toast.success("Sent. They'll follow up."); setIssueOpen(false); await refresh(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Save failed."); }
    finally { setSaving(false); }
  }

  if (loading) return <div style={{ padding: 40, fontFamily: "'Bricolage Grotesque', sans-serif" }}>Loading…</div>;
  if (notFound) return (
    <div style={{ minHeight: "100vh", background: "var(--cream)", display: "grid", placeItems: "center", padding: 24 }}>
      <div style={{ background: "#fff", borderRadius: 32, padding: 40, maxWidth: 440, display: "flex", flexDirection: "column", gap: 12 }}>
        <h1 className="disp" style={{ fontSize: 40 }}>Nothing here.</h1>
        <p style={{ color: "var(--ink-soft)" }}>This link isn't valid or has been revoked. Ask the business to send a fresh link.</p>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "var(--cream)", padding: "40px 24px" }} data-testid="public-hub">
      <div style={{ maxWidth: 720, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div className="brand-mark"><DueoCharacter shape="squircle" mood="happy" tone="lilac" size={28} /></div>
            <span className="disp" style={{ fontSize: 22 }}>dueo</span>
          </div>
          <StatusPill hub={hub} />
        </div>

        {/* Case card */}
        <div style={{ background: "#fff", borderRadius: 32, padding: 32, display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>From {hub.business_name || "your business"}</span>
            <h1 className="disp" style={{ fontSize: "clamp(38px,6vw,60px)", lineHeight: 1 }} data-testid="pub-headline">
              Hey {firstName}, <span className="serif">let's close this.</span>
            </h1>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <span className="disp num" style={{ fontSize: "clamp(48px,8vw,80px)", lineHeight: 1 }} data-testid="pub-amount">{formatRupees(hub.amount_paise)}</span>
            <span style={{ fontSize: 15, color: "var(--ink-soft)" }} data-testid="pub-invoice">Invoice {hub.invoice_number || "—"} · Due {hub.due_date || "—"}</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <button className="pill pill-k" onClick={() => setPayOpen(true)} data-testid="pub-pay" style={{ height: 60, fontSize: 17 }}>Pay now →</button>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button className="pill pill-w" onClick={() => { setDateOpen(true); setIssueOpen(false); }} data-testid="pub-confirm-open" style={{ flex: "1 1 200px", height: 52 }}>Confirm payment date</button>
              <button className="pill pill-w" onClick={() => { setIssueOpen(true); setDateOpen(false); }} data-testid="pub-issue-open" style={{ flex: "1 1 200px", height: 52 }}>There's an issue</button>
            </div>
          </div>
        </div>

        {/* Pay panel */}
        {payOpen && (
          <div style={{ background: "#fff", borderRadius: 28, padding: 24, display: "flex", flexDirection: "column", gap: 12 }} data-testid="pub-pay-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 className="disp" style={{ fontSize: 22 }}>Pay {hub.business_name}</h3>
              <button className="pill pill-w" onClick={() => setPayOpen(false)} style={{ height: 36, padding: "0 14px" }}>Close</button>
            </div>
            <div style={{ background: "var(--cream)", borderRadius: 18, padding: 18, whiteSpace: "pre-wrap", fontSize: 15, lineHeight: 1.5 }}>
              {hub.business_payment_details || "The business hasn't shared payment details on this link. Contact them directly."}
            </div>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>Dueo doesn't process the payment — you pay the business directly, then confirm below.</span>
          </div>
        )}

        {/* Confirm date */}
        {dateOpen && (
          <div style={{ background: "#fff", borderRadius: 28, padding: 24, display: "flex", flexDirection: "column", gap: 12 }} data-testid="pub-confirm-panel">
            <h3 className="disp" style={{ fontSize: 22 }}>When will payment go out?</h3>
            <input type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} data-testid="pub-confirm-date"
              style={{ height: 52, padding: "0 16px", borderRadius: 14, border: "1.5px solid var(--line)", fontSize: 16 }} />
            <div style={{ display: "flex", gap: 10 }}>
              <button className="pill pill-k" onClick={submitConfirm} disabled={saving} data-testid="pub-confirm-submit" style={{ height: 52, padding: "0 20px" }}>{saving ? "Saving…" : "Confirm date"}</button>
              <button className="pill pill-w" onClick={() => setDateOpen(false)} style={{ height: 52 }}>Cancel</button>
            </div>
          </div>
        )}

        {/* Issue */}
        {issueOpen && (
          <div style={{ background: "#fff", borderRadius: 28, padding: 24, display: "flex", flexDirection: "column", gap: 12 }} data-testid="pub-issue-panel">
            <h3 className="disp" style={{ fontSize: 22 }}>What's the issue?</h3>
            <textarea rows={4} value={issueNote} onChange={(e) => setIssueNote(e.target.value)} placeholder="Wrong amount, invoice not received, need more time — tell them here."
              data-testid="pub-issue-note"
              style={{ padding: 14, borderRadius: 14, border: "1.5px solid var(--line)", fontSize: 15, lineHeight: 1.5, fontFamily: "inherit", resize: "vertical" }} />
            <div style={{ display: "flex", gap: 10 }}>
              <button className="pill pill-k" onClick={submitIssue} disabled={saving} data-testid="pub-issue-submit" style={{ height: 52, padding: "0 20px" }}>{saving ? "Sending…" : "Send"}</button>
              <button className="pill pill-w" onClick={() => setIssueOpen(false)} style={{ height: 52 }}>Cancel</button>
            </div>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>Flagging an issue pauses reminders until they respond.</span>
          </div>
        )}

        {/* Timeline */}
        <div style={{ background: "#fff", borderRadius: 28, padding: 24, display: "flex", flexDirection: "column", gap: 8 }} data-testid="pub-timeline">
          <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)", marginBottom: 8 }}>What's happened so far</span>
          {timeline.length === 0 && <span style={{ color: "var(--ink-soft)" }}>No activity yet.</span>}
          {timeline.map((e, i) => (
            <div key={i} style={{ display: "flex", gap: 14, padding: "10px 0", borderBottom: i < timeline.length - 1 ? "1px solid var(--line-soft)" : "none" }} data-testid={`timeline-${e.kind}`}>
              <TimelineDot kind={e.kind} />
              <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
                <span style={{ fontSize: 15, fontWeight: 600 }}>{e.label}</span>
                {e.detail && <span style={{ fontSize: 14, color: "var(--ink-soft)" }}>{e.detail}</span>}
                <span className="mono" style={{ fontSize: 11, color: "var(--muted)" }}>{niceDate(e.at)}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ padding: 20, textAlign: "center", fontSize: 13, color: "var(--muted)" }}>
          Need help? Reply on WhatsApp or reach out to {hub.business_name || "the business"} directly. Sent via <strong style={{ color: "var(--ink)" }}>dueo</strong>.
        </div>
      </div>
    </div>
  );
}
