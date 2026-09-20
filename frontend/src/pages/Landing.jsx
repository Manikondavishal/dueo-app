import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DueoCharacter, ShieldCharacter } from "../components/DueoCharacter";

const REPLIES = [
  { q: "\u201cI\u2019ll pay Friday.\u201d", title: "Follow up Friday.", body: "Promise saved. Dueo follows up on Friday with a payment link.", shape: "cloud", tone: "butter", mood: "focus" },
  { q: "\u201cI\u2019ll check with accounts.\u201d", title: "Follow up with accounts.", body: "Accounts is the blocker. Dueo contacts your client\u2019s accounts team instead of repeating the reminder.", shape: "bean", tone: "lilac", mood: "happy" },
  { q: "\u201cSend the invoice again.\u201d", title: "Send it again.", body: "Dueo sends the invoice document again, with the payment link.", shape: "squircle", tone: "sky", mood: "cheer" },
  { q: "\u201cThere\u2019s an issue with the work.\u201d", title: "Pause and alert you.", body: "Dueo stops all messages and puts the dispute in front of you.", shape: "burst", tone: "coral", mood: "alert" },
  { q: "\u201cWe\u2019ve already paid.\u201d", title: "Stop.", body: "Dueo stops chasing and asks for the payment reference to match it.", shape: "flower", tone: "mint", mood: "focus" },
];

const PAIN = [
  { t: "\u201cAny update?\u201d", bg: "var(--coral)", r: -4 },
  { t: "\u201cI\u2019ll check with accounts.\u201d", bg: "#fff", r: 3 },
  { t: "\u201cFollowing up again.\u201d", bg: "var(--butter)", r: -2 },
  { t: "\u201cCan you confirm a date?\u201d", bg: "var(--sky)", r: 4 },
  { t: "\u201cFriday.\u201d", bg: "var(--mint)", r: -5 },
  { t: "\u201cStill waiting for approval.\u201d", bg: "var(--lilac)", r: 2 },
];

const PEEK = [
  {
    k: "today",
    tag: "Today view",
    dot: "#A9A0F0",
    title: "One case, one next move.",
    note: "Kestrel Logistics \u00b7 \u20b985,000 \u00b7 13 days overdue",
    src: "https://customer-assets-eiarnc6j.emergentagent.net/job_invoice-follow-up-8/artifacts/l4st8qqm_Invoice%20detail%401x.png",
    alt: "Dueo Today view showing a Kestrel Logistics invoice for \u20b985,000 with Follow up with accounts as the next best action.",
  },
  {
    k: "invoices",
    tag: "Invoices",
    dot: "#7FD0A3",
    title: "Every invoice, every state.",
    note: "7 invoices \u00b7 \u20b97,48,400 in play",
    src: "https://customer-assets-eiarnc6j.emergentagent.net/job_invoice-follow-up-8/artifacts/g8nnx6vg_Invoices%401x.png",
    alt: "Dueo Invoices list showing needs-you, following-up and promised invoices grouped in one view.",
  },
  {
    k: "proof",
    tag: "Proof of promise",
    dot: "#F5D642",
    title: "A tamper-evident record.",
    note: "Chronology + hash chain, printable to PDF",
    src: "https://customer-assets-eiarnc6j.emergentagent.net/job_invoice-follow-up-8/artifacts/wwlmh2rd_Proof%20of%20promise%401x.png",
    alt: "Dueo Proof of Promise document listing chronological events for an invoice with per-event hashes.",
  },
];

const SHIELD_STEPS = [
  { name: "Case received", status: "Done", mark: "\u2713", cls: "sd-done" },
  { name: "Evidence organised", status: "Done", mark: "\u2713", cls: "sd-done" },
  { name: "MSMED review", status: "In progress", mark: "3", cls: "sd-now" },
  { name: "Human review", status: "Next", mark: "4", cls: "sd-todo" },
  { name: "Legal support", status: "", mark: "5", cls: "sd-todo" },
  { name: "Recovery", status: "", mark: "6", cls: "sd-todo" },
];

