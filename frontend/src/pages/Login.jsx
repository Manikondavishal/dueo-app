import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DueoCharacter } from "../components/DueoCharacter";
import { api, refId } from "../lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState("email");
  const [loading, setLoading] = useState(false);

  const sendCode = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.requestCode(email);
      toast(res.message);
      setStage("code");
    } catch {
      toast.error("Couldn\u2019t send code.", { description: `Reference ${refId()}` });
    } finally {
      setLoading(false);
    }
  };

  const verify = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.verifyCode(email, code);
      const me = await api.me();
      if (me.org && me.org.settings && me.org.settings.setup_completed) navigate("/today");
      else navigate("/setup");
    } catch (err) {
      const status = err?.response?.status;
      toast.error(status === 429 ? "Too many attempts. Try again later." : "That code didn\u2019t work.", { description: `Reference ${refId()}` });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }} className="m-gutter">
      <div style={{ width: "100%", maxWidth: 460 }}>
        <a href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }} style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "center", marginBottom: 28 }}><span className="logo" /><span className="disp" style={{ fontSize: 30 }}>dueo</span></a>
        <div className="panel" style={{ padding: 36, display: "flex", flexDirection: "column", gap: 20 }} data-testid="login-card">
          <div style={{ display: "flex", justifyContent: "center" }}><DueoCharacter shape="cloud" mood="happy" tone="lilac" size={120} /></div>
          {stage === "email" ? (
            <form onSubmit={sendCode} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <h1 className="disp" style={{ fontSize: 40, lineHeight: 1 }}>Log in</h1>
              <div><label className="field-lbl">Work email</label><input className="field" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="login-email" /></div>
              <button className="pill pill-k" type="submit" disabled={loading} data-testid="login-send-code">{loading ? "Sending\u2026" : "Email me a code"}</button>
            </form>
          ) : (
            <form onSubmit={verify} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <h1 className="disp" style={{ fontSize: 36, lineHeight: 1 }}>Enter your code</h1>
              <p style={{ fontSize: 15, color: "var(--muted)" }}>If this email has access, we&rsquo;ve sent a sign-in code.</p>
              <input className="field mono" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} style={{ fontSize: 24, letterSpacing: 8, textAlign: "center" }} data-testid="login-code" />
              <button className="pill pill-k" type="submit" disabled={loading} data-testid="login-verify">{loading ? "Checking\u2026" : "Verify code"}</button>
              <button type="button" className="pill pill-w sm" onClick={() => setStage("email")}>Use a different email</button>
            </form>
          )}
          <div style={{ textAlign: "center", fontSize: 14, color: "var(--muted)" }}>
            No invite yet? <a href="/invite" onClick={(e) => { e.preventDefault(); navigate("/invite"); }} style={{ fontWeight: 600, color: "var(--ink)" }} data-testid="login-get-invite">Get the invite</a>
          </div>
        </div>
      </div>
    </div>
  );
}
