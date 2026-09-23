import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";
import client from "../lib/api";

const EMPTY = { name: "", phone: "", email: "" };
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE_RE = /^\+?\d[\d\s\-]{6,}$/;

const inputStyle = {
  height: 48, padding: "0 16px", borderRadius: 14, border: "1.5px solid var(--line)",
  fontSize: 15, background: "#fff", outline: "none",
};

function contactFilled(c) {
  return !!(c.name || c.phone || c.email);
}

function contactValid(c) {
  return c.name.trim().length > 1 && PHONE_RE.test(c.phone.trim()) && EMAIL_RE.test(c.email.trim());
}

function ContactBlock({ title, subtitle, tone, character, contact, onChange, required, testidPrefix }) {
  const filled = contactFilled(contact);
  return (
    <div style={{ background: tone, borderRadius: 28, padding: 24, display: "flex", flexDirection: "column", gap: 16 }} data-testid={`${testidPrefix}-block`}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)" }}>{required ? "Required" : "Optional"}</span>
          <h3 className="disp" style={{ fontSize: 24, lineHeight: 1.05 }}>{title}</h3>
          <p style={{ fontSize: 14, color: "var(--ink-soft)", maxWidth: 460 }}>{subtitle}</p>
        </div>
        <DueoCharacter shape={character.shape} mood={character.mood} tone={character.tone} size={60} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1.4fr", gap: 12 }}>
        <input value={contact.name} onChange={(e) => onChange({ ...contact, name: e.target.value })} placeholder="Full name" style={inputStyle} data-testid={`${testidPrefix}-name`} />
        <input value={contact.phone} onChange={(e) => onChange({ ...contact, phone: e.target.value })} placeholder="+91 98765 43210" style={inputStyle} data-testid={`${testidPrefix}-phone`} />
        <input value={contact.email} onChange={(e) => onChange({ ...contact, email: e.target.value })} placeholder="name@company.com" style={inputStyle} data-testid={`${testidPrefix}-email`} />
      </div>
      {filled && !contactValid(contact) && (
        <span style={{ fontSize: 13, color: "var(--coral)", fontWeight: 600 }} data-testid={`${testidPrefix}-hint`}>All three fields, please: real name, valid phone, valid email.</span>
      )}
    </div>
  );
}

export default function Contacts() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ctx, setCtx] = useState(null);
  const [hub, setHub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [poc, setPoc] = useState(EMPTY);
  const [e1, setE1] = useState(EMPTY);
  const [e2, setE2] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
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
        const { contacts } = await api.getHubContacts(id);
        const byRole = Object.fromEntries(contacts.map((c) => [c.role, c]));
        if (byRole.poc) setPoc({ name: byRole.poc.name, phone: byRole.poc.phone, email: byRole.poc.email });
        if (byRole.escalation_1) setE1({ name: byRole.escalation_1.name, phone: byRole.escalation_1.phone, email: byRole.escalation_1.email });
        if (byRole.escalation_2) setE2({ name: byRole.escalation_2.name, phone: byRole.escalation_2.phone, email: byRole.escalation_2.email });
      } catch (e) {
        if (e?.response?.status === 404) setErr("This hub doesn't exist or isn't yours.");
        else navigate("/login");
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const primaryOk = contactValid(poc);
  const escalationsOk = (!contactFilled(e1) || contactValid(e1)) && (!contactFilled(e2) || contactValid(e2));
  const canContinue = primaryOk && escalationsOk && !saving;

  async function save() {
    if (!canContinue) return;
    setSaving(true); setErr("");
    try {
      await client.post(`/hubs/${id}/contacts`, {
        poc,
        escalation_1: contactFilled(e1) ? e1 : null,
        escalation_2: contactFilled(e2) ? e2 : null,
      });
      toast.success("Contacts saved.");
      navigate(`/hub/${id}/tone`);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Save failed. Try again.");
    } finally { setSaving(false); }
  }

  const orgName = ctx?.org?.display_name || "";
  if (loading) return <Shell active="today" orgName=""><Skeleton h={420} r={32} /></Shell>;
  if (err && !hub) return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <h1 className="disp" style={{ fontSize: 40 }}>Hmm.</h1>
        <p style={{ color: "var(--ink-soft)" }}>{err}</p>
        <button className="pill pill-k" onClick={() => navigate("/upload")} style={{ height: 52, width: 220 }} data-testid="contacts-back">Upload an invoice</button>
      </div>
    </Shell>
  );

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 960 }} data-testid="contacts-page">
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <h1 className="disp" style={{ fontSize: "clamp(40px,6vw,64px)", lineHeight: .95 }}>Who should Dueo <span className="serif">contact?</span></h1>
          <DueoCharacter shape="bean" mood="focus" tone="mint" size={80} />
        </div>
        <p style={{ fontSize: 18, lineHeight: 1.5, color: "var(--ink-soft)", maxWidth: 620 }}>
          The primary contact is who Dueo reaches first. Escalations only get pinged if the primary goes quiet.
        </p>

        <ContactBlock
          title="Primary contact" subtitle="Usually the person who owes you — someone at the client who can pay or move the payment."
          tone="var(--mint)" character={{ shape: "flower", mood: "cheer", tone: "mint" }}
          contact={poc} onChange={setPoc} required testidPrefix="poc" />
        <ContactBlock
          title="Escalation 1" subtitle="A backup at the client — accounts head, finance manager. Only used if the primary doesn't respond."
          tone="var(--butter)" character={{ shape: "cloud", mood: "focus", tone: "butter" }}
          contact={e1} onChange={setE1} required={false} testidPrefix="esc1" />
        <ContactBlock
          title="Escalation 2" subtitle="Final backup — usually the founder or CEO."
          tone="var(--lilac)" character={{ shape: "squircle", mood: "sleepy", tone: "lilac" }}
          contact={e2} onChange={setE2} required={false} testidPrefix="esc2" />

        {err && <div style={{ color: "var(--coral)", fontWeight: 600 }} data-testid="contacts-error">{err}</div>}

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <button className="pill pill-k" disabled={!canContinue} onClick={save} data-testid="contacts-continue"
            style={{ height: 60, padding: "0 32px", fontSize: 17, opacity: canContinue ? 1 : .5 }}>
            {saving ? "Saving…" : "Continue to tone →"}
          </button>
          <button className="pill pill-w" onClick={() => navigate(`/hub/${id}/proceed`)} style={{ height: 60 }} data-testid="contacts-back-proceed">Back</button>
          {!primaryOk && <span style={{ fontSize: 13, color: "var(--muted)" }}>Fill primary contact to continue.</span>}
        </div>
      </div>
    </Shell>
  );
}
