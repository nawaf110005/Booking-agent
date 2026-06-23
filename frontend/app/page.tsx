"use client";

import { useEffect, useState } from "react";
import Chat from "@/components/Chat";
import { health } from "@/lib/api";

const STEPS = [
  { n: 1, t: "Tell me", d: "“4 Gold for Coldplay in Riyadh.” Arabic or English." },
  { n: 2, t: "I quote it", d: "Member discount + 15% VAT, itemised to the halala." },
  { n: 3, t: "Pick seats", d: "Live seat map; I hold them for 10 minutes." },
  { n: 4, t: "Confirm & go", d: "You approve the total, pay, and get a QR ticket." },
];

const FEATURES = [
  { i: "💬", t: "One chat, zero forms", d: "The whole funnel — find, price, seat, pay — collapses into a single conversation." },
  { i: "🪪", t: "Discount, automatically", d: "Your tier is read from your email and applied every time — never buried five clicks deep." },
  { i: "🪑", t: "Atomic 10-min holds", d: "Seats are held all-or-nothing with a visible timer. No two people hold the same seat." },
  { i: "✅", t: "Confirm before you pay", d: "The agent shows the exact total and waits for your yes. It never charges on its own." },
  { i: "🎫", t: "Signed QR ticket", d: "Tamper-evident, HMAC-signed, delivered straight to your inbox." },
  { i: "🧠", t: "Learns your taste", d: "It asks what you like and remembers it — showing the right shows, not the whole catalog." },
];

const STATS = [
  { to: 80, suf: "%", mid: false, d: "of ticketing carts are abandoned at checkout — the problem we remove" },
  { to: 1, suf: "", mid: true, d: "conversation from “I want a ticket” to a QR ticket" },
  { to: 0, suf: "", mid: false, d: "forms to fill out — it’s all chat, Arabic or English" },
  { to: 15, suf: "%", mid: false, d: "member discount auto-applied — read from your email" },
  { to: 10, suf: " min", mid: true, d: "atomic seat hold with a live timer — nobody double-books" },
  { to: 100, suf: "%", mid: false, d: "confirm-before-pay — the agent never charges on its own" },
];

const DEMO = [
  { who: "user", t: "4 Gold tickets for Coldplay in Riyadh, nawaf@example.com" },
  { who: "agent", t: "Nawaf, you’re Platinum — 15% off. Gold ×4 = 3,128.00 SAR incl. VAT. Pick 4 seats →" },
  { who: "user", t: "G3, G4, G5, G6" },
  { who: "agent", t: "Held for 10:00 ⏱️ Confirm to pay and I’ll send your QR ticket." },
  { who: "user", t: "confirm" },
  { who: "agent", t: "Done ✅ Your ticket is on its way to your inbox 🎫" },
];

const VIBES = ["Concerts", "Sports", "Comedy", "Theatre", "Festivals", "Conferences"];

