"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { chat, createSession, mediaUrl, pay, seats, venue } from "@/lib/api";
import type { AgentReply, SeatMapData, Ticket, VenueLayout } from "@/lib/types";

type Msg = {
  id: number;
  role: "user" | "agent";
  text?: string;
  reply?: AgentReply;
  ticket?: Ticket;
};

let _mid = 0;
const nextId = () => ++_mid;

function fmtCountdown(expiresIso: string, nowMs: number): string {
  const diff = Math.max(0, Math.floor((new Date(expiresIso).getTime() - nowMs) / 1000));
  const m = Math.floor(diff / 60);
  const s = diff % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function Chat({
  open,
  setOpen,
  queued,
  onConsumed,
  aiActive,
}: {
  open: boolean;
  setOpen: (b: boolean) => void;
  queued: string | null;
  onConsumed: () => void;
  aiActive: boolean;
}) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: nextId(),
      role: "agent",
      text:
        "Hello! I'm your Booking Assistant 🎫\nTell me what you're looking for — e.g. \"Coldplay in Riyadh\" — or click any event to start.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([
    "Coldplay in Riyadh",
    "Riyadh Derby",
    "What's on this weekend?",
  ]);
  const [now, setNow] = useState(() => Date.now());

  const listRef = useRef<HTMLDivElement>(null);
  const initRef = useRef(false);

  // Create a session once.
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    createSession()
      .then(setSessionId)
      .catch(() => setSessionId(null));
  }, []);

  // Tick the countdown clock once per second.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Auto-scroll on new messages.
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || sending) return;
      setSuggestions([]);
      setMessages((m) => [...m, { id: nextId(), role: "user", text }]);
      setInput("");
      setSending(true);
      try {
        let sid = sessionId;
        if (!sid) {
          sid = await createSession();
          setSessionId(sid);
        }
        const reply = await chat(sid, text);
        setMessages((m) => [...m, { id: nextId(), role: "agent", text: reply.reply, reply }]);
        setSuggestions(reply.suggestions ?? []);
      } catch (e) {
        const err = e instanceof Error ? e.message : "Something went wrong";
        setMessages((m) => [
          ...m,
          { id: nextId(), role: "agent", text: `⚠️ ${err}. Is the backend running on :8000?` },
        ]);
      } finally {
        setSending(false);
      }
    },
    [sessionId, sending],
  );

  // Consume a queued message (e.g. an event "Book" click → "#3").
  useEffect(() => {
    if (queued && sessionId) {
      send(queued);
      onConsumed();
    }
  }, [queued, sessionId, send, onConsumed]);

  async function handlePay(bookingId: number) {
    setSending(true);
    try {
      const { ticket } = await pay(bookingId);
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "agent", text: "🎉 Payment confirmed — here's your ticket!" },
        { id: nextId(), role: "agent", ticket },
      ]);
      setSuggestions([]);
    } catch (e) {
      const err = e instanceof Error ? e.message : "Payment failed";
      setMessages((m) => [...m, { id: nextId(), role: "agent", text: `⚠️ ${err}` }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      {/* Launcher */}
      <button
        onClick={() => setOpen(!open)}
        aria-label="Open booking assistant"
        className="fixed bottom-5 right-5 z-50 grid h-14 w-14 place-items-center rounded-full bg-brand text-2xl shadow-lg shadow-brand-purple/40 transition hover:scale-105"
      >
        {open ? "✕" : "🎫"}
      </button>

      {/* Panel */}
      {open && (
        <section className="fixed bottom-24 right-5 z-50 flex h-[72vh] max-h-[640px] w-[min(92vw,390px)] flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl animate-slideUp">
          {/* Header */}
          <header className="flex items-center justify-between bg-brand px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">🎫</span>
              <div className="leading-tight">
                <div className="font-semibold">Booking Assistant</div>
                <div className="flex items-center gap-1 text-xs text-white/80">
                  <span className="h-2 w-2 rounded-full bg-emerald-300 animate-pulseDot" />
                  {aiActive ? "AI mode" : "Ready"}
                </div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close" className="text-white/80 hover:text-white">
              ✕
            </button>
          </header>

          {/* Messages */}
          <div ref={listRef} className="scroll-thin flex-1 space-y-3 overflow-y-auto p-3">
            {messages.map((m, i) => (
              <MessageBubble
                key={m.id}
                msg={m}
                now={now}
                onSend={send}
                onPay={handlePay}
                isLast={i === messages.length - 1}
              />
            ))}
            {sending && (
              <div className="flex gap-1 px-2 text-muted">
                <span className="h-2 w-2 animate-pulseDot rounded-full bg-muted" />
                <span className="h-2 w-2 animate-pulseDot rounded-full bg-muted [animation-delay:.2s]" />
                <span className="h-2 w-2 animate-pulseDot rounded-full bg-muted [animation-delay:.4s]" />
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="border-t border-line p-3">
            {suggestions.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-line bg-surface2 px-3 py-1 text-xs text-white/90 transition hover:border-brand-purple"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
              className="flex items-center gap-2"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message…"
                className="flex-1 rounded-full border border-line bg-bg px-4 py-2 text-sm outline-none focus:border-brand-purple"
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                aria-label="Send"
                className="grid h-9 w-9 place-items-center rounded-full bg-brand text-sm disabled:opacity-40"
              >
                ➤
              </button>
            </form>
            <p className="mt-2 text-center text-[10px] text-muted">
              {aiActive ? "Powered by an LLM agent" : "Rule-based demo — add an LLM key for full NLU"}
            </p>
          </div>
        </section>
      )}
    </>
  );
}

function MessageBubble({
  msg,
  now,
  onSend,
  onPay,
  isLast,
}: {
  msg: Msg;
  now: number;
  onSend: (m: string) => void;
  onPay: (bookingId: number) => void;
  isLast: boolean;
}) {
  if (msg.ticket) return <TicketCard ticket={msg.ticket} />;

  const isUser = msg.role === "user";
  // Render **bold** as <strong>; newlines are handled by whitespace-pre-wrap.
  const rich = (text: string) =>
    text.split(/\*\*(.+?)\*\*/g).map((p, i) => (i % 2 ? <strong key={i}>{p}</strong> : <span key={i}>{p}</span>));
  return (
    <div className={isUser ? "flex flex-col items-end" : "flex flex-col items-start"}>
      <span className="mb-0.5 px-1 text-[10px] uppercase tracking-wide text-muted">
        {isUser ? "You" : "Assistant"}
      </span>
      {msg.text && (
        <div
          className={
            isUser
              ? "max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand px-3 py-2 text-sm"
              : "max-w-[90%] whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-surface2 px-3 py-2 text-sm"
          }
        >
          {rich(msg.text)}
        </div>
      )}
      {msg.reply && <Payload reply={msg.reply} now={now} onSend={onSend} onPay={onPay} isLast={isLast} />}
    </div>
  );
}

function Payload({
  reply,
  now,
  onSend,
  onPay,
  isLast,
}: {
  reply: AgentReply;
  now: number;
  onSend: (m: string) => void;
  onPay: (bookingId: number) => void;
  isLast: boolean;
}) {
  return (
    <div className="mt-2 w-[90%] space-y-2">
      {reply.member && (
        <div className="inline-flex items-center gap-1 rounded-full border border-line bg-surface2 px-3 py-1 text-xs">
          <span>{reply.member.is_member ? "⭐" : "👤"}</span>
          {reply.member.label}
        </div>
      )}

      {reply.events && reply.events.length > 0 && (
        <div className="space-y-2">
          {reply.events.map((ev) => (
            <div key={ev.id} className="overflow-hidden rounded-xl border border-line bg-surface2">
              <div className="h-2 w-full bg-brand" />
              <div className="p-3">
                <div className="text-sm font-semibold">{ev.title}</div>
                <div className="text-xs text-muted">
                  {ev.venue} · {ev.city}
                </div>
                {ev.when ? (
                  <div className="mt-0.5 text-xs text-muted">🗓 {ev.when}</div>
                ) : null}
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-muted">
                    {ev.price_from_sar ? `From ${ev.price_from_sar}` : ""}
                  </span>
                  <button
                    onClick={() => onSend(`#${ev.id}`)}
                    className="rounded-full bg-brand px-3 py-1 text-xs font-medium"
                  >
                    Select
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {reply.categories && reply.categories.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {reply.categories.map((c) => (
            <button
              key={c.category}
              onClick={() => onSend(c.category)}
              className="rounded-lg border border-line bg-surface2 px-2.5 py-1.5 text-left text-xs transition hover:border-brand-purple"
            >
              <span className="font-semibold capitalize">{c.category}</span>{" "}
              {c.discounted_sar !== c.base_sar ? (
                <span>
                  <s className="text-muted">{c.base_sar}</s>{" "}
                  <span className="grad-text font-semibold">{c.discounted_sar}</span>
                </span>
              ) : (
                <span>{c.base_sar}</span>
              )}
              <span className="block text-[10px] text-muted">{c.available} available</span>
            </button>
          ))}
        </div>
      )}

      {reply.quote && (
        <div className="rounded-xl border border-line bg-surface2 p-3 text-sm">
          {reply.quote.lines.map((l, i) => (
            <div
              key={i}
              className={i === reply.quote!.lines.length - 1 ? "mt-1 border-t border-line pt-1 font-semibold" : ""}
            >
              {l}
            </div>
          ))}
        </div>
      )}

      {reply.seatmap_url && <SeatMap reply={reply} onSend={onSend} frozen={!isLast} />}

      {reply.hold && !reply.confirmation && (
        <div className="rounded-lg border border-line bg-surface2 px-3 py-2 text-xs">
          Seats held: <strong>{reply.hold.seat_ids.join(", ")}</strong> — expires in{" "}
          <span className="grad-text font-semibold">{fmtCountdown(reply.hold.expires_at, now)}</span>
        </div>
      )}

      {reply.confirmation && (
        <div className="rounded-xl border border-brand-purple/60 bg-surface2 p-3 text-sm">
          <div className="font-semibold">{reply.confirmation.event_title}</div>
          <Row k="When" v={reply.confirmation.when} />
          <Row k="Venue" v={reply.confirmation.venue} />
          <Row k="Seats" v={reply.confirmation.seats.join(", ")} />
          <Row k="Subtotal" v={reply.confirmation.subtotal_sar} />
          <Row k="VAT 15%" v={reply.confirmation.vat_sar} />
          <div className="mt-1 flex justify-between border-t border-line pt-1 font-semibold">
            <span>Total</span>
            <span className="grad-text">{reply.confirmation.total_sar}</span>
          </div>
          <div className="mt-1 text-[11px] text-muted">
            Hold expires in {fmtCountdown(reply.confirmation.expires_at, now)}
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => onSend("confirm")}
              className="flex-1 rounded-lg bg-brand py-2 text-sm font-semibold"
            >
              ✅ Confirm &amp; pay
            </button>
            <button
              onClick={() => onSend("cancel")}
              className="rounded-lg border border-line px-3 py-2 text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {reply.payment && (
        <div className="rounded-xl border border-line bg-surface2 p-3 text-sm">
          <div className="mb-2 flex justify-between font-semibold">
            <span>Total</span>
            <span className="grad-text">{reply.payment.total_sar}</span>
          </div>
          <button
            onClick={() => onPay(reply.payment!.booking_id)}
            className="w-full rounded-lg bg-brand py-2 text-sm font-semibold"
          >
            Pay now (sandbox)
          </button>
        </div>
      )}
    </div>
  );
}

const CAT_ACCENT: Record<string, string> = {
  vip: "#ffd166",
  gold: "#f4a62a",
  silver: "#c9d1d9",
  standing: "#6ee7b7",
};

/** Venue seat map: the stage, then every section by distance from it (VIP front →
 *  Standing back). The chosen section expands into a clickable grid; the others are
 *  tappable bands that switch section. Confirm sends the seat IDs (same as typing). */
function SeatMap({
  reply,
  onSend,
  frozen = false,
}: {
  reply: AgentReply;
  onSend: (m: string) => void;
  frozen?: boolean;
}) {
  const idMatch = /\/events\/(\d+)\//.exec(reply.seatmap_url || "");
  const eventId = idMatch ? Number(idMatch[1]) : null;
  const qs = new URLSearchParams((reply.seatmap_url || "").split("?")[1] || "");
  const category = reply.quote?.category || qs.get("category") || "";
  const quantity = reply.quote?.quantity || 1;

  const [data, setData] = useState<SeatMapData | null>(null);
  const [layout, setLayout] = useState<VenueLayout | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    if (eventId == null || !category) {
      setError("Seat map unavailable");
      return;
    }
    let alive = true;
    Promise.all([venue(eventId), seats(eventId, category)])
      .then(([v, s]) => {
        if (alive) {
          setLayout(v);
          setData(s);
        }
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [eventId, category]);

  function toggle(id: string, status: string) {
    if (frozen || status !== "available") return;
    setSelected((cur) => {
      if (cur.includes(id)) return cur.filter((s) => s !== id);
      if (cur.length >= quantity) return [...cur.slice(1), id]; // rotate out oldest
      return [...cur, id];
    });
  }

  const ready = selected.length === quantity;
  const seatClass = (status: string, isSel: boolean) =>
    isSel
      ? "bg-brand border-white text-white shadow-[0_0_0_2px_rgba(255,255,255,.25)] -translate-y-0.5"
      : status === "available"
        ? "bg-[#2ea043] border-transparent text-white hover:-translate-y-0.5"
        : status === "held"
          ? "bg-[#d29922] border-transparent text-white/90 cursor-not-allowed"
          : "bg-[#5b5b6b] border-transparent text-white/60 cursor-not-allowed opacity-70";

  return (
    <div
      className={`relative flex flex-col gap-2 rounded-xl border border-line bg-surface2 p-3 ${frozen ? "opacity-50 saturate-50" : ""}`}
    >
      {frozen && (
        <span className="absolute right-2 top-2 z-10 rounded-full border border-line bg-surface px-2 py-0.5 text-[10px] font-bold text-muted">
          ✓ locked
        </span>
      )}
      <div className="mx-auto w-3/4 rounded-b-[60%] border-t-2 border-brand-purple bg-gradient-to-b from-brand-purple/30 to-transparent py-0.5 text-center text-[10px] tracking-[0.35em] text-muted">
        STAGE
      </div>
      <div className="text-center text-sm font-semibold">
        Pick {quantity} {category} seat{quantity > 1 ? "s" : ""} — tap a section to change
      </div>

      <div className="flex flex-col gap-1.5">
        {error && <p className="text-xs text-muted">{error} — type seat IDs to continue.</p>}
        {!layout && !error && <p className="text-xs text-muted">Loading venue…</p>}
        {layout?.sections.map((sec) => {
          const accent = CAT_ACCENT[sec.category] || "#8888aa";
          const isActive = sec.category === category;
          if (isActive) {
            return (
              <div
                key={sec.category}
                className="rounded-md border border-brand-purple bg-surface p-2"
                style={{ borderLeft: `4px solid ${accent}` }}
              >
                <SectionLabel sec={sec} accent={accent} active />
                <div className="mt-1.5 flex flex-col items-center gap-1 overflow-x-auto">
                  {!data && <span className="text-[11px] text-muted">Loading seats…</span>}
                  {data?.rows.map((r) => (
                    <div key={r.row} className="flex items-center gap-1">
                      <span className="w-4 text-center text-[10px] font-bold text-muted">{r.row}</span>
                      {r.seats.map((s) => {
                        const isSel = selected.includes(s.id);
                        return (
                          <button
                            key={s.id}
                            type="button"
                            title={`${s.id} · ${s.status}`}
                            aria-label={`Seat ${s.id}, ${s.status}`}
                            disabled={frozen || s.status !== "available"}
                            onClick={() => toggle(s.id, s.status)}
                            className={`h-6 w-6 shrink-0 rounded-[7px_7px_4px_4px] border text-[10px] font-bold transition ${seatClass(s.status, isSel)}`}
                          >
                            {s.number}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            );
          }
          return (
            <button
              key={sec.category}
              type="button"
              disabled={frozen || sec.available === 0}
              onClick={() => onSend(sec.category)}
              className="rounded-md border border-line bg-surface p-2 text-left transition hover:-translate-y-px hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50"
              style={{ borderLeft: `4px solid ${accent}` }}
            >
              <SectionLabel sec={sec} accent={accent} />
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap justify-center gap-3 text-[11px] text-muted">
        <Legend swatch="bg-[#2ea043]" label="available" />
        <Legend swatch="bg-brand" label="selected" />
        <Legend swatch="bg-[#d29922]" label="held" />
        <Legend swatch="bg-[#5b5b6b]" label="sold" />
      </div>

      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-bold">
          {selected.length} of {quantity} selected
        </span>
        <button
          type="button"
          disabled={frozen || !ready}
          onClick={() => ready && !frozen && onSend(selected.join(", "))}
          className="max-w-[65%] truncate rounded-md bg-brand px-3 py-2 text-xs font-bold text-white transition hover:-translate-y-px disabled:cursor-not-allowed disabled:translate-y-0 disabled:border disabled:border-line disabled:bg-surface disabled:opacity-40"
        >
          {ready ? `Hold ${selected.join(", ")} →` : `Select ${quantity - selected.length} more`}
        </button>
      </div>
      <p className="text-center text-[11px] text-muted">
        Tip: you can also type seat IDs (e.g. &ldquo;G3, G4&rdquo;) and send.
      </p>
    </div>
  );
}

function SectionLabel({
  sec,
  accent,
  active = false,
}: {
  sec: VenueLayout["sections"][number];
  accent: string;
  active?: boolean;
}) {
  const sold = sec.available === 0;
  return (
    <div className="flex flex-wrap items-baseline gap-2">
      <span className="text-[13px] font-extrabold tracking-wide" style={{ color: accent }}>
        {active ? "📍 " : ""}
        {sec.category.toUpperCase()}
      </span>
      <span className="text-[11px] text-muted">
        {sold
          ? "sold out"
          : `${sec.available} seats · from ${sec.price_from_sar}${active ? " · you're here" : " · tap to choose"}`}
      </span>
    </div>
  );
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <i className={`inline-block h-[11px] w-[11px] rounded-[3px] ${swatch}`} />
      {label}
    </span>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted">{k}</span>
      <span>{v}</span>
    </div>
  );
}

function TicketCard({ ticket }: { ticket: Ticket }) {
  return (
    <div className="flex flex-col items-start">
      <span className="mb-0.5 px-1 text-[10px] uppercase tracking-wide text-muted">Assistant</span>
      <div className="w-[90%] overflow-hidden rounded-xl border border-line bg-surface2">
        <div className="bg-brand px-3 py-2 text-sm font-semibold">{ticket.event_title}</div>
        <div className="p-3">
          <Row k="Seats" v={ticket.seats.join(", ")} />
          <Row k="Email" v={ticket.email} />
          <Row k="Booking ID" v={String(ticket.booking_id)} />
          <div className="mt-1 flex justify-between border-t border-line pt-1 font-semibold">
            <span>Total paid</span>
            <span className="grad-text">{ticket.total_sar}</span>
          </div>
          <div className="mt-3 grid place-items-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={mediaUrl(ticket.qr_url)}
              alt="Ticket QR code"
              className="h-36 w-36 rounded-md bg-white p-1"
            />
            <a
              href={mediaUrl(ticket.qr_url)}
              download={`ticket-${ticket.booking_id}.png`}
              className="mt-2 text-xs text-brand-purple underline"
            >
              ⬇ Download QR
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
