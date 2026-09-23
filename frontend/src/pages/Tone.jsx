import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";
import client from "../lib/api";

const TONES = [
  { key: "professional", label: "Professional", shape: "squircle", tone: "sky",   mood: "focus", body: "Clear and courteous. Best for corporate clients." },
  { key: "warm",         label: "Warm",         shape: "flower",   tone: "mint",  mood: "cheer", body: "Friendly, first-name basis. Best for long-time clients." },
  { key: "firm",         label: "Firm",         shape: "bean",     tone: "coral", mood: "focus", body: "Direct. Best when payment is well past due." },
];

const CATS = [
  { key: "initial",    label: "Initial nudge" },
  { key: "follow_up",  label: "Follow-up" },
  { key: "escalation", label: "Escalation" },
];

export default function Tone() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ctx, setCtx] = useState(null);
  const [hub, setHub] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tone, setTone] = useState("professional");
  const [cat, setCat] = useState("initial");
  const [messages, setMessages] = useState({ initial: "", follow_up: "", escalation: "" });
  const [consent, setConsent] = useState(false);
  const [approving, setApproving] = useState(false);
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
        const { contacts: cs } = await api.getHubContacts(id);
        setContacts(cs);
        if (!cs.find((c) => c.role === "poc")) {
          setErr("Add a primary contact before approving.");
        }
      } catch (e) {
        if (e?.response?.status === 404) setErr("This hub doesn't exist or isn't yours.");
        else navigate("/login");
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!hub) return;
    (async () => {
      try {
        const { messages: m } = await client.get(`/hubs/${id}/preview-messages`, { params: { tone } }).then((r) => r.data);
        setMessages(m);
      } catch (e) { setErr(e?.response?.data?.detail || "Preview failed."); }
    })();
  }, [hub, tone, id]);

  const poc = useMemo(() => contacts.find((c) => c.role === "poc"), [contacts]);

  async function approve() {
    if (!consent || approving) return;
    setApproving(true); setErr("");
    try {
      const res = await client.post(`/hubs/${id}/approve`, { tone, consent: true }).then((r) => r.data);
      if (res.send_error) {
        toast.error("Plan created, but WhatsApp send failed. Check the hub for details.");
      } else {
        toast.success(`Sent to ${poc?.name || "your primary"} — status ${res.message?.provider_status || "queued"}.`);
      }
      navigate(`/today`);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Approve failed. Try again.");
    } finally { setApproving(false); }
  }

  const orgName = ctx?.org?.display_name || "";

  if (loading) return <Shell active="today" orgName=""><Skeleton h={420} r={32} /></Shell>;
  if (err && !hub) return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <h1 className="disp" style={{ fontSize: 40 }}>Hmm.</h1>
        <p style={{ color: "var(--ink-soft)" }}>{err}</p>
        <button className="pill pill-k" onClick={() => navigate("/upload")} style={{ height: 52, width: 220 }} data-testid="tone-back">Upload an invoice</button>
      </div>
    </Shell>
  );

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 960 }} data-testid="tone-page">
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <h1 className="disp" style={{ fontSize: "clamp(40px,6vw,64px)", lineHeight: .95 }}>Pick a <span className="serif">tone.</span></h1>
          <DueoCharacter shape="cloud" mood="cheer" tone="lilac" size={80} />
        </div>
        <p style={{ fontSize: 15, color: "var(--ink-soft)" }} data-testid="tone-cadence">
          Up to 5 follow-ups over 30 days, escalating to your backup contacts if unanswered.
        </p>

        {/* Tone selector */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          {TONES.map((t) => {
            const on = tone === t.key;
            return (
              <button key={t.key} onClick={() => setTone(t.key)} aria-pressed={on}
                data-testid={`tone-${t.key}`}
                style={{
                  textAlign: "left", background: on ? "var(--ink)" : "#fff",
                  color: on ? "var(--cream)" : "var(--ink)",
                  border: "none", borderRadius: 24, padding: 20, cursor: "pointer",
                  display: "flex", flexDirection: "column", gap: 10, transition: "transform .15s, background .15s",
                  transform: on ? "translateY(-2px)" : "none",
                }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 20, fontWeight: 700 }}>{t.label}</span>
                  <DueoCharacter shape={t.shape} mood={t.mood} tone={t.tone} size={48} />
                </div>
                <span style={{ fontSize: 13, opacity: .85, lineHeight: 1.4 }}>{t.body}</span>
              </button>
            );
          })}
        </div>

        {/* Category tabs */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {CATS.map((c) => (
            <button key={c.key} onClick={() => setCat(c.key)} aria-pressed={cat === c.key}
              data-testid={`tab-${c.key}`}
              style={{
                height: 40, padding: "0 18px", borderRadius: 999, border: "1.5px solid var(--line)",
                background: cat === c.key ? "var(--ink)" : "#fff",
                color: cat === c.key ? "var(--cream)" : "var(--ink)",
                fontWeight: 600, cursor: "pointer", transition: "background .15s",
              }}>{c.label}</button>
          ))}
        </div>

        {/* Preview */}
        <div style={{ background: "#fff", borderRadius: 28, padding: 28, display: "flex", flexDirection: "column", gap: 12 }} data-testid="preview-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="dot" style={{ background: "var(--mint)" }} />
              <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase" }}>To {poc?.name || "primary contact"}</span>
            </div>
            <span className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>WhatsApp preview</span>
          </div>
          <div style={{ background: "var(--cream)", borderRadius: 18, padding: "16px 18px", whiteSpace: "pre-wrap", fontSize: 15, lineHeight: 1.55, fontFamily: "'Bricolage Grotesque', system-ui, sans-serif" }} data-testid="preview-body">
            {messages[cat] || "Preview loading…"}
          </div>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>Static template. Client name, invoice # and amount are substituted from this hub.</span>
        </div>

        {/* Consent */}
        <label style={{ display: "flex", alignItems: "flex-start", gap: 12, cursor: "pointer", padding: 18, borderRadius: 20, background: "var(--butter)" }} data-testid="consent-label">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ marginTop: 4, transform: "scale(1.2)" }} data-testid="consent-checkbox" />
          <span style={{ fontSize: 15, lineHeight: 1.5 }}>
            <strong>I'm happy with these.</strong> Let Dueo send messages to my client on my behalf using the tone I picked above.
          </span>
        </label>

        {err && <div style={{ color: "var(--coral)", fontWeight: 600 }} data-testid="tone-error">{err}</div>}

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <button className="pill pill-k" disabled={!consent || approving} onClick={approve} data-testid="approve-btn"
            style={{ height: 60, padding: "0 32px", fontSize: 17, opacity: (!consent || approving) ? .5 : 1 }}>
            {approving ? "Handing it over…" : "Hand it to Dueo →"}
          </button>
          <button className="pill pill-w" onClick={() => navigate(`/hub/${id}/contacts`)} style={{ height: 60 }} data-testid="tone-back-contacts">Back</button>
          {!consent && <span style={{ fontSize: 13, color: "var(--muted)" }}>Check the box above to enable sending.</span>}
        </div>

        <div style={{ marginTop: 4, fontSize: 13, color: "var(--muted)", background: "var(--lilac)", padding: 14, borderRadius: 16 }}>
          <strong>Sandbox note:</strong> Twilio's WhatsApp sandbox will only deliver to numbers that have joined by texting the sandbox code. Make sure the primary's WhatsApp has joined before you hand it over.
        </div>
      </div>
    </Shell>
  );
}
