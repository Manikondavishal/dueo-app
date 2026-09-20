import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DueoCharacter } from "../components/DueoCharacter";
import { api, refId } from "../lib/api";

const BUSINESS_TYPES = [
  { v: "agency_studio", l: "Agency or studio" },
  { v: "consulting", l: "Consulting" },
  { v: "it_software", l: "IT and software" },
  { v: "other", l: "Other" },
];
const VOLUMES = ["Under 10", "10\u201350", "50\u2013200", "200+"];

export default function Invite() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: "", business_name: "", work_email: "", mobile: "+91",
    business_type: "agency_studio", city_state: "", monthly_invoice_volume: "10\u201350",
    udyam_number: "", company_website: "",
  });
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.full_name || !form.business_name || !form.work_email || form.mobile.length < 5) {
      toast("Please fill name, business, email and mobile.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.requestInvite(form);
      setDone(true);
      toast.success(res.message || "Request received.");
    } catch (err) {
      const status = err?.response?.status;
      toast.error(status === 429 ? "Too many requests. Try again later." : "Couldn\u2019t submit.", { description: `Reference ${refId()}` });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", padding: 24 }} className="m-gutter">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", maxWidth: 1120, margin: "0 auto 24px" }}>
        <a href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }} style={{ display: "flex", alignItems: "center", gap: 10 }}><span className="logo" /><span className="disp" style={{ fontSize: 26 }}>dueo</span><span style={{ marginLeft: 10, fontSize: 13, fontWeight: 700, background: "var(--lilac)", borderRadius: 999, padding: "4px 12px" }}>Early access</span></a>
        <button className="pill pill-w sm" onClick={() => navigate("/")} data-testid="invite-back">&larr; Back</button>
      </div>

      <div style={{ maxWidth: 1120, margin: "0 auto", display: "grid", gridTemplateColumns: "minmax(0,420px) 1fr", gap: 28 }} className="invite-grid">
        <div style={{ background: "var(--lilac)", borderRadius: 40, padding: 40, display: "flex", flexDirection: "column", gap: 20, minHeight: 380 }}>
          <DueoCharacter shape="bean" mood="cheer" tone="lilac" size={180} />
          <h1 className="disp" style={{ fontSize: "clamp(40px,6vw,64px)", lineHeight: .95 }}>Get the <span className="serif">invite.</span></h1>
          <p style={{ fontSize: 18, color: "var(--ink-soft)" }}>For Indian service businesses. We review every request by hand.</p>
        </div>

        {done ? (
          <div className="panel m-inner" style={{ padding: 40, display: "flex", flexDirection: "column", gap: 16, alignItems: "flex-start", justifyContent: "center" }} data-testid="invite-success">
            <DueoCharacter shape="flower" mood="focus" tone="mint" size={130} />
            <h2 className="disp" style={{ fontSize: 40, lineHeight: 1 }}>Request received.</h2>
            <p style={{ fontSize: 18, color: "var(--ink-soft)", maxWidth: 460 }}>Thanks. We review every request by hand and will email you when your invite is approved.</p>
            <button className="pill pill-k" onClick={() => navigate("/")}>Back to home</button>
          </div>
        ) : (
          <form className="panel m-inner" style={{ padding: 40, display: "flex", flexDirection: "column", gap: 18 }} onSubmit={submit} data-testid="invite-form">
            {/* Honeypot */}
            <input type="text" name="company_website" value={form.company_website} onChange={(e) => set("company_website", e.target.value)} tabIndex={-1} autoComplete="off" style={{ position: "absolute", left: "-9999px", width: 1, height: 1 }} aria-hidden="true" />
            <div className="inv-2col">
              <div><label className="field-lbl">Full name *</label><input className="field" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} data-testid="inv-full-name" /></div>
              <div><label className="field-lbl">Business name *</label><input className="field" value={form.business_name} onChange={(e) => set("business_name", e.target.value)} data-testid="inv-business-name" /></div>
            </div>
            <div className="inv-2col">
              <div><label className="field-lbl">Work email *</label><input className="field" type="email" value={form.work_email} onChange={(e) => set("work_email", e.target.value)} data-testid="inv-email" /></div>
              <div><label className="field-lbl">Mobile number *</label><input className="field" value={form.mobile} onChange={(e) => set("mobile", e.target.value)} data-testid="inv-mobile" /></div>
            </div>
            <div><label className="field-lbl">City and state</label><input className="field" value={form.city_state} onChange={(e) => set("city_state", e.target.value)} placeholder="Bengaluru, Karnataka" data-testid="inv-city" /></div>
            <div>
              <label className="field-lbl">Business type</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {BUSINESS_TYPES.map((b) => (
                  <button type="button" key={b.v} className={`chip ${form.business_type === b.v ? "chip-on" : ""}`} onClick={() => set("business_type", b.v)} data-testid={`inv-type-${b.v}`}>{b.l}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="field-lbl">Invoices per month</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {VOLUMES.map((v) => (
                  <button type="button" key={v} className={`chip ${form.monthly_invoice_volume === v ? "chip-on" : ""}`} onClick={() => set("monthly_invoice_volume", v)} data-testid={`inv-vol-${v}`}>{v}</button>
                ))}
              </div>
            </div>
            <div><label className="field-lbl">Udyam number (optional)</label><input className="field" value={form.udyam_number} onChange={(e) => set("udyam_number", e.target.value)} placeholder="UDYAM-XX-00-0000000" data-testid="inv-udyam" /></div>
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 6 }}>
              <button className="pill pill-k" type="submit" disabled={loading} data-testid="inv-submit">{loading ? "Sending\u2026" : "Get the invite today \u2192"}</button>
              <span style={{ fontSize: 14, color: "var(--muted)" }}>Name, business, email and mobile are required.</span>
            </div>
          </form>
        )}
      </div>
      <style>{`
        .inv-2col{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        @media (max-width: 767px){ .invite-grid{ grid-template-columns:1fr !important; } .inv-2col{ grid-template-columns:1fr; } }
      `}</style>
    </div>
  );
}
