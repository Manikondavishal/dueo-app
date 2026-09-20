import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DueoCharacter } from "../components/DueoCharacter";
import { api, refId } from "../lib/api";

export default function Setup() {
  const navigate = useNavigate();
  const [ctx, setCtx] = useState(null);
  const [form, setForm] = useState({ display_name: "", mobile: "+91", udyam_number: "", consent: false });
  const [loading, setLoading] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.authenticated) { navigate("/login"); return; }
        setCtx(me);
        setForm((f) => ({ ...f, display_name: me.org?.display_name || "", mobile: me.user?.mobile || "+91" }));
      } catch { navigate("/login"); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e, skip = false) => {
    e.preventDefault();
    if (!form.display_name) { toast("Add the name clients will see."); return; }
    if (!form.consent) { toast("Please accept the terms to continue."); return; }
    setLoading(true);
    try {
      await api.setup({ display_name: form.display_name, mobile: form.mobile, udyam_number: skip ? "" : form.udyam_number, consent: form.consent, consent_version: "2026-06-01" });
      navigate("/today");
    } catch {
      toast.error("Couldn\u2019t save setup.", { description: `Reference ${refId()}` });
    } finally { setLoading(false); }
  };

  return (
    <div style={{ minHeight: "100vh", padding: 24 }} className="m-gutter">
      <a href="/" onClick={(e) => { e.preventDefault(); }} style={{ display: "flex", alignItems: "center", gap: 10, maxWidth: 720, margin: "0 auto 24px" }}><span className="logo" /><span className="disp" style={{ fontSize: 26 }}>dueo</span></a>
      <div style={{ maxWidth: 720, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", gap: 10 }} data-testid="setup-steps">
          <span className="st st-lilac">Step 1 of 3</span>
          <span className="st" style={{ background: "#EFE9DC", color: "#57524A" }}>2 &middot; Coming next</span>
          <span className="st" style={{ background: "#EFE9DC", color: "#57524A" }}>3 &middot; Coming next</span>
        </div>
        <div className="panel m-inner" style={{ padding: 40, display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <DueoCharacter shape="cloud" mood="cheer" tone="butter" size={90} />
            <div><h1 className="disp" style={{ fontSize: 40, lineHeight: 1 }}>Set up Dueo</h1><p style={{ color: "var(--muted)" }}>A few details so Dueo can chase in your name.</p></div>
          </div>
          <form onSubmit={(e) => submit(e)} style={{ display: "flex", flexDirection: "column", gap: 18 }} data-testid="setup-form">
            <div><label className="field-lbl">Name clients will see</label><input className="field" value={form.display_name} onChange={(e) => set("display_name", e.target.value)} data-testid="setup-display-name" /></div>
            <div><label className="field-lbl">Mobile (+91)</label><input className="field" value={form.mobile} onChange={(e) => set("mobile", e.target.value)} data-testid="setup-mobile" /></div>
            <div>
              <label className="field-lbl">Udyam number (optional)</label>
              <input className="field" value={form.udyam_number} onChange={(e) => set("udyam_number", e.target.value)} placeholder="UDYAM-XX-00-0000000" data-testid="setup-udyam" />
              <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 14 }}>
                <button type="button" className="pill pill-w sm" onClick={(e) => submit(e, true)} data-testid="setup-skip">Skip for now</button>
                <a href="https://udyamregistration.gov.in" target="_blank" rel="noreferrer" style={{ alignSelf: "center", fontWeight: 600, color: "#3B31A8" }} data-testid="setup-udyam-link">Don&rsquo;t have one? Create it free</a>
              </div>
            </div>
            <label style={{ display: "flex", gap: 12, alignItems: "flex-start", fontSize: 15, cursor: "pointer" }}>
              <input type="checkbox" checked={form.consent} onChange={(e) => set("consent", e.target.checked)} style={{ width: 20, height: 20, marginTop: 2 }} data-testid="setup-consent" />
              <span>I agree to the terms and to Dueo processing this data to follow up on my invoices.</span>
            </label>
            <button className="pill pill-k" type="submit" disabled={loading} data-testid="setup-submit">{loading ? "Saving\u2026" : "Finish setup \u2192"}</button>
          </form>
        </div>
      </div>
    </div>
  );
}
