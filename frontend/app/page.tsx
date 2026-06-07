"use client";

import { useEffect, useState } from "react";
import Chat from "@/components/Chat";
import { health, listEvents } from "@/lib/api";
import type { EventOut } from "@/lib/types";

// Literal classes so Tailwind JIT picks the gradients up.
const POSTERS = [
  "from-[#e6007e] to-[#7b2ff7]",
  "from-[#ff6b35] to-[#e6007e]",
  "from-[#00b4d8] to-[#7b2ff7]",
  "from-[#22d46e] to-[#00b4d8]",
  "from-[#ffbe0b] to-[#e6007e]",
  "from-[#7b2ff7] to-[#00b4d8]",
];

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function Home() {
  const [events, setEvents] = useState<EventOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aiActive, setAiActive] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [queued, setQueued] = useState<string | null>(null);

  useEffect(() => {
    listEvents()
      .then(setEvents)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load events"));
    health()
      .then((h) => setAiActive(h.llm_configured))
      .catch(() => setAiActive(false));
  }, []);

  function book(id: number) {
    setQueued(`#${id}`);
    setChatOpen(true);
  }

  return (
    <>
      {/* Nav */}
      <nav className="sticky top-0 z-40 flex items-center justify-between border-b border-line/60 bg-bg/80 px-6 py-3 backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-brand text-sm">🎫</span>
          <div className="leading-none">
            <span className="grad-text text-xl font-extrabold">Tazkara</span>
            <span className="ml-2 text-[10px] text-muted">by Booking-Agent</span>
          </div>
        </div>
        <ul className="hidden gap-6 text-sm text-white/80 md:flex">
          <li>Events</li>
          <li>Sports</li>
          <li>Concerts</li>
          <li>Theatre</li>
          <li>More</li>
        </ul>
        <span className="rounded-full border border-line px-3 py-1 text-xs text-white/80">EN | ع</span>
      </nav>

      {/* Hero */}
      <header className="relative overflow-hidden bg-brand-soft px-6 py-20 text-center">
        <span className="rounded-full border border-line px-3 py-1 text-xs uppercase tracking-widest text-white/70">
          AI-Powered Ticketing
        </span>
        <h1 className="mt-6 text-5xl font-extrabold leading-tight md:text-6xl">
          Book live events
          <br />
          <span className="grad-text">in one chat</span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-white/70">
          From “I want a ticket” to ticket in your inbox.
        </p>
        <button
          onClick={() => setChatOpen(true)}
          className="mt-8 rounded-full bg-brand px-7 py-3 font-semibold shadow-lg shadow-brand-purple/40 transition hover:scale-105"
        >
          Book with AI 🎫
        </button>
        <div className="mt-8 flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm text-white/60">
          <span>● Seat holds in 10 min</span>
          <span>● Member discounts applied</span>
          <span>● QR ticket to your inbox</span>
          <span>● {aiActive ? "Live AI agent" : "No hidden fees"}</span>
        </div>
      </header>

      {/* Events */}
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="mb-6 flex items-end justify-between">
          <h2 className="text-2xl font-bold">What’s on</h2>
          <span className="text-sm text-muted">{events ? `${events.length} events` : ""}</span>
        </div>

        {error && (
          <div className="rounded-xl border border-line bg-surface p-6 text-center text-muted">
            🎭 Couldn’t reach the backend ({error}). Start it with{" "}
            <code className="text-white">uvicorn</code> on :8000.
          </div>
        )}

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {(events ?? Array.from({ length: 6 }).map((_, i) => null)).map((ev, i) =>
            ev ? (
              <article
                key={ev.id}
                className="overflow-hidden rounded-2xl border border-line bg-surface transition hover:-translate-y-1 hover:border-brand-purple"
              >
                <div
                  className={`relative h-36 bg-gradient-to-br ${POSTERS[ev.id % POSTERS.length]} p-4`}
                >
                  <span className="absolute bottom-3 left-4 right-4 text-lg font-bold drop-shadow">
                    {ev.title}
                  </span>
                </div>
                <div className="p-4">
                  <div className="text-sm text-white/80">
                    {ev.venue} · {ev.city}
                  </div>
                  <div className="text-xs text-muted">{fmtDate(ev.starts_at)}</div>
                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-xs text-muted">
                      {ev.price_from_sar ? `From ${ev.price_from_sar}` : ""}
                    </span>
                    <button
                      onClick={() => book(ev.id)}
                      className="rounded-full bg-brand px-4 py-1.5 text-sm font-medium"
                    >
                      Book
                    </button>
                  </div>
                </div>
              </article>
            ) : (
              <div key={i} className="h-64 animate-pulse rounded-2xl border border-line bg-surface" />
            ),
          )}
        </div>
      </section>

      <footer className="border-t border-line/60 px-6 py-8 text-center text-xs text-muted">
        <strong className="grad-text">Tazkara</strong> — demo clone of WeBook · Booking-Agent capstone
        2026 · not affiliated with WeBook
      </footer>

      <Chat
        open={chatOpen}
        setOpen={setChatOpen}
        queued={queued}
        onConsumed={() => setQueued(null)}
        aiActive={aiActive}
      />
    </>
  );
}
