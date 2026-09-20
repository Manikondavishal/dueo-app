import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { DueoCharacter } from "../components/DueoCharacter";
import { api } from "../lib/api";

export default function InviteConsume() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState("loading");
  const token = params.get("token");

  useEffect(() => {
    (async () => {
      if (!token) { setState("error"); return; }
      try {
        await api.consumeInvite(token);
        navigate("/setup");
      } catch {
        setState("error");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div className="panel" style={{ padding: 40, maxWidth: 460, width: "100%", display: "flex", flexDirection: "column", gap: 20, alignItems: "center", textAlign: "center" }} data-testid="invite-consume">
        {state === "loading" ? (
          <>
            <DueoCharacter shape="bean" mood="happy" tone="lilac" size={130} />
            <div className="disp" style={{ fontSize: 32 }}>Verifying your invite…</div>
          </>
        ) : (
          <>
            <DueoCharacter shape="burst" mood="alert" tone="coral" size={130} bob={false} />
            <div className="disp" style={{ fontSize: 30, lineHeight: 1.05 }}>This link can&rsquo;t be used.</div>
            <p style={{ fontSize: 16, color: "var(--ink-soft)" }}>Sign in with your email instead.</p>
            <button className="pill pill-k" onClick={() => navigate("/login")} data-testid="invite-consume-login">Sign in with your email</button>
          </>
        )}
      </div>
    </div>
  );
}
