import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import Shell from "../components/Shell";
import { DueoCharacter } from "../components/DueoCharacter";
import { Skeleton } from "../components/Skeleton";
import { api } from "../lib/api";
import client from "../lib/api";

const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf";
const MAX_BYTES = 15 * 1024 * 1024;

function formatRupees(paise) {
  if (paise === null || paise === undefined) return "\u2014";
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(rupees);
}

function Field({ label, value, testid }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }} data-testid={testid}>
      <span className="mono" style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--muted)" }}>{label}</span>
      <span className="disp" style={{ fontSize: 24, lineHeight: 1.1 }}>{value || "\u2014"}</span>
    </div>
  );
}

export default function Upload() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [ctx, setCtx] = useState(null);
  const [checking, setChecking] = useState(true);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState("idle"); // idle | uploading | extracting | done | failed
  const [hub, setHub] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.authenticated) { navigate("/login"); return; }
        if (!me.org || !me.org.settings?.setup_completed) { navigate("/setup"); return; }
        setCtx(me);
      } catch { navigate("/login"); }
      finally { setChecking(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pick(f) {
    setErr("");
    if (!f) return;
    if (!ACCEPT.split(",").includes(f.type)) { setErr("Only PDF, PNG, JPEG or WEBP."); return; }
    if (f.size > MAX_BYTES) { setErr("File is over 15 MB."); return; }
    setFile(f);
  }

  async function submit() {
    if (!file || phase === "uploading" || phase === "extracting") return;
    setErr("");
    setPhase("uploading");
    try {
      const form = new FormData();
      form.append("file", file);
      const up = await client.post("/uploads", form, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
      setPhase("extracting");
      const res = await client.post("/hubs/from-upload", { upload_id: up.id }).then((r) => r.data);
      setHub(res.hub);
      setPhase("done");
      if (res.llm_status === "failed") toast.warning("We couldn't auto-fill. Review the details on the next step.");
      else if (res.llm_status === "skipped") toast.info("PDF received. Enter the details on the next step.");
      else toast.success("Details extracted.");
    } catch (e) {
      setPhase("failed");
      setErr(e?.response?.data?.detail || "Upload failed. Try again.");
    }
  }

  const orgName = ctx?.org?.display_name || "";

  if (checking) {
    return (
      <Shell active="today" orgName="">
        <Skeleton h={220} r={32} />
      </Shell>
    );
  }

  return (
    <Shell active="today" orgName={orgName}>
      <div style={{ display: "flex", flexDirection: "column", gap: 28, maxWidth: 880 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <h1 className="disp" style={{ fontSize: "clamp(40px,6vw,64px)", lineHeight: .95 }}>Add an <span className="serif">invoice.</span></h1>
          <DueoCharacter shape="cloud" mood="focus" tone="lilac" size={80} />
        </div>
        <p style={{ fontSize: 18, lineHeight: 1.5, color: "var(--ink-soft)", maxWidth: 620 }}>
          Drop the invoice you sent to your client. Dueo reads it, then you'll review
          the details before we contact anyone.
        </p>

        {phase !== "done" && (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]); }}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            data-testid="upload-dropzone"
            style={{
              borderRadius: 32,
              border: `2px dashed ${dragging ? "var(--ink)" : "rgba(22,19,15,.2)"}`,
              background: dragging ? "var(--butter)" : "#fff",
              padding: "56px 32px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 16,
              cursor: "pointer",
              transition: "border-color .2s, background .2s",
            }}
          >
            <DueoCharacter shape="flower" mood="cheer" tone="mint" size={80} />
            <div className="disp" style={{ fontSize: 28, textAlign: "center" }}>{file ? file.name : "Drop a PDF or image here."}</div>
            <div style={{ fontSize: 14, color: "var(--muted)" }}>{file ? `${(file.size / 1024).toFixed(0)} KB` : "or click to choose. PDF / PNG / JPEG / WEBP up to 15 MB."}</div>
            <input ref={inputRef} type="file" accept={ACCEPT} onChange={(e) => pick(e.target.files?.[0])} style={{ display: "none" }} data-testid="upload-input" />
          </div>
        )}

        {err && <div style={{ color: "var(--coral)", fontWeight: 600 }} data-testid="upload-error">{err}</div>}

        {phase !== "done" && (
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <button
              className="pill pill-k"
              disabled={!file || phase === "uploading" || phase === "extracting"}
              onClick={submit}
              data-testid="upload-submit"
              style={{ height: 56, padding: "0 28px", fontSize: 16, opacity: (!file || phase === "uploading" || phase === "extracting") ? .5 : 1 }}
            >
              {phase === "uploading" ? "Uploading\u2026" : phase === "extracting" ? "Reading the invoice\u2026" : "Read this invoice \u2192"}
            </button>
            <button className="pill pill-w" onClick={() => navigate("/today")} data-testid="upload-cancel" style={{ height: 56 }}>Cancel</button>
          </div>
        )}

        {phase === "done" && hub && (
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }} data-testid="upload-result">
            <div style={{ borderRadius: 36, background: "var(--lilac)", padding: 32, display: "flex", flexDirection: "column", gap: 24 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span className="dot" style={{ background: "var(--mint)" }} />
                  <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase" }}>Extracted</span>
                </div>
                <span className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>llm: {hub.llm_status}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 24 }}>
                <Field label="Invoice #" value={hub.invoice_number} testid="field-invoice-number" />
                <Field label="Client" value={hub.client_name} testid="field-client-name" />
                <Field label="Amount" value={formatRupees(hub.amount_paise)} testid="field-amount" />
                <Field label="Due date" value={hub.due_date} testid="field-due-date" />
              </div>
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button
                className="pill pill-k"
                onClick={() => navigate(`/hub/${hub.id}/review`)}
                data-testid="continue-to-review"
                style={{ height: 56, padding: "0 28px", fontSize: 16 }}
              >
                Review the details \u2192
              </button>
              <button
                className="pill pill-w"
                onClick={() => { setFile(null); setHub(null); setPhase("idle"); }}
                data-testid="upload-another"
                style={{ height: 56 }}
              >
                Upload another
              </button>
            </div>
            <p style={{ fontSize: 14, color: "var(--muted)" }}>Draft hub id: <span className="mono">{hub.id}</span></p>
          </div>
        )}
      </div>
    </Shell>
  );
}