export default function Home() {
  const [aiActive, setAiActive] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  useEffect(() => {
    health().then((h) => setAiActive(h.llm_configured)).catch(() => setAiActive(false));
  }, []);

  // Scroll-reveal, floating particles, count-up numbers, auto-typing demo chat.
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

    const reveals = Array.from(document.querySelectorAll<HTMLElement>(".reveal"));
    let io: IntersectionObserver | undefined;
    if ("IntersectionObserver" in window && !reduce) {
      io = new IntersectionObserver(
        (es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io?.unobserve(e.target); } }),
        { threshold: 0.15 },
      );
      reveals.forEach((el) => io?.observe(el));
    } else {
      reveals.forEach((el) => el.classList.add("in"));
    }

    const pc = document.getElementById("particles");
    if (pc && !reduce && pc.childElementCount === 0) {
      const glyphs = ["🎫", "✦", "🎟️", "★", "♪"];
      for (let i = 0; i < 16; i++) {
        const s = document.createElement("span");
        s.className = "particle";
        s.textContent = glyphs[i % glyphs.length];
        s.style.left = `${Math.random() * 100}%`;
        s.style.animationDuration = `${10 + Math.random() * 12}s`;
        s.style.animationDelay = `${Math.random() * 10}s`;
        s.style.fontSize = `${0.8 + Math.random() * 1.4}rem`;
        pc.appendChild(s);
      }
    }

    const countUp = (el: HTMLElement) => {
      const to = parseFloat(el.dataset.to ?? "0");
      if (reduce) { el.textContent = String(to); return; }
      let start: number | null = null;
      const step = (ts: number) => {
        if (start === null) start = ts;
        const p = Math.min((ts - start) / 1400, 1);
        el.textContent = String(Math.round(p * to));
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    let io2: IntersectionObserver | undefined;
    const counts = Array.from(document.querySelectorAll<HTMLElement>(".count"));
    if ("IntersectionObserver" in window) {
      io2 = new IntersectionObserver(
        (es) => es.forEach((e) => { if (e.isIntersecting) { countUp(e.target as HTMLElement); io2?.unobserve(e.target); } }),
        { threshold: 0.6 },
      );
      counts.forEach((c) => io2?.observe(c));
    } else {
      counts.forEach(countUp);
    }

    const chat = document.getElementById("demo-chat");
    let io3: IntersectionObserver | undefined;
    if (chat) {
      const bubbles = Array.from(chat.querySelectorAll<HTMLElement>(".bubble"));
      const typing = document.getElementById("demo-typing");
      let played = false;
      const play = () => {
        if (played) return;
        played = true;
        if (reduce) { bubbles.forEach((b) => b.classList.add("show")); return; }
        let i = 0;
        const next = () => {
          if (i >= bubbles.length) { typing?.classList.remove("show"); return; }
          const b = bubbles[i];
          if (b.classList.contains("agent") && typing) {
            typing.classList.add("show");
            setTimeout(() => { typing.classList.remove("show"); b.classList.add("show"); i += 1; setTimeout(next, 700); }, 800);
          } else {
            b.classList.add("show"); i += 1; setTimeout(next, 650);
          }
        };
        next();
      };
      if ("IntersectionObserver" in window) {
        io3 = new IntersectionObserver(
          (es) => es.forEach((e) => { if (e.isIntersecting) { play(); io3?.unobserve(e.target); } }),
          { threshold: 0.4 },
        );
        io3.observe(chat);
      } else {
        play();
      }
    }

    return () => { io?.disconnect(); io2?.disconnect(); io3?.disconnect(); };
  }, []);

  return (
    <>
      {/* Nav */}
      <nav className="sticky top-0 z-40 flex items-center justify-between border-b border-line/60 bg-bg/80 px-6 py-3 backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-brand text-sm">🎫</span>
          <div className="leading-none">
            <span className="grad-text text-xl font-extrabold">Booking Agent</span>
            <span className="ml-2 text-[10px] text-muted">AI booking concierge</span>
          </div>
        </div>
        <ul className="hidden gap-6 text-sm text-white/80 md:flex">
          <li><a href="#how" className="hover:text-white">How it works</a></li>
          <li><a href="#why" className="hover:text-white">Why Booking Agent</a></li>
          <li><a href="#demo" className="hover:text-white">See it</a></li>
        </ul>
        <span className="rounded-full border border-line px-3 py-1 text-xs text-white/80">EN</span>
      </nav>

      {/* Hero */}
      <header className="relative flex min-h-[92vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <div className="hero-aurora">
          <span className="blob blob-1" />
          <span className="blob blob-2" />
          <span className="blob blob-3" />
        </div>
        <div id="particles" className="particles" />

        <div className="relative z-10 max-w-3xl">
          <span className="reveal inline-block rounded-full border border-line px-3 py-1 text-xs uppercase tracking-widest text-white/70">
            🎫 AI-Powered Ticketing · Saudi Arabia
          </span>
          <h1 className="reveal mt-6 text-5xl font-extrabold leading-[1.05] md:text-7xl">
            Book live events <span className="grad-anim">in one chat.</span>
          </h1>
          <p className="reveal mx-auto mt-5 max-w-xl text-lg text-white/70">
            From “I want a ticket” to a QR ticket in your inbox — no forms, no five-step
            checkout. Just a conversation.
          </p>
          <div className="reveal mt-8 flex flex-wrap items-center justify-center gap-4">
            <button
              onClick={() => setChatOpen(true)}
              className="btn-shine glow rounded-full bg-brand px-7 py-3 font-semibold shadow-lg shadow-brand-purple/40 transition hover:scale-105"
            >
              Book with AI 🎫
            </button>
            <a href="#how" className="text-sm font-semibold text-muted transition hover:text-white">
              See how it works ↓
            </a>
          </div>
          <div className="reveal mt-8 flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-white/60">
            <span>● Seat holds in 10 min</span>
            <span>● Member discounts applied</span>
            <span>● QR ticket to your inbox</span>
            <span>● {aiActive ? "Live AI agent" : "Confirm before you pay"}</span>
          </div>
        </div>

        <div className="marquee relative z-10 mt-12 w-full border-y border-line py-4">
          <div className="marquee-track">
            {[...VIBES, ...VIBES].map((v, i) => (
              <span key={i}>
                {v}
                <span aria-hidden className="px-4 text-brand-purple">✦</span>
              </span>
            ))}
          </div>
        </div>
        <div className="scroll-cue absolute bottom-5"><span /></div>
      </header>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-6xl px-6 py-20">
        <div className="reveal mb-12 text-center">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-brand-purple">The idea</span>
          <h2 className="mt-2 text-3xl font-extrabold md:text-4xl">
            One conversation. <span className="grad-text">Ticket in your inbox.</span>
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-muted">
            You chat; the agent finds the event, applies your member discount, holds your seats
            atomically, and waits for your OK before charging anything.
          </p>
        </div>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li
              key={s.n}
              className="reveal rounded-2xl border border-line bg-surface p-6 transition hover:-translate-y-1 hover:border-brand-purple"
              style={{ transitionDelay: `${i * 120}ms` }}
            >
              <span className="grid h-10 w-10 place-items-center rounded-full bg-brand font-extrabold text-white shadow-lg shadow-brand-purple/40">
                {s.n}
              </span>
              <h3 className="mt-4 text-lg font-bold">{s.t}</h3>
              <p className="mt-1 text-sm text-muted">{s.d}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Why */}
      <section id="why" className="border-y border-line/60 bg-[#14141c] py-20">
        <div className="mx-auto max-w-6xl px-6">
          <div className="reveal mb-12 text-center">
            <span className="text-xs font-bold uppercase tracking-[0.16em] text-brand-purple">Why it’s different</span>
            <h2 className="mt-2 text-3xl font-extrabold md:text-4xl">
              A booking <span className="grad-text">agent</span>, not a search bar
            </h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <article
                key={f.t}
                className="feat reveal rounded-2xl border border-line bg-bg p-6 transition hover:-translate-y-1.5 hover:border-brand-purple"
                style={{ transitionDelay: `${i * 80}ms` }}
              >
                <div className="feat-icon mb-3 inline-block text-3xl">{f.i}</div>
                <h3 className="text-lg font-bold">{f.t}</h3>
                <p className="mt-1 text-sm text-muted">{f.d}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Demo */}
      <section id="demo" className="mx-auto max-w-6xl px-6 py-20 text-center">
        <div className="reveal mb-10">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-brand-purple">See it</span>
          <h2 className="mt-2 text-3xl font-extrabold md:text-4xl">
            From “I want a ticket” to <span className="grad-text">done</span>
          </h2>
        </div>
        <div className="reveal mx-auto max-w-md rounded-[28px] border border-line bg-surface p-5 shadow-2xl">
          <div className="mx-auto mb-4 h-1.5 w-28 rounded-full bg-line" />
          <div id="demo-chat" className="flex min-h-[250px] flex-col gap-2">
            {DEMO.map((m, i) => (
              <div
                key={i}
                className={`bubble ${m.who} max-w-[88%] rounded-2xl px-4 py-2 text-left text-[0.95rem] leading-snug ${
                  m.who === "user"
                    ? "self-end rounded-br-md bg-gradient-to-br from-[#e6007e] to-[#7b2ff7] text-white"
                    : "self-start rounded-bl-md border border-line bg-[#1c1c2a]"
                }`}
              >
                {m.t}
              </div>
            ))}
            <div id="demo-typing" className="typing-dots self-start px-3 py-2">
              <span /><span /><span />
            </div>
          </div>
        </div>
        <button
          onClick={() => setChatOpen(true)}
          className="btn-shine glow mt-8 rounded-full bg-brand px-7 py-3 font-semibold shadow-lg shadow-brand-purple/40 transition hover:scale-105"
        >
          Try it now — Book with AI 🎫
        </button>
      </section>

      {/* By the numbers */}
      <section id="numbers" className="mx-auto max-w-6xl px-6 py-20">
        <div className="reveal mb-12 text-center">
          <span className="text-xs font-bold uppercase tracking-[0.16em] text-brand-purple">By the numbers</span>
          <h2 className="mt-2 text-3xl font-extrabold md:text-4xl">
            The checkout funnel, <span className="grad-text">collapsed</span>
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-muted">
            Ticketing loses most of its sales at checkout. Booking Agent turns the entire funnel into a
            single conversation — here’s the idea in numbers.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {STATS.map((s, i) => (
            <div
              key={i}
              className={`reveal rounded-2xl border border-line p-7 text-center ${
                s.mid ? "bg-gradient-to-br from-[#e6007e]/15 to-[#7b2ff7]/15" : "bg-surface"
              }`}
              style={{ transitionDelay: `${i * 80}ms` }}
            >
              <div className="grad-text text-5xl font-black leading-none">
                <span className="count" data-to={s.to}>0</span>{s.suf}
              </div>
              <p className="mt-3 text-sm text-muted">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-line/60 px-6 py-8 text-center text-xs text-muted">
        <strong className="grad-text">Booking Agent</strong> — AI event-booking concierge · Booking-Agent
        capstone 2026
      </footer>

      <Chat open={chatOpen} setOpen={setChatOpen} queued={null} onConsumed={() => {}} aiActive={aiActive} />
    </>
  );
}
