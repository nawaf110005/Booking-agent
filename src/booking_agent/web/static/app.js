/**
 * app.js — Tazkara Booking-Agent Web UI
 *
 * Architecture:
 *   - State object holds session_id, open/closed, active hold timers, etc.
 *   - API helpers: createSession(), fetchEvents(), chat(), pay()
 *   - UI helpers: appendAgentBubble(), appendUserBubble(), renderPayload()
 *   - Event wiring at the bottom (DOMContentLoaded)
 *
 * All fetch calls are wrapped in try/catch; errors surface as agent bubbles.
 * No frameworks, no build step, no external CDN.
 */

"use strict";

/* ─────────────────────────────────────────────────────────────
   STATE
───────────────────────────────────────────────────────────── */
const STATE = {
  sessionId: null,
  chatOpen: false,
  sending: false,
  /** Timer id for active hold countdown */
  holdTimerId: null,
  /** Timer id for confirmation card countdown */
  confirmTimerId: null,
  /** Current suggestions to display in the composer bar */
  currentSuggestions: [],
};

/* ─────────────────────────────────────────────────────────────
   CONSTANTS
───────────────────────────────────────────────────────────── */
const API = {
  sessions: "/v1/sessions",
  events:   "/v1/events",
  chat:     "/v1/chat",
  pay:      (bookingId) => `/v1/pay/${bookingId}`,
};

/**
 * Deterministic poster gradient per event id.
 * We pick from a curated palette so every card has a stable, vivid colour.
 */
const POSTER_GRADIENTS = [
  ["#e6007e", "#7b2ff7"],
  ["#ff6b35", "#e6007e"],
  ["#00b4d8", "#7b2ff7"],
  ["#22d46e", "#00b4d8"],
  ["#ffbe0b", "#e6007e"],
  ["#7b2ff7", "#00b4d8"],
  ["#e6007e", "#ff6b35"],
  ["#3a0ca3", "#e6007e"],
];
function posterGradient(eventId) {
  const idx = Math.abs(eventId) % POSTER_GRADIENTS.length;
  const [a, b] = POSTER_GRADIENTS[idx];
  return `linear-gradient(135deg, ${a}, ${b})`;
}

/* ─────────────────────────────────────────────────────────────
   API HELPERS
───────────────────────────────────────────────────────────── */

/**
 * Generic JSON fetch wrapper.
 * @returns {Promise<any>} parsed JSON
 * @throws  on network error or non-2xx
 */
async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      msg = body.detail || body.error || msg;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

/** POST /v1/sessions → { session_id } */
async function createSession() {
  const data = await apiFetch(API.sessions, { method: "POST", body: "{}" });
  return data.session_id;
}

/** GET /v1/events → EventOut[] */
async function fetchEvents(query = "", city = "") {
  const params = new URLSearchParams();
  if (query) params.set("query", query);
  if (city)  params.set("city", city);
  const qs = params.toString();
  return apiFetch(`${API.events}${qs ? "?" + qs : ""}`);
}

/** POST /v1/chat → AgentReply */
async function sendChat(message) {
  return apiFetch(API.chat, {
    method: "POST",
    body: JSON.stringify({ session_id: STATE.sessionId, message }),
  });
}

/** POST /v1/pay/{bookingId} → { ticket: {...} } */
async function payBooking(bookingId) {
  return apiFetch(API.pay(bookingId), { method: "POST", body: "{}" });
}

/* ─────────────────────────────────────────────────────────────
   DATE / TIME HELPERS
───────────────────────────────────────────────────────────── */

