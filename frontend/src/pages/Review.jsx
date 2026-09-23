import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";
import client from "../lib/api";

function paiseToRupees(paise) {
  if (paise === null || paise === undefined || paise === "") return "";
  return String(paise / 100);
}

function Row({ label, hint, children }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span style={{ fontSize: 14, fontWeight: 600 }}>{label}</span>
      {children}
      {hint && <span style={{ fontSize: 12, color: "var(--muted)" }}>{hint}</span>}
    </label>
  );
}

const inputStyle = {
  height: 52, padding: "0 18px", borderRadius: 16, border: "1.5px solid var(--line)",
  fontSize: 16, background: "#fff", outline: "none",
};

export default function Review() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ctx, setCtx] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hub, setHub] = useState(null);
  const [form, setForm] = useState(null);
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
        setForm({
          invoice_number: h.invoice_number || "",
          client_name: h.client_name || "",
          amount_rupees: paiseToRupees(h.amount_paise),
          currency: h.currency || "INR",
          due_date: h.due_date || "",
          business_payment_details: h.business_payment_details || "",
        });
      } catch (e) {
        if (e?.response?.status === 404) setErr("This hub doesn't exist or isn't yours.");
        else navigate("/login");
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  function validate() {
    if (!form.invoice_number.trim()) return "Invoice number is required.";
    if (!form.client_name.trim()) return "Client name is required.";
    const amt = parseFloat(form.amount_rupees);
    if (!(amt > 0)) return "Amount must be a positive number.";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.due_date)) return "Due date must be YYYY-MM-DD.";
    if (!form.business_payment_details.trim()) return "Payment details are required so clients can pay you.";
    return "";
  }

  async function save() {
    if (saving) return;
    const v = validate();
    if (v) { setErr(v); return; }
    setErr(""); setSaving(true);
    try {
      const { hub: h } = await api.patchHub(id, {
        invoice_number: form.invoice_number.trim(),
        client_name: form.client_name.trim(),
        amount_rupees: parseFloat(form.amount_rupees),
        currency: form.currency.trim().toUpperCase(),
        due_date: form.due_date.trim(),
        business_payment_details: form.business_payment_details.trim(),
      });
      setHub(h);
      toast.success("Saved.");
      navigate(`/hub/${id}/preview`);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Save failed. Try again.");
    } finally { setSaving(false); }
  }

  const orgName = ctx?.org?.display_name || "";

  if (loading) {
    return (
      <Shell active="today" orgName="">
        <Skeleton h={360} r={32} />
      </Shell>
    );
  }
  if (err && !hub) {
    return (
      <Shell active="today" orgName={orgName}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <h1 className="disp" style={{ fontSize: 40 }}>Hmm.</h1>
          <p style={{ color: "var(--ink-soft)" }}>{err}</p>
          <button className="pill pill-k" onClick={() => navigate("/upload")} style={{ height: 52, width: 220 }} data-testid="review-back">Upload an invoice</button>
        </div>
      </Shell>
    );
  }

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 28, maxWidth: 880 }} data-testid="review-page">
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <h1 className="disp" style={{ fontSize: "clamp(40px,6vw,64px)", lineHeight: .95 }}>Review the <span className="serif">details.</span></h1>
          <DueoCharacter shape="bean" mood="focus" tone="butter" size={80} />
        </div>
        <p style={{ fontSize: 18, lineHeight: 1.5, color: "var(--ink-soft)", maxWidth: 620 }}>
          {hub?.llm_status === "ok" ? "Dueo filled these in from the invoice. Fix anything that's off, then continue." : "Enter the invoice details. Dueo needs these to follow up with your client."}
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, background: "#fff", padding: 28, borderRadius: 32 }}>
          <Row label="Invoice number">
            <input value={form.invoice_number} onChange={(e) => set("invoice_number", e.target.value)} style={inputStyle} placeholder="INV-0417" data-testid="input-invoice-number" />
          </Row>
          <Row label="Client name">
            <input value={form.client_name} onChange={(e) => set("client_name", e.target.value)} style={inputStyle} placeholder="Kestrel Logistics" data-testid="input-client-name" />
          </Row>
          <Row label="Amount (₹)" hint="Whole rupees or with decimals.">
            <input type="number" min="0" step="0.01" value={form.amount_rupees} onChange={(e) => set("amount_rupees", e.target.value)} style={inputStyle} placeholder="85000" data-testid="input-amount" />
          </Row>
          <Row label="Currency">
            <input value={form.currency} onChange={(e) => set("currency", e.target.value)} style={inputStyle} data-testid="input-currency" />
          </Row>
          <Row label="Due date" hint="YYYY-MM-DD">
            <input type="date" value={form.due_date} onChange={(e) => set("due_date", e.target.value)} style={inputStyle} data-testid="input-due-date" />
          </Row>
          <div />
          <div style={{ gridColumn: "1 / -1" }}>
            <Row label="How you get paid" hint="UPI ID, bank details, payment link — whatever your client should use.">
              <textarea rows={4} value={form.business_payment_details} onChange={(e) => set("business_payment_details", e.target.value)} style={{ ...inputStyle, height: "auto", padding: "12px 18px", fontFamily: "inherit", lineHeight: 1.4, resize: "vertical" }} placeholder={"UPI: yourname@bank\nBank: HDFC, A/C 123456, IFSC HDFC0001234"} data-testid="input-payment-details" />
            </Row>
          </div>
        </div>

        {err && <div style={{ color: "var(--coral)", fontWeight: 600 }} data-testid="review-error">{err}</div>}

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button className="pill pill-k" onClick={save} disabled={saving} style={{ height: 56, padding: "0 28px", fontSize: 16, opacity: saving ? .5 : 1 }} data-testid="review-save">
            {saving ? "Saving\u2026" : "Save and preview \u2192"}
          </button>
          <button className="pill pill-w" onClick={() => navigate("/upload")} style={{ height: 56 }} data-testid="review-back-upload">Back to upload</button>
        </div>
      </div>
    </Shell>
  );
}
