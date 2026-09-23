import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";
import client from "../lib/api";

const BASE = process.env.REACT_APP_BACKEND_URL;

function OptionCard({ tone, dot, character, label, title, body, selected, disabled, onSelect, testid }) {
  return (
    <button
      onClick={onSelect}
      disabled={disabled}
      data-testid={testid}
      aria-pressed={selected}
      style={{
        textAlign: "left",
        background: selected ? tone : "#fff",
        border: `2px solid ${selected ? "var(--ink)" : "transparent"}`,
        borderRadius: 32, padding: 28, cursor: disabled ? "not-allowed" : "pointer",
        display: "flex", flexDirection: "column", gap: 18,
        transition: "background .2s, border-color .2s, transform .2s",
        transform: selected ? "translateY(-2px)" : "none",
        boxShadow: selected ? "0 30px 50px -30px rgba(22,19,15,.4)" : "0 20px 40px -30px rgba(22,19,15,.25)",
        opacity: disabled ? .5 : 1, minHeight: 320,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, height: 28, padding: "0 12px", borderRadius: 999, background: selected ? "#fff" : tone, fontSize: 12, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase" }}>
          <span className="dot" style={{ background: dot }} />{label}
        </span>
        <DueoCharacter shape={character.shape} mood={character.mood} tone={character.tone} size={70} />
      </div>
      <h3 className="disp" style={{ fontSize: 28, lineHeight: 1.05 }}>{title}</h3>
      <p style={{ fontSize: 15, lineHeight: 1.5, color: "var(--ink-soft)" }}>{body}</p>
    </button>
  );
}

export default function Proceed() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ctx, setCtx] = useState(null);
  const [hub, setHub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [choice, setChoice] = useState(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.authenticated) { navigate("/login"); return; }
        if (!me.org || !me.org.settings?.setup_completed) { navigate("/setup"); return; }
        setCtx(me);
        const { hub: h } = await api.getHub(id);
        setHub(h);
        if (h.handling_mode) setChoice(h.handling_mode);
      } catch (e) {
        if (e?.response?.status === 404) setErr("This hub doesn't exist or isn't yours.");
        else navigate("/login");
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const publicLink = useMemo(() => hub ? `${BASE}/hub/${hub.public_token}` : "", [hub]);

  async function save(mode) {
    if (saving) return;
    setSaving(true); setErr("");
    try {
      const { hub: h } = await client.post(`/hubs/${id}/handling`, { mode }).then((r) => r.data);
      setHub(h);
      setChoice(mode);
      if (mode === "dueo_handles") {
        toast.success("Dueo will handle it. Add your contacts next.");
        navigate(`/hub/${id}/contacts`);
      } else {
        toast.success("You'll share it yourself. Link ready below.");
      }
    } catch (e) {
      setErr(e?.response?.data?.detail || "Could not save. Try again.");
    } finally { setSaving(false); }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(publicLink);
      setCopied(true); toast.success("Link copied.");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setErr("Copy failed. Select and copy manually.");
    }
  }

  const orgName = ctx?.org?.display_name || "";

  if (loading) return <Shell active="today" orgName=""><Skeleton h={420} r={32} /></Shell>;
  if (err && !hub) return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <h1 className="disp" style={{ fontSize: 40 }}>Hmm.</h1>
        <p style={{ color: "var(--ink-soft)" }}>{err}</p>
        <button className="pill pill-k" onClick={() => navigate("/upload")} style={{ height: 52, width: 220 }} data-testid="proceed-back">Upload an invoice</button>
      </div>
    </Shell>
  );

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 28, maxWidth: 1040 }} data-testid="proceed-page">
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <h1 className="disp" style={{ fontSize: "clamp(40px,6vw,64px)", lineHeight: .95 }}>How should we <span className="serif">send this?</span></h1>
          <DueoCharacter shape="cloud" mood="focus" tone="lilac" size={80} />
        </div>
        <p style={{ fontSize: 18, lineHeight: 1.5, color: "var(--ink-soft)", maxWidth: 640 }}>
          Pick once. You can pause and step in anytime after this.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <OptionCard
            tone="var(--butter)" dot="#B08A00"
            character={{ shape: "flower", mood: "cheer", tone: "butter" }}
            label="Manual" title={"I'll share the link myself."}
            body="You copy Dueo's payment link and send it to the client on your own channels. Dueo tracks the case but stays quiet."
            selected={choice === "share_myself"}
            disabled={saving}
            onSelect={() => save("share_myself")}
            testid="option-share-myself"
          />
          <OptionCard
            tone="var(--mint)" dot="#2F8A5A"
            character={{ shape: "bean", mood: "happy", tone: "mint" }}
            label="Autopilot" title="Let Dueo handle it."
            body="Give Dueo the contact and tone. It follows up over WhatsApp on the schedule you approve, until they pay."
            selected={choice === "dueo_handles"}
            disabled={saving}
            onSelect={() => save("dueo_handles")}
            testid="option-dueo-handles"
          />
        </div>

        {choice === "share_myself" && (
          <div data-testid="share-link-panel" style={{ background: "#fff", borderRadius: 28, padding: 24, display: "flex", flexDirection: "column", gap: 14 }}>
            <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>Your client's payment link</span>
            <div style={{ display: "flex", alignItems: "stretch", gap: 12, flexWrap: "wrap" }}>
              <div style={{ flex: "1 1 320px", background: "var(--cream)", borderRadius: 14, padding: "14px 16px", fontFamily: "'Geist Mono', ui-monospace, monospace", fontSize: 14, wordBreak: "break-all" }} data-testid="share-link-url">{publicLink}</div>
              <button className="pill pill-k" onClick={copy} data-testid="share-copy" style={{ height: 52, padding: "0 22px" }}>{copied ? "Copied ✓" : "Copy link"}</button>
            </div>
            <p style={{ fontSize: 13, color: "var(--muted)" }}>Send it over WhatsApp, email, or wherever you talk to this client. The page shows the invoice and pay buttons.</p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 6 }}>
              <button className="pill pill-w" onClick={() => navigate("/today")} data-testid="share-done" style={{ height: 52 }}>Done for now</button>
              <button className="pill pill-w" onClick={() => save("dueo_handles")} data-testid="switch-to-dueo" style={{ height: 52 }}>Actually, let Dueo handle it →</button>
            </div>
          </div>
        )}

        {err && <div style={{ color: "var(--coral)", fontWeight: 600 }} data-testid="proceed-error">{err}</div>}
      </div>
    </Shell>
  );
}