/** Format an ISO datetime string for display e.g. "Fri 14 Mar 2025, 20:00" */
function formatDate(isoString) {
  try {
    const d = new Date(isoString);
    return d.toLocaleString("en-GB", {
      weekday: "short", day: "numeric", month: "short",
      year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

/** Return "mm:ss" from a future ISO timestamp; negative → 0 */
function countdown(isoExpires) {
  const diff = Math.max(0, Math.floor((new Date(isoExpires) - Date.now()) / 1000));
  const m = Math.floor(diff / 60);
  const s = diff % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/* ─────────────────────────────────────────────────────────────
   DOM HELPERS
───────────────────────────────────────────────────────────── */

/** Safely convert a plain string to node with \n → <br> (no innerHTML eval). */
function textToNodes(str) {
  const frag = document.createDocumentFragment();
  str.split("\n").forEach((line, i, arr) => {
    frag.appendChild(document.createTextNode(line));
    if (i < arr.length - 1) frag.appendChild(document.createElement("br"));
  });
  return frag;
}

/** Scroll the message list to the bottom. */
function scrollToBottom() {
  const list = document.getElementById("chat-messages");
  list.scrollTop = list.scrollHeight;
}

/**
 * Remove any existing typing indicator and return its container ref.
 * Creates a fresh one.
 */
function showTyping() {
  removeTyping();
  const list = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "typing-indicator";
  wrap.id = "typing-indicator";
  wrap.setAttribute("aria-label", "Agent is typing");
  wrap.innerHTML = "<span></span><span></span><span></span>";
  list.appendChild(wrap);
  scrollToBottom();
}

function removeTyping() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

/* ─────────────────────────────────────────────────────────────
   BUBBLE BUILDERS
───────────────────────────────────────────────────────────── */

/**
 * Append a user message bubble to the chat list.
 * @param {string} text
 */
function appendUserBubble(text) {
  const list = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "msg msg--user";

  const sender = document.createElement("div");
  sender.className = "msg__sender";
  sender.textContent = "You";

  const bubble = document.createElement("div");
  bubble.className = "msg__bubble";
  bubble.appendChild(textToNodes(text));

  wrap.appendChild(sender);
  wrap.appendChild(bubble);
  list.appendChild(wrap);
  scrollToBottom();
}

/**
 * Append an agent message bubble (with optional payload) to the chat list.
 * @param {string} replyText   The agent's text reply.
 * @param {object|null} payload  The full AgentReply (for structured data).
 * @returns {HTMLElement}        The wrapper div (so callers can append more).
 */
function appendAgentBubble(replyText, payload = null) {
  const list = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "msg msg--agent";

  const sender = document.createElement("div");
  sender.className = "msg__sender";
  sender.textContent = "Assistant";

  const bubble = document.createElement("div");
  bubble.className = "msg__bubble";
  if (replyText) bubble.appendChild(textToNodes(replyText));

  wrap.appendChild(sender);
  wrap.appendChild(bubble);

  // Render structured payload below the bubble
  if (payload) {
    const payloadEl = renderPayload(payload);
    if (payloadEl) {
      const payloadWrap = document.createElement("div");
      payloadWrap.className = "payload";
      payloadWrap.appendChild(payloadEl);
      wrap.appendChild(payloadWrap);
    }
  }

  list.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

/* ─────────────────────────────────────────────────────────────
   PAYLOAD RENDERER
   Handles all structured data from AgentReply.
───────────────────────────────────────────────────────────── */

/**
 * Given an AgentReply object, return a DOM fragment with all rich elements,
 * or null if there is nothing to render.
 */
function renderPayload(reply) {
  const frag = document.createDocumentFragment();
  let hasContent = false;

  /* ── events[] ─────────────────────────────────────────── */
  if (reply.events && reply.events.length > 0) {
    hasContent = true;
    const container = document.createElement("div");
    container.className = "mini-events";

    reply.events.forEach((ev) => {
      const card = document.createElement("div");
      card.className = "mini-event-card";

      const title = document.createElement("div");
      title.className = "mini-event-card__title";
      title.textContent = ev.title;

      const meta = document.createElement("div");
      meta.className = "mini-event-card__meta";
      meta.textContent = `${ev.venue} · ${ev.city}`;

      const footer = document.createElement("div");
      footer.className = "mini-event-card__footer";

      const date = document.createElement("span");
      date.style.fontSize = ".72rem";
      date.style.color = "var(--text-muted)";
      date.textContent = formatDate(ev.starts_at);

      const btn = document.createElement("button");
      btn.className = "btn-select";
      btn.textContent = "Select";
      btn.setAttribute("aria-label", `Select event ${ev.title}`);
      btn.addEventListener("click", () => handleUserMessage(`#${ev.id}`));

      if (ev.price_from_sar) {
        const price = document.createElement("span");
        price.style.fontSize = ".72rem";
        price.style.color = "var(--text-muted)";
        price.textContent = `From ${ev.price_from_sar}`;
        footer.appendChild(price);
      } else {
        footer.appendChild(date);
      }
      footer.appendChild(btn);

      card.appendChild(title);
      card.appendChild(meta);
      card.appendChild(footer);
      container.appendChild(card);
    });

    frag.appendChild(container);
  }

  /* ── member ───────────────────────────────────────────── */
  if (reply.member) {
    hasContent = true;
    const m = reply.member;
    const chip = document.createElement("div");
    chip.className = "member-chip";
    chip.setAttribute("role", "status");

    const icon = document.createElement("span");
    icon.className = "member-chip__icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = m.is_member ? "⭐" : "👤";

    chip.appendChild(icon);
    chip.appendChild(document.createTextNode(
      m.label || `${m.tier ? m.tier + " member" : "Guest"} · ${m.discount_label || "no discount"} · up to ${m.ticket_cap}`
    ));
    frag.appendChild(chip);
  }

  /* ── categories[] ─────────────────────────────────────── */
  if (reply.categories && reply.categories.length > 0) {
    hasContent = true;
    const container = document.createElement("div");
    container.className = "categories";

    reply.categories.forEach((cat) => {
      const btn = document.createElement("button");
      btn.className = "category-chip";
      btn.setAttribute("aria-label", `Select ${cat.category} category`);

      const hasDiscount = cat.discounted_sar && cat.discounted_sar !== cat.base_sar;

      // Name
      const name = document.createElement("strong");
      name.textContent = cat.category.charAt(0).toUpperCase() + cat.category.slice(1);

      // Price
      const price = document.createElement("span");
      price.className = "cat-price";

      if (hasDiscount) {
        const orig = document.createElement("s");
        orig.style.color = "var(--text-muted)";
        orig.textContent = cat.base_sar;
        const disc = document.createElement("span");
        disc.className = "cat-discounted";
        disc.textContent = ` → ${cat.discounted_sar}`;
        price.appendChild(orig);
        price.appendChild(disc);
      } else {
        price.textContent = cat.base_sar || "";
      }

      // Available
      const avail = document.createElement("span");
      avail.className = "cat-avail";
      avail.textContent = `${cat.available} left`;

      btn.appendChild(name);
      btn.appendChild(price);
      btn.appendChild(avail);

      btn.addEventListener("click", () => handleUserMessage(cat.category.toLowerCase()));
      container.appendChild(btn);
    });

    frag.appendChild(container);
  }

  /* ── quote ────────────────────────────────────────────── */
  if (reply.quote) {
    hasContent = true;
    const q = reply.quote;
    const card = document.createElement("div");
    card.className = "quote-card";
    card.setAttribute("role", "region");
    card.setAttribute("aria-label", "Booking quote");

    if (q.lines && q.lines.length) {
      q.lines.forEach((line, i) => {
        const row = document.createElement("div");
        row.className = i === q.lines.length - 1 ? "quote-card__total" : "quote-card__line";
        row.textContent = line;
        card.appendChild(row);
      });
    } else if (q.total_sar) {
      const total = document.createElement("div");
      total.className = "quote-card__total";
      total.textContent = `Total: ${q.total_sar}`;
      card.appendChild(total);
    }

    frag.appendChild(card);
  }

  /* ── seatmap_url ──────────────────────────────────────── */
  if (reply.seatmap_url) {
    hasContent = true;
    const wrap = document.createElement("div");
    wrap.className = "seatmap-wrap";

    const img = document.createElement("img");
    img.src = reply.seatmap_url;
    img.alt = "Seat map — green=available, amber=held, grey=sold";

    const caption = document.createElement("div");
    caption.className = "seatmap-caption";
    caption.textContent = "green = available · amber = held · grey = sold";

    const hint = document.createElement("div");
    hint.style.cssText = "font-size:.75rem;color:var(--text-muted);margin-top:.3rem;text-align:center;";
    hint.textContent = 'Type seat IDs (e.g. "G3, G4") then send to hold them';

    wrap.appendChild(img);
    wrap.appendChild(caption);
    wrap.appendChild(hint);
    frag.appendChild(wrap);
  }

  /* ── hold ─────────────────────────────────────────────── */
  if (reply.hold) {
    hasContent = true;
    const h = reply.hold;
    const card = document.createElement("div");
    card.className = "hold-card";
    card.setAttribute("role", "status");
    card.setAttribute("aria-live", "polite");

    const seats = h.seat_ids ? h.seat_ids.join(", ") : "";
    const label = document.createElement("span");
    label.textContent = `Seats held: ${seats} — expires in `;

    const countdownEl = document.createElement("span");
    countdownEl.className = "hold-card__countdown";
    countdownEl.textContent = countdown(h.expires_at);

    card.appendChild(label);
    card.appendChild(countdownEl);
    frag.appendChild(card);

    // Live countdown timer
    if (STATE.holdTimerId) clearInterval(STATE.holdTimerId);
    STATE.holdTimerId = setInterval(() => {
      const remaining = countdown(h.expires_at);
      countdownEl.textContent = remaining;
      if (remaining === "00:00") {
        clearInterval(STATE.holdTimerId);
        STATE.holdTimerId = null;
        countdownEl.className = "hold-card__expired";
        countdownEl.textContent = "Hold expired";
        label.textContent = `Seats ${seats} — `;
      }
    }, 1000);
  }

  /* ── confirmation ─────────────────────────────────────── */
  if (reply.confirmation) {
    hasContent = true;
    const c = reply.confirmation;
    const card = document.createElement("div");
    card.className = "confirmation-card";
    card.setAttribute("role", "region");
    card.setAttribute("aria-label", "Booking confirmation — review before paying");

    const title = document.createElement("div");
    title.className = "confirmation-card__title";
    title.textContent = c.event_title || "Your booking";

    const makeRow = (label, value) => {
      const row = document.createElement("div");
      row.className = "confirmation-card__row";
      const l = document.createElement("span");
      l.textContent = label;
      const v = document.createElement("span");
      v.textContent = value;
      row.appendChild(l);
      row.appendChild(v);
      return row;
    };

    card.appendChild(title);
    if (c.when)  card.appendChild(makeRow("When",  formatDate(c.when)));
    if (c.venue) card.appendChild(makeRow("Venue", c.venue));
    if (c.seats && c.seats.length) card.appendChild(makeRow("Seats", c.seats.join(", ")));
    if (c.subtotal_sar) card.appendChild(makeRow("Subtotal", c.subtotal_sar));
    if (c.vat_sar)      card.appendChild(makeRow("VAT 15%",  c.vat_sar));

    if (c.total_sar) {
      const total = document.createElement("div");
      total.className = "confirmation-card__total";
      const tl = document.createElement("span");
      tl.textContent = "Total";
      const tv = document.createElement("span");
      tv.textContent = c.total_sar;
      total.appendChild(tl);
      total.appendChild(tv);
      card.appendChild(total);
    }

    // Live countdown on confirmation hold
    if (c.expires_at) {
      const expiry = document.createElement("div");
      expiry.className = "confirmation-card__expires";
      expiry.textContent = `Hold expires in ${countdown(c.expires_at)}`;
      card.appendChild(expiry);

      if (STATE.confirmTimerId) clearInterval(STATE.confirmTimerId);
      STATE.confirmTimerId = setInterval(() => {
        const rem = countdown(c.expires_at);
        expiry.textContent = rem === "00:00"
          ? "Hold expired — please restart"
          : `Hold expires in ${rem}`;
        if (rem === "00:00") {
          clearInterval(STATE.confirmTimerId);
          STATE.confirmTimerId = null;
        }
      }, 1000);
    }

    // Action buttons (HUMAN-IN-THE-LOOP gate)
    const actions = document.createElement("div");
    actions.className = "confirmation-card__actions";

    const confirmBtn = document.createElement("button");
    confirmBtn.className = "btn-confirm";
    confirmBtn.textContent = "✅ Confirm & pay";
    confirmBtn.setAttribute("aria-label", "Confirm booking and proceed to payment");
    confirmBtn.addEventListener("click", () => handleUserMessage("confirm"));

    const cancelBtn = document.createElement("button");
    cancelBtn.className = "btn-cancel";
    cancelBtn.textContent = "Cancel";
    cancelBtn.setAttribute("aria-label", "Cancel booking");
    cancelBtn.addEventListener("click", () => handleUserMessage("cancel"));

    actions.appendChild(confirmBtn);
    actions.appendChild(cancelBtn);
    card.appendChild(actions);

    frag.appendChild(card);
  }

  /* ── payment ──────────────────────────────────────────── */
  if (reply.payment) {
    hasContent = true;
    const p = reply.payment;
    const card = document.createElement("div");
    card.className = "payment-card";
    card.setAttribute("role", "region");
    card.setAttribute("aria-label", "Payment");

    const total = document.createElement("div");
    total.className = "payment-card__total";
    total.textContent = `Total: ${p.total_sar}`;

    const payBtn = document.createElement("button");
    payBtn.className = "btn-pay";
    payBtn.textContent = "Pay now (sandbox)";
    payBtn.setAttribute("aria-label", "Complete sandbox payment");

    payBtn.addEventListener("click", async () => {
      payBtn.disabled = true;
      payBtn.textContent = "Processing…";
      try {
        const result = await payBooking(p.booking_id);
        // result.ticket from POST /v1/pay
        renderTicketBubble(result.ticket);
      } catch (err) {
        appendAgentBubble(`Payment failed: ${err.message}`);
      }
    });

    card.appendChild(total);
    card.appendChild(payBtn);
    frag.appendChild(card);
  }

  return hasContent ? frag : null;
}

/**
 * Render a paid ticket as a celebratory agent bubble + ticket card.
 * @param {object} ticket — { booking_id, event_title, seats, total_sar, email, qr_url }
 */
function renderTicketBubble(ticket) {
  // Celebratory text bubble
  appendAgentBubble("🎉 Payment confirmed — here's your ticket!");

  const list = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "msg msg--agent";

  const card = document.createElement("div");
  card.className = "ticket-card";
  card.setAttribute("role", "region");
  card.setAttribute("aria-label", "Your ticket");

  const header = document.createElement("div");
  header.className = "ticket-card__header";
  header.textContent = ticket.event_title || "Your Event";

  const body = document.createElement("div");
  body.className = "ticket-card__body";

  const makeRow = (label, value) => {
    const row = document.createElement("div");
    row.className = "ticket-card__row";
    const l = document.createElement("span");
    l.textContent = label;
    const v = document.createElement("span");
    v.textContent = value;
    row.appendChild(l);
    row.appendChild(v);
    return row;
  };

  if (ticket.seats && ticket.seats.length) {
    body.appendChild(makeRow("Seats", ticket.seats.join(", ")));
  }
  if (ticket.email) {
    body.appendChild(makeRow("Email", ticket.email));
  }
  if (ticket.booking_id) {
    body.appendChild(makeRow("Booking ID", String(ticket.booking_id)));
  }

  if (ticket.total_sar) {
    const total = document.createElement("div");
    total.className = "ticket-card__total";
    const tl = document.createElement("span");
    tl.textContent = "Total paid";
    const tv = document.createElement("span");
    tv.textContent = ticket.total_sar;
    total.appendChild(tl);
    total.appendChild(tv);
    body.appendChild(total);
  }

  card.appendChild(header);
  card.appendChild(body);

  // QR code image
  if (ticket.qr_url) {
    const qr = document.createElement("img");
    qr.src = ticket.qr_url;
    qr.alt = "Ticket QR code";
    qr.className = "ticket-card__qr";
    card.appendChild(qr);

    const dl = document.createElement("a");
    dl.href = ticket.qr_url;
    dl.download = `ticket-${ticket.booking_id || "qr"}.png`;
    dl.className = "ticket-card__download";
    dl.textContent = "⬇ Download QR";
    dl.setAttribute("aria-label", "Download QR code image");
    card.appendChild(dl);
  }

  wrap.appendChild(card);
  list.appendChild(wrap);
  scrollToBottom();
}

/* ─────────────────────────────────────────────────────────────
   SUGGESTIONS BAR
───────────────────────────────────────────────────────────── */

/**
 * Re-render the quick-reply chips above the composer input.
 * @param {string[]} suggestions
 */
function renderSuggestions(suggestions) {
  const bar = document.getElementById("suggestions-bar");
  bar.innerHTML = "";
  if (!suggestions || suggestions.length === 0) return;

  suggestions.forEach((text) => {
    const chip = document.createElement("button");
    chip.className = "suggestion-chip";
    chip.textContent = text;
    chip.setAttribute("aria-label", `Quick reply: ${text}`);
    chip.addEventListener("click", () => handleUserMessage(text));
    bar.appendChild(chip);
  });
}

/* ─────────────────────────────────────────────────────────────
   CORE SEND FLOW
───────────────────────────────────────────────────────────── */

/**
 * Unified entry point for all user-initiated messages:
 * - Typed text, chip clicks, card buttons, category selects, confirm/cancel.
 * @param {string} message
 * @param {boolean} [silent=false]  If true, skip the user bubble (used for greeting).
 */
async function handleUserMessage(message, silent = false) {
  if (STATE.sending) return;
  if (!message.trim()) return;

  // Clear suggestions while agent is responding
  renderSuggestions([]);

  if (!silent) {
    appendUserBubble(message);
  }

  // Clear input
  const input = document.getElementById("chat-input");
  input.value = "";
  setSendEnabled(false);

  showTyping();
  STATE.sending = true;
  setAgentStatus("Thinking…");

  try {
    const reply = await sendChat(message);
    removeTyping();
    appendAgentBubble(reply.reply, reply);

    // Update suggestion chips
    if (reply.suggestions && reply.suggestions.length > 0) {
      renderSuggestions(reply.suggestions);
    }

    setAgentStatus("Ready");
  } catch (err) {
    removeTyping();
    appendAgentBubble(`Sorry, something went wrong: ${err.message}. Please try again.`);
    setAgentStatus("Ready");
  } finally {
    STATE.sending = false;
    setSendEnabled(true);
    input.focus();
  }
}

/** Update the status dot text in the chat header. */
function setAgentStatus(text) {
  const el = document.getElementById("agent-status");
  if (el) el.textContent = text;
}

/** Enable / disable the send button. */
function setSendEnabled(enabled) {
  const btn = document.getElementById("chat-send");
  const inp = document.getElementById("chat-input");
  if (btn) btn.disabled = !enabled || !inp.value.trim();
}

/* ─────────────────────────────────────────────────────────────
   CHAT PANEL OPEN / CLOSE
───────────────────────────────────────────────────────────── */

function openChat() {
  STATE.chatOpen = true;
  const panel   = document.getElementById("chat-panel");
  const launcher = document.getElementById("chat-launcher");
  const badge    = document.getElementById("chat-badge");

  panel.classList.remove("hidden");
  launcher.setAttribute("aria-expanded", "true");
  badge.classList.remove("visible");

  // Focus the input for keyboard users
  setTimeout(() => document.getElementById("chat-input")?.focus(), 80);
}

function closeChat() {
  STATE.chatOpen = false;
  const panel    = document.getElementById("chat-panel");
  const launcher = document.getElementById("chat-launcher");

  panel.classList.add("hidden");
  launcher.setAttribute("aria-expanded", "false");
  launcher.focus();
}

function toggleChat() {
  if (STATE.chatOpen) closeChat();
  else openChat();
}

/* ─────────────────────────────────────────────────────────────
   EVENTS GRID
───────────────────────────────────────────────────────────── */

/**
 * Fetch events and render the "What's on" grid.
 * Falls back gracefully to an error state.
 */
async function loadEventsGrid() {
  const grid      = document.getElementById("events-grid");
  const countEl   = document.getElementById("events-count");

  try {
    const events = await fetchEvents();

    // Clear skeletons
    grid.innerHTML = "";

    if (!events || events.length === 0) {
      const empty = document.createElement("div");
      empty.className = "events-empty";
      empty.setAttribute("role", "status");
      empty.innerHTML = `<div class="events-empty__icon">🎭</div>
        <p>No events found. Start the server and seed the database.</p>`;
      grid.appendChild(empty);
      return;
    }

    countEl.textContent = `${events.length} event${events.length !== 1 ? "s" : ""}`;

    events.forEach((ev) => {
      grid.appendChild(buildEventCard(ev));
    });

  } catch (err) {
    grid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "events-empty";
    empty.setAttribute("role", "alert");
    empty.innerHTML = `<div class="events-empty__icon">⚠️</div>
      <p>Could not load events: <strong>${err.message}</strong>.<br/>
      Make sure the API server is running.</p>`;
    grid.appendChild(empty);
  }
}

/**
 * Build a single event card DOM element.
 * @param {object} ev — EventOut
 * @returns {HTMLElement}
 */
function buildEventCard(ev) {
  const article = document.createElement("article");
  article.className = "event-card";
  article.setAttribute("role", "listitem");
  article.setAttribute("aria-label", ev.title);

  /* Poster (gradient header with overlaid title) */
  const poster = document.createElement("div");
  poster.className = "event-card__poster";
  poster.style.background = posterGradient(ev.id);

  const titleOverlay = document.createElement("div");
  titleOverlay.className = "event-card__title-overlay";
  titleOverlay.textContent = ev.title;

  poster.appendChild(titleOverlay);

  /* Body */
  const body = document.createElement("div");
  body.className = "event-card__body";

  const meta = document.createElement("div");
  meta.className = "event-card__meta";

  const venue = document.createElement("span");
  venue.textContent = ev.venue || "TBA";

  const dot = document.createElement("span");
  dot.className = "event-card__dot";
  dot.setAttribute("aria-hidden", "true");

  const city = document.createElement("span");
  city.textContent = ev.city || "";

  meta.appendChild(venue);
  if (ev.city) {
    meta.appendChild(dot);
    meta.appendChild(city);
  }

  const date = document.createElement("div");
  date.className = "event-card__date";
  date.textContent = formatDate(ev.starts_at);

  /* Footer (price + book button) */
  const footer = document.createElement("div");
  footer.className = "event-card__footer";

  const price = document.createElement("div");
  price.className = "event-card__price";
  price.textContent = ev.status === "cancelled" ? "Cancelled" : "View pricing";

  const bookBtn = document.createElement("button");
  bookBtn.className = "btn-book";
  bookBtn.textContent = "Book";
  bookBtn.setAttribute("aria-label", `Book ${ev.title}`);
  bookBtn.addEventListener("click", () => {
    openChat();
    // Small delay so the panel animation plays before message appears
    setTimeout(() => handleUserMessage(`#${ev.id}`), 120);
  });

  footer.appendChild(price);
  if (ev.status !== "cancelled") footer.appendChild(bookBtn);

  body.appendChild(meta);
  body.appendChild(date);
  body.appendChild(footer);

  article.appendChild(poster);
  article.appendChild(body);

  return article;
}

/* ─────────────────────────────────────────────────────────────
   BOOT / INIT
───────────────────────────────────────────────────────────── */

async function init() {
  /* 1. Wire chat open/close */
  document.getElementById("chat-launcher").addEventListener("click", toggleChat);
  document.getElementById("chat-close").addEventListener("click", closeChat);

  // Hero CTA → open chat
  document.getElementById("hero-cta").addEventListener("click", () => openChat());

  /* 2. Wire composer send */
  const input   = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");

  input.addEventListener("input", () => {
    sendBtn.disabled = !input.value.trim() || STATE.sending;
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) {
        handleUserMessage(input.value.trim());
      }
    }
  });

  sendBtn.addEventListener("click", () => {
    if (!sendBtn.disabled) {
      handleUserMessage(input.value.trim());
    }
  });

  /* 3. Keyboard: Escape closes chat */
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && STATE.chatOpen) closeChat();
  });

  /* 4. Create session */
  try {
    STATE.sessionId = await createSession();
  } catch (err) {
    console.warn("Session creation failed:", err.message);
    // Generate a client-side fallback id so UI still works for display
    STATE.sessionId = `local-${Date.now()}`;
  }

  /* 5. Show static greeting bubble (no API call needed) */
  appendAgentBubble(
    "Hello! I'm your Booking Assistant 👋\n\n" +
    "I can help you find events, check pricing, select seats, and book tickets.\n\n" +
    "Tell me what you're looking for, or click any event below to get started.",
    {
      suggestions: ["Show me all events", "Coldplay tickets", "Family events in Riyadh"],
    }
  );

  /* 6. Load events grid */
  await loadEventsGrid();
}

/* ─────────────────────────────────────────────────────────────
   ENTRY POINT
───────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", init);