function Nav() {
  const navigate = useNavigate();
  return (
    <nav aria-label="Main" className="ld-nav">
      <a href="#top" style={{ display: "flex", alignItems: "center", gap: 10 }} data-testid="landing-logo">
        <span className="logo" /><span className="disp" style={{ fontSize: 26 }}>dueo</span>
      </a>
      <div className="ld-nav-links">
        <a href="#intel">How it works</a>
        <a href="#shield">Shield</a>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button className="pill pill-w" style={{ height: 44 }} onClick={() => navigate("/login")} data-testid="nav-login">Log in</button>
        <button className="pill pill-k" style={{ height: 44 }} onClick={() => navigate("/invite")} data-testid="nav-get-invite">Get the invite today &rarr;</button>
      </div>
    </nav>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const [sel, setSel] = useState(1);

  useEffect(() => {
    document.title = "Dueo: get paid without chasing";
    const set = (name, content, prop) => {
      let el = document.querySelector(prop ? `meta[property="${name}"]` : `meta[name="${name}"]`);
      if (!el) { el = document.createElement("meta"); el.setAttribute(prop ? "property" : "name", name); document.head.appendChild(el); }
      el.setAttribute("content", content);
    };
    const desc = "Dueo follows up on overdue B2B invoices until you get paid. Built for Indian service businesses.";
    set("description", desc);
    set("og:title", "Dueo: get paid without chasing", true);
    set("og:description", desc, true);
    set("og:type", "website", true);
  }, []);

  const r = REPLIES[sel];

  return (
    <div id="top" className="ld-root">
      {/* HERO */}
      <section className="ld-section">
        <div className="ld-hero">
          <Nav />
          <div className="ld-hero-grid">
            <div className="ld-hero-copy">
              <div className="ld-badge"><span className="dot" style={{ background: "var(--yellow)" }} />Payment follow-up, on autopilot</div>
              <h1 className="disp ld-h1">Get paid.<br />Without<br /><span className="serif ld-h1-accent">chasing</span>.</h1>
              <div className="ld-hero-sub">
                <p>Dueo follows up with your clients over WhatsApp, email and phone until you get paid.</p>
                <p>And when they still don&rsquo;t pay, Dueo helps you move from follow-up to recovery.</p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
                <button className="pill pill-k" style={{ height: 60, padding: "0 30px", fontSize: 18 }} onClick={() => navigate("/invite")} data-testid="hero-get-invite">Get the invite today &rarr;</button>
                <span style={{ fontSize: 15, color: "var(--ink-soft)", maxWidth: 160, lineHeight: 1.3 }}>Launching for Indian service businesses.</span>
              </div>
            </div>
            <div className="ld-hero-art">
              <DueoCharacter shape="cloud" mood="happy" tone="butter" size={200} className="ld-peek" style={{ "--r": "-8deg" }} />
              <div className="ld-phone">
                <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 6px 0" }}>
                  <div className="disp" style={{ width: 44, height: 44, borderRadius: "58% 42% 52% 48% / 50% 55% 45% 50%", background: "#A9A0F0", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>M</div>
                  <div style={{ display: "flex", flexDirection: "column" }}><span style={{ fontSize: 16, fontWeight: 700 }}>Meridian Studio</span><span style={{ fontSize: 13, color: "var(--muted)" }}>Payment request</span></div>
                </div>
                <div className="ld-phone-body">
                  <div className="rise" style={{ animationDelay: ".3s", alignSelf: "flex-start", maxWidth: 262, background: "#fff", borderRadius: "22px 22px 22px 6px", padding: "14px 14px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}><span style={{ fontSize: 15, fontWeight: 600 }}>Hey Nikhil</span><span style={{ fontSize: 16, fontWeight: 700 }}>Invoice #0417 &middot; &#8377;85,000 for UGC ads is sent</span><span style={{ fontSize: 14, color: "var(--muted)" }}>Due 7 Sep 2026</span></div>
                    {["Pay now", "Confirm payment date", "There\u2019s an issue"].map((t) => (
                      <span key={t} style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 38, borderRadius: 12, border: "1.5px solid var(--line)", fontSize: 14, fontWeight: 600, color: "#3B31A8" }}>{t}</span>
                    ))}
                  </div>
                  <div className="rise" style={{ animationDelay: "1.1s", alignSelf: "flex-end", maxWidth: 230, background: "var(--mint)", borderRadius: "22px 22px 6px 22px", padding: "12px 16px", fontSize: 16, lineHeight: 1.35 }}>I&rsquo;ll check with accounts.</div>
                  <div className="rise" style={{ animationDelay: "1.9s", alignSelf: "flex-start", maxWidth: 262, background: "#fff", borderRadius: "22px 22px 22px 6px", padding: "12px 16px", fontSize: 15, lineHeight: 1.4 }}>Thanks, Amit. We&rsquo;ll check in with your accounts team tomorrow at 10:00 AM.</div>
                </div>
              </div>
              <div className="wig ld-note" style={{ transform: "rotate(-4deg)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 700, color: "#3B31A8" }}><span className="dot" style={{ background: "#A9A0F0" }} />Dueo noticed</div>
                <div className="disp" style={{ fontSize: 24, lineHeight: 1.05 }}>Accounts is the blocker.</div>
                <div style={{ borderRadius: 14, background: "var(--lilac)", padding: "10px 12px", display: "flex", flexDirection: "column", gap: 2 }}><span style={{ fontSize: 14, fontWeight: 700 }}>Next: Follow up with accounts</span><span style={{ fontSize: 13, color: "var(--ink-soft)" }}>Mon 21 Sep &middot; 10:00 AM</span></div>
              </div>
            </div>
          </div>
          <div className="ld-hero-chips">
            {[["#7FD0A3", "MSMED protection"], ["#8DBDF0", "Advocates"], ["#FF9C7D", "Lawyers"], ["#F5D642", "Human recovery support"]].map(([c, t]) => (
              <span key={t} className="ld-chip"><span className="dot" style={{ background: c }} />{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* PAIN */}
      <section className="ld-section ld-pain">
        <div className="ld-pain-grid">
          <h2 className="disp ld-h2">Following up on your invoices is a <span className="serif">second job.</span></h2>
          <div className="ld-bubbles">
            {PAIN.map((p, i) => (
              <div key={i} className="wig ld-bubble" style={{ background: p.bg, transform: `rotate(${p.r}deg)` }}>{p.t}</div>
            ))}
          </div>
        </div>
        <div className="ld-pain-cta">
          <div className="disp" style={{ fontSize: "clamp(38px,7vw,78px)", lineHeight: 1 }}>You have a business to run.</div>
          <div className="disp" style={{ fontSize: "clamp(38px,7vw,78px)", lineHeight: 1 }}>Dueo does the <span className="serif marker">chasing.</span></div>
          <p style={{ maxWidth: 640, fontSize: 21, lineHeight: 1.5, color: "var(--ink-soft)", marginTop: 8 }}>Give Dueo the invoice. It follows up with the client, remembers what they said and keeps going until you get paid.</p>
        </div>
      </section>

      {/* SHIELD */}
      <section id="shield" className="ld-section">
        <div className="ld-shield">
          <div className="ld-shield-copy">
            <div className="ld-badge" style={{ fontWeight: 700 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16130F" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z" /></svg>
              Dueo Shield
            </div>
            <h2 className="disp" style={{ fontSize: "clamp(44px,8vw,96px)", lineHeight: .94 }}>Late payment isn&rsquo;t free.</h2>
            <p className="ld-p">For Micro &amp; Small Enterprises, qualifying delayed payments can attract statutory interest under the MSMED framework.</p>
            <p className="ld-p">Dueo helps track the relevant timeline, preserve the evidence and move the case toward recovery.</p>
            <div style={{ height: 1, background: "var(--ink)", opacity: .15, margin: "8px 0" }} />
            <h3 className="serif" style={{ fontSize: "clamp(32px,5vw,60px)", lineHeight: 1 }}>And you don&rsquo;t have to fight it alone.</h3>
            <p className="ld-p">Access advocates and lawyers when an unpaid invoice needs human intervention.</p>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
              <span className="disp ld-tag" style={{ background: "var(--lilac)" }}>AI to chase.</span>
              <span className="disp ld-tag" style={{ background: "var(--butter)" }}>Humans to recover.</span>
            </div>
          </div>
          <div className="ld-shield-card-wrap">
            <ShieldCharacter size={180} className="ld-shield-char" />
            <div className="ld-shield-card">
              <div className="mono" style={{ fontSize: 12, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>Shield case</div>
              <div className="disp" style={{ fontSize: 34, lineHeight: 1.05, marginBottom: 12 }}>Case timeline</div>
              {SHIELD_STEPS.map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 0", borderTop: "1px solid var(--line-soft)" }}>
                  <span className={`sd ${s.cls}`}>{s.mark}</span>
                  <span style={{ flexGrow: 1, fontSize: 18, fontWeight: 600 }}>{s.name}</span>
                  <span style={{ fontSize: 14, color: "var(--muted)" }}>{s.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* INTELLIGENCE */}
      <section id="intel" className="ld-section">
        <div className="ld-intel">
          <h2 className="disp" style={{ fontSize: "clamp(40px,7vw,88px)", lineHeight: .98, textAlign: "center" }}>Your client replies.<br /><span className="serif">Dueo knows what to do.</span></h2>
          <div className="ld-intel-grid">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {REPLIES.map((rr, i) => (
                <button key={i} className={`rep ${sel === i ? "rep-on" + i : ""}`} aria-pressed={sel === i} onClick={() => setSel(i)} data-testid={`reply-${i}`}>
                  <span>{rr.q}</span><span aria-hidden="true">&rarr;</span>
                </button>
              ))}
            </div>
            <div className={`ld-intel-panel pan${sel}`} data-testid="intel-panel">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24, width: "100%", flexWrap: "wrap" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 340 }}>
                  <span className="mono ld-move-tag">Dueo&rsquo;s move</span>
                  <h3 className="disp" style={{ fontSize: "clamp(36px,5vw,54px)", lineHeight: 1 }}>{r.title}</h3>
                  <p style={{ fontSize: 18, lineHeight: 1.45 }}>{r.body}</p>
                </div>
                <DueoCharacter shape={r.shape} mood={r.mood} tone={r.tone} size={200} />
              </div>
            </div>
          </div>
          <div className="ld-intel-foot">
            <div>
              <div className="disp" style={{ fontSize: "clamp(30px,4vw,44px)", lineHeight: 1.05 }}>Not another reminder.</div>
              <div style={{ fontSize: 20, color: "var(--ink-soft)" }}>A follow-up that understands the conversation.</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="ld-ch" style={{ background: "var(--mint)" }}>WhatsApp</span>
              <span className="ld-ch" style={{ background: "var(--sky)" }}>Email</span>
              <span className="ld-ch" style={{ background: "var(--butter)" }}>Phone</span>
              <span style={{ fontSize: 18, fontWeight: 600, marginLeft: 8 }}>One case. One timeline.</span>
            </div>
          </div>
        </div>
      </section>

      {/* PEEK INSIDE */}
      <section className="ld-section">
        <div className="ld-peek-sec">
          <div className="ld-peek-head">
            <h2 className="disp" style={{ fontSize: "clamp(40px,7vw,84px)", lineHeight: .98, maxWidth: 640 }}>Peek inside <span className="serif">what we&rsquo;re building.</span></h2>
            <p>A quick look at the Dueo app: your Today view, your invoices, and the Proof of promise document we generate for every case.</p>
          </div>
          <div className="ld-peek-grid">
            {PEEK.map((p) => (
              <figure key={p.k} className="ld-peek-card" data-testid={`peek-${p.k}`}>
                <span className="ld-peek-tag"><span className="dot" style={{ background: p.dot }} />{p.tag}</span>
                <div className="ld-peek-shot"><img src={p.src} alt={p.alt} loading="lazy" /></div>
                <figcaption className="ld-peek-label">
                  <span className="disp">{p.title}</span>
                  <span>{p.note}</span>
                </figcaption>
              </figure>
            ))}
          </div>
          <div className="ld-peek-foot">
            <DueoCharacter shape="flower" mood="cheer" tone="mint" size={60} />
            <span>Screens from our in-progress build. Details will change.</span>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="ld-section">
        <div className="ld-final">
          <DueoCharacter shape="flower" mood="focus" tone="butter" size={140} />
          <h2 className="disp" style={{ fontSize: "clamp(48px,9vw,112px)", lineHeight: .92 }}>Give it to Dueo.<br /><span className="serif">Get back to work.</span></h2>
          <button className="pill pill-k" style={{ height: 64, padding: "0 34px", fontSize: 19 }} onClick={() => navigate("/invite")} data-testid="final-get-invite">Get the invite today &rarr;</button>
          <div style={{ fontSize: 17, color: "var(--ink-soft)" }}>Early access for Indian service businesses.</div>
        </div>
      </section>

      <footer className="ld-footer">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}><span className="logo" /><span className="disp" style={{ fontSize: 24 }}>dueo</span></div>
        <div style={{ display: "flex", alignItems: "center", gap: 24, fontSize: 14, color: "var(--muted)" }}>
          <a href="/login" onClick={(e) => { e.preventDefault(); navigate("/login"); }} style={{ fontWeight: 600, color: "var(--ink)" }}>Log in</a>
          <a href="/invite" onClick={(e) => { e.preventDefault(); navigate("/invite"); }} style={{ fontWeight: 600, color: "var(--ink)" }}>Get the invite</a>
          <span>&copy; 2026 Dueo</span>
        </div>
      </footer>
    </div>
  );
}
