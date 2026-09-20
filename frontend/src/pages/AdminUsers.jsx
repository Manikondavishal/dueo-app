import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { AdminNav } from "./AdminLeads";

export default function AdminUsers() {
  const navigate = useNavigate();
  const [users, setUsers] = useState(null);

  const load = async () => {
    try { setUsers((await api.adminUsers()).users); }
    catch (e) { if ([401, 403].includes(e?.response?.status)) navigate("/login"); else toast.error("Couldn\u2019t load users."); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const toggle = async (u) => {
    try {
      if (u.status === "active") { await api.adminSuspend(u.id); toast.success("User suspended."); }
      else { await api.adminRestore(u.id); toast.success("User restored."); }
      load();
    } catch { toast.error("Action failed."); }
  };

  return (
    <div style={{ minHeight: "100vh", padding: 24 }} className="m-gutter">
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <AdminNav active="users" />
        <h1 className="disp" style={{ fontSize: 48, lineHeight: 1, marginBottom: 20 }}>Users</h1>
        {users === null ? (
          <div className="skel" style={{ height: 120, borderRadius: 24 }} />
        ) : users.length === 0 ? (
          <div className="panel" style={{ padding: 40, textAlign: "center", color: "var(--muted)" }} data-testid="users-empty">No users yet.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }} data-testid="users-list">
            {users.map((u) => (
              <div key={u.id} className="panel" style={{ padding: 20, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }} data-testid={`user-${u.id}`}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="disp" style={{ fontSize: 20 }}>{u.full_name}</span>
                    <span className="st" style={{ background: u.status === "active" ? "var(--mint)" : "var(--coral)", color: "#16130F" }} data-testid={`user-status-${u.id}`}>{u.status}</span>
                  </div>
                  <div style={{ fontSize: 14, color: "var(--muted)" }}>{u.email} &middot; {u.mobile}</div>
                </div>
                {u.status === "active"
                  ? <button className="pill pill-w sm" onClick={() => toggle(u)} data-testid={`user-suspend-${u.id}`}>Suspend</button>
                  : <button className="pill pill-k sm" onClick={() => toggle(u)} data-testid={`user-restore-${u.id}`}>Restore</button>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
