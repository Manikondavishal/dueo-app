import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";

const TABS = [
  { key: "", label: "All" },
  { key: "new", label: "New" },
  { key: "manual_review", label: "Manual review" },
  { key: "approved", label: "Approved" },
  { key: "held", label: "Held" },
  { key: "rejected", label: "Rejected" },
  { key: "activated", label: "Activated" },
];

function AdminNav({ active }) {
  const navigate = useNavigate();
  const items = [["leads", "Leads", "/admin/leads"], ["users", "Users", "/admin/users"], ["outbox", "Outbox", "/admin/outbox"]];
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}><span className="logo" /><span className="disp" style={{ fontSize: 26 }}>dueo</span><span style={{ fontSize: 13, fontWeight: 700, background: "var(--sky)", borderRadius: 999, padding: "4px 12px" }}>Admin</span></div>
      <div style={{ display: "flex", gap: 8 }}>
        {items.map(([k, l, to]) => (
          <button key={k} className={`chip ${active === k ? "chip-on" : ""}`} onClick={() => navigate(to)} data-testid={`admin-nav-${k}`}>{l}</button>
        ))}
      </div>
    </div>
  );
}

export default function AdminLeads() {
  const navigate = useNavigate();
  const [leads, setLeads] = useState(null);
  const [tab, setTab] = useState("");
  const [busy, setBusy] = useState(null);

  const load = async (status) => {
    try {
      const res = await api.adminLeads(status);
      setLeads(res.leads);
    } catch (e) {
      if (e?.response?.status === 403 || e?.response?.status === 401) { navigate("/login"); return; }
      toast.error("Couldn\u2019t load leads.");
    }
  };
  useEffect(() => { load(tab); /* eslint-disable-next-line */ }, [tab]);

  const act = async (id, action) => {
    setBusy(id + action);
    try {
      await api.adminLeadAction(id, action);
      toast.success(`Lead ${action}${action.endsWith("e") ? "d" : "ed"}.`);
      load(tab);
    } catch { toast.error("Action failed."); }
    finally { setBusy(null); }
  };

  return (
    <div style={{ minHeight: "100vh", padding: 24 }} className="m-gutter">
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <AdminNav active="leads" />
        <h1 className="disp" style={{ fontSize: 48, lineHeight: 1, marginBottom: 20 }}>Leads</h1>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20 }}>
          {TABS.map((t) => (
            <button key={t.key} className={`chip ${tab === t.key ? "chip-on" : ""}`} onClick={() => setTab(t.key)} data-testid={`leads-tab-${t.key || "all"}`}>{t.label}</button>
          ))}
        </div>
        {leads === null ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{[0, 1, 2].map((i) => <div key={i} className="skel" style={{ height: 90, borderRadius: 24 }} />)}</div>
        ) : leads.length === 0 ? (
          <div className="panel" style={{ padding: 40, textAlign: "center", color: "var(--muted)" }} data-testid="leads-empty">No leads here yet.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }} data-testid="leads-list">
            {leads.map((l) => (
              <div key={l.id} className="panel" style={{ padding: 20, display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", justifyContent: "space-between" }} data-testid={`lead-${l.id}`}>
                <div style={{ minWidth: 240 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="disp" style={{ fontSize: 22 }}>{l.business_name}</span>
                    <span className="st st-lilac" data-testid={`lead-status-${l.id}`}>{l.status}</span>
                  </div>
                  <div style={{ fontSize: 14, color: "var(--muted)" }}>{l.full_name} &middot; {l.work_email} &middot; {l.mobile}</div>
                  <div style={{ fontSize: 13, color: "var(--muted)" }}>{l.business_type} &middot; {l.city_state || "\u2014"} &middot; {l.monthly_invoice_volume || "\u2014"}{l.udyam_number ? ` \u00b7 ${l.udyam_number}` : ""}</div>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button className="pill pill-k sm" disabled={busy === l.id + "approve"} onClick={() => act(l.id, "approve")} data-testid={`lead-approve-${l.id}`}>Approve</button>
                  <button className="pill pill-w sm" onClick={() => act(l.id, "hold")} data-testid={`lead-hold-${l.id}`}>Hold</button>
                  <button className="pill pill-w sm" onClick={() => act(l.id, "reject")} data-testid={`lead-reject-${l.id}`}>Reject</button>
                  {(l.status === "approved" || l.status === "activated") && <button className="pill pill-w sm" onClick={() => act(l.id, "resend")} data-testid={`lead-resend-${l.id}`}>Resend</button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export { AdminNav };
