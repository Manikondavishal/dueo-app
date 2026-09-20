import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { AdminNav } from "./AdminLeads";

export default function AdminOutbox() {
  const navigate = useNavigate();
  const [emails, setEmails] = useState(null);

  useEffect(() => {
    (async () => {
      try { setEmails((await api.adminOutbox()).emails); }
      catch (e) { if ([401, 403].includes(e?.response?.status)) navigate("/login"); else toast.error("Couldn\u2019t load outbox."); }
    })();
    // eslint-disable-next-line
  }, []);

  return (
    <div style={{ minHeight: "100vh", padding: 24 }} className="m-gutter">
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <AdminNav active="outbox" />
        <h1 className="disp" style={{ fontSize: 48, lineHeight: 1, marginBottom: 6 }}>Outbox</h1>
        <p style={{ color: "var(--muted)", marginBottom: 20 }}>Every email Dueo sends is recorded here.</p>
        {emails === null ? (
          <div className="skel" style={{ height: 120, borderRadius: 24 }} />
        ) : emails.length === 0 ? (
          <div className="panel" style={{ padding: 40, textAlign: "center", color: "var(--muted)" }} data-testid="outbox-empty">No emails yet.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }} data-testid="outbox-list">
            {emails.map((e) => (
              <details key={e.id} className="panel" style={{ padding: 20 }} data-testid={`outbox-${e.id}`}>
                <summary style={{ cursor: "pointer", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                  <span className="st st-lilac">{e.kind}</span>
                  <strong>{e.subject}</strong>
                  <span style={{ color: "var(--muted)", fontSize: 14 }}>&rarr; {e.to}</span>
                  <span className="st" style={{ background: e.status === "sent" ? "var(--mint)" : e.status === "failed" ? "var(--coral)" : "var(--butter)", color: "#16130F", marginLeft: "auto" }}>{e.status}</span>
                </summary>
                <div style={{ marginTop: 14, borderTop: "1px solid var(--line-soft)", paddingTop: 14 }} dangerouslySetInnerHTML={{ __html: e.html }} />
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
