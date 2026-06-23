# AI Event Ticket Booking Agent — Full Project Requirements (Agentic AI Bootcamp)

> Companion to [`docs/proposal.md`](docs/proposal.md) (business case + market
> research) and [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
> (the principles every feature must satisfy). This document is the full
> requirements scope, mirroring the bootcamp's instructor-version brief.

## 1. Business Context

### Client
A live-events organiser, venue, or national ticketing platform (e.g. a WeBook-,
Platinumlist-, or GEA-style operator) that sells tickets for concerts, sports,
theatre, conferences, and cultural events — and a buyer who wants to go from
"I want a ticket" to "ticket in my inbox" without fighting a multi-page checkout.

### Industry
Event ticketing / live-entertainment commerce / conversational commerce.
Saudi-first (Vision 2030, GEA, Riyadh Season, MDLBEAST, Saudi Pro League, F1),
bilingual Arabic/English, Mada / Apple Pay / STC Pay payments.

### Why This Problem Matters
Buying a ticket today is full of friction, and the friction costs money:

- Slow, multi-page checkout (find → category → seat → register → pay → confirm).
- Confusing seat maps that are unreadable on mobile.
- Member discounts buried five clicks deep, so buyers never apply them.
- Multi-ticket coordination (4 seats together) is painful.
- Payment redirects time out mid-checkout; Mada/Apple Pay support is uneven.
- **Cart abandonment in ticketing is among the highest in e-commerce (60–80%).**
- Tickets get lost in spam; QR codes fail to scan.
- Generic "popular now" carousels never learn the buyer; when a user is clearly
  frustrated, the platform re-serves the same results and the user gives up.

A chat-first agent collapses the funnel into one conversation, surfaces the
member discount automatically, holds seats atomically, and delivers a signed
ticket — in the user's own language.

## 2. Problem Statement

Event buyers and organisers face these pain points:

- Checkout is long and abandoned more than half the time.
- Seat selection is unusable on mobile.
- Member discounts are inconsistently applied at the moment of purchase.
- Buying multiple adjacent seats is clumsy and error-prone.
- Payment friction (redirects, timeouts, gateway gaps) loses sales.
- Ticket delivery is unreliable; fraud (screenshotted QR) is easy.
- Discovery ("what's on this weekend in Riyadh?") is not conversational.
- Platforms don't personalise and don't detect frustration.

Traditional ticketing forces users to click through forms and dashboards.

We need an agent that:

**Listens → Identifies event → Quotes (with member discount) → Selects seats → Holds (timer) → Confirms (HITL) → Pays → Delivers ticket.**

## 3. Project Objectives

The system should:

- Let users book one or more tickets end-to-end through natural-language chat.
- Search the events catalog from intent and disambiguate with rich event cards.
- Look up membership by email and apply the correct discount and ticket cap.
- Quote prices with base, member discount, VAT 15%, and total itemised.
- Render a seat map (available / sold / held) and accept seat IDs.
- Place an atomic, time-bounded (10-minute) seat hold with a visible expiry.
- Require explicit confirmation before issuing a payment URL (HITL).
- Generate a Moyasar sandbox payment session and process its webhook safely
  (signature-verified, idempotent).
- Generate a PDF ticket with an HMAC-signed QR code, surface it in chat, and
  email it to the buyer.
- Remember per-user preferences across sessions and weight suggestions.
- Detect user sentiment each turn and adapt strategy when frustration appears.
- Reduce checkout friction and cart abandonment.

## 4. Target Users

### Primary Users
- Event-goers booking concerts, sports, theatre, conferences, family/cultural events.
- Members of clubs / loyalty / GEA-tied programmes entitled to discounts.
- Bilingual Saudi users who code-switch Arabic/English.
- Accessibility / hands-busy users (voice — stretch).

### Internal Users
- Event organisers and venue operators (catalog + capacity).
- Support / operations teams (booking status, force-release, refunds — stretch).
- Marketing / revenue teams (which events/categories convert).

## 5. Agentic AI Use Case

This is not a search bar wrapped in chat.

The agent must:

- Understand messy, bilingual intent and map it to a concrete event.
- Disambiguate when several events match (different date/city).
- Decide what is still missing (email, quantity, category, seats) and ask.
- Look up membership and apply discount + ticket cap deterministically.
- Compute an exact quote (base + discount + VAT) and present it.
- Render a seat map and validate the chosen seats against availability.
- Place an atomic hold and track its expiry in session state.
- Pause for explicit confirmation before payment (HITL).
- Create a payment session, then resolve the booking from the webhook.
- Generate and deliver a signed ticket.
- Read per-user preferences each turn and re-rank suggestions.
- Classify sentiment each turn and switch strategy on frustration.

### Example user input

> "I want a ticket for the Coldplay show in Riyadh, 4 seats together in Gold.
> My email is nawaf@example.com."

The agent should extract:

| Field | Value |
|-------|-------|
| Intent | book_ticket |
| Event query | Coldplay |
| City | Riyadh |
| Quantity | 4 |
| Category | Gold |
| Seat preference | adjacent |
| Email | nawaf@example.com |
| Required | member lookup → quote → seat map → hold → confirm → pay |

## 6. Agent Roles & Responsibilities

### MVP: Single-Agent System

| Component | Responsibility |
|-----------|---------------|
| Booking Agent | Understands intent, searches events, looks up membership, quotes price, renders seat map, holds seats, confirms (HITL), creates payment session, resolves webhook, delivers ticket, personalises, detects sentiment |

### Recommended Multi-Agent System (stretch)

| Agent | Responsibility |
|-------|---------------|
| Intake / NLU Agent | Interprets messages (Arabic/English), extracts intent + entities, classifies sentiment |
| Catalog Agent | Event search, disambiguation, rich cards, recommendations |
| Pricing Agent | Member lookup, ticket cap, quote (base + discount + VAT) |
| Seat & Hold Agent | Seat-map render, availability check, atomic hold + TTL, sweeper |
| Payment Agent | Moyasar session, webhook verification + idempotency, booking state |
| Fulfilment Agent | PDF + HMAC QR, email, in-chat ticket card |
| Recommender Agent | Preference-weighted "what should I see this weekend?" |

## 7. RAG / Knowledge Base

### Knowledge Sources
- Venue FAQs (parking, gates, accessibility, prohibited items).
- Refund / cancellation / exchange policy.
- Transport and directions per venue.
- Event descriptions, age ratings, dress code.
- Membership-programme terms and discount rules.
- Bilingual help content (Arabic/English).

### Usage
RAG is used when:
- A user asks a policy/logistics question ("can I get a refund?", "where do I park?").
- The agent needs venue/accessibility facts to answer mid-booking.
- Generating consistent, grounded answers instead of hallucinating policy.
- (Stretch) grounding recommendations in event descriptions.

## 8. Tools & Tool Usage

### Key Principle
Tools are Python functions — NOT separate applications. No WeBook / Ticketmaster
integration for the MVP. The one external service is the **payment gateway**
(Moyasar sandbox), isolated behind a single adapter with a fake for tests.

### Tool Design Approach
Implement tools as typed Python functions / backend modules / SQL query
functions, optionally exposed as FastAPI endpoints.

### Core Booking Tools

| Tool | Purpose |
|------|---------|
| `search_events(query, city?, date?)` | Find matching events in the catalog |
| `get_event_details(event_id)` | Full event record for a card |
| `render_event_card(event_id)` | Inline card (image + date + venue + URL) |
| `lookup_member_by_email(email)` | Membership tier + discount + cap |
| `get_ticket_cap(tier)` | Max tickets per booking for a tier |
| `get_categories_with_pricing(event_id, tier?)` | Category prices + discounted prices |
| `compute_quote(event_id, category, qty, tier?)` | Base + discount + VAT 15% + total |
| `render_seat_map(event_id, category)` | PNG seat map (available/sold/held) |
| `check_seat_availability(event_id, seat_ids)` | Are these seats free right now? |
| `place_seat_hold(event_id, seat_ids, email)` | Atomic hold + 10-min TTL → token + expiry |
| `release_seat_hold(hold_id)` | Release a hold (manual or by sweeper) |
| `create_booking(...)` | Persist a held booking + items |
| `create_payment_session(booking_id)` | Moyasar checkout URL + session id |
| `handle_payment_webhook(payload, signature)` | Verify + idempotent → mark paid |
| `generate_ticket_pdf(booking_id)` | PDF with HMAC-signed QR |
| `send_ticket_email(booking_id)` | Email the PDF to the buyer |
| `get_booking_status(booking_id)` | Poll booking/payment status |
| `get_user_preferences(email)` | Read per-user preference profile |
| `update_user_preferences(email, ...)` | Update profile after a booking/rejection |
| `recommend_events(email, context)` | Preference-weighted suggestions |
| `classify_sentiment(message, history)` | engaged / neutral / frustrated |

### Example Tool Flow: Booking a Ticket

```
User: "Coldplay, Riyadh, 4 Gold seats, nawaf@example.com"
        ↓
search_events()  →  (disambiguate if needed)
        ↓
lookup_member_by_email()  →  tier, discount, cap
        ↓
get_categories_with_pricing()  →  compute_quote()
        ↓
render_seat_map()  →  user picks G12–G15
        ↓
check_seat_availability()  →  place_seat_hold()  (10-min TTL)
        ↓
HITL confirmation summary  →  user approves
        ↓
create_payment_session()  →  payment URL
        ↓ (webhook, server-to-server)
handle_payment_webhook()  →  mark paid (idempotent)
        ↓
generate_ticket_pdf()  →  send_ticket_email()  →  in-chat ticket card
```

### Example Tool Flow: Asking a Policy Question

```
User: "Can I get a refund if I can't make it?"
        ↓
rag_search("refund policy", venue)
        ↓
Agent answers grounded in docs/venue-faq/*, with the policy quoted
```

### Example Tool Flow: Discovery + Personalisation

```
User: "What's on this weekend?"
        ↓
get_user_preferences(email)  →  past: 2× football, 1× rock concert
        ↓
recommend_events()  →  weighted suggestions (sports + music first)
        ↓
classify_sentiment()  →  if "frustrated", widen the net / change category
```

## 9. Architecture

```
   Chat Interface (Streamlit / Gradio / CLI)
                 |
            FastAPI Backend
                 |
    Agent Orchestrator (LangChain → LangGraph stretch)
                 |
   +-------------+-------------+-------------+-------------+
   |             |             |             |             |
 Booking      Pricing      Seat-map      Payment      Fulfilment
  Tools        Tools       Renderer      (Moyasar)    (PDF/QR/Email)
   |             |             |             |             |
   +-------------+-------------+-------------+-------------+
                 |
          SQLite / PostgreSQL
   (events, venues, seats, members, bookings,
    booking_items, holds, payments, tickets,
    audit_log, user_preferences, interaction_log)
                 |
        Background hold-sweeper  +  optional RAG (venue FAQ)
```

### Frontend Requirement
React/Next.js is NOT required. Streamlit (MVP — must render inline images for
event cards, seat maps, and ticket cards), Gradio, FastAPI Swagger, or a CLI
chat are acceptable.

## 10. Memory Design

### Short-Term Memory (session)
- Current event in focus.
- Current cart: category, quantity, selected seats.
- Active hold: seat IDs + expiry timestamp.
- Pending approval state (awaiting confirmation before payment).
- Payment session id, last error.
- Rolling sentiment over the last N turns.

### Long-Term Memory (database)
- Events catalog, venues, seat layouts, per-event seats.
- Members (email → tier, discount, cap).
- Bookings, booking_items, holds, payments, tickets.
- Audit log of state transitions.
- Per-user preferences (categories, venues, price band, rejected categories, language).
- Interaction log (per-turn message, intent, sentiment, tools called).

### Suggested Tables

| Table | Purpose |
|-------|---------|
| `events` | title, datetime, venue_id, image_url, detail_url, status |
| `venues` | name, city, capacity, layout reference |
| `seat_layouts` | per-venue grid (sections, rows, seat IDs) |
| `seats` | per-event seat: event_id, seat_id, category, base_price, status |
| `members` | email (key), tier, discount_pct, ticket_cap |
| `bookings` | buyer_email, event_id, status, subtotal, discount, vat, total |
| `booking_items` | booking_id, seat_id, unit_price, discount_applied, vat |
| `holds` | booking_id, event_id, seat_id, expires_at |
| `payments` | booking_id, gateway, session_id, status, idempotency_key, signature_verified |
| `tickets` | booking_id, pdf_path, qr_token (HMAC), issued_at, emailed_at |
| `audit_log` | append-only state transitions |
| `user_preferences` | email, preferred/rejected categories, venues, price band, language |
| `interaction_log` | session_id, turn, user_msg, agent_msg, intent, sentiment, tools |

### Membership-Aware Ticket Cap (defaults)

| Tier | Discount | Max tickets / booking |
|------|----------|------------------------|
| (Non-member) | 0% | 4 |
| Bronze | 5% | 4 |
| Silver | 10% | 6 |
| Gold | 12% | 6 |
| Platinum | 15% | 8 |

### Storage Options

| Memory Type | Storage |
|-------------|---------|
| Session state | In-memory / Redis |
| Operational records | SQLite or PostgreSQL |
| Hold TTLs | `holds` table + sweeper (or Redis SETNX+TTL) |
| Venue FAQ / policy | Vector DB (Chroma/FAISS) or in-memory BM25 |

## 11. Evaluation Criteria

### Task Performance
- Books one or more tickets end-to-end on scripted scenarios.
- Disambiguates ambiguous events correctly.
- Applies the right discount and ticket cap per tier.
- Quote math correct across tiers and quantities (incl. VAT).

### Agent Behavior
- Asks for missing info (email, quantity, category, seats) instead of guessing.
- NEVER issues a payment URL without explicit confirmation (HITL).
- Refuses politely when quantity exceeds the tier cap.
- Picks the right tool for the intent (book vs ask vs discover).

### Tool Usage Quality
- Atomic holds; two requests cannot hold the same seat (concurrency safety).
- Webhook is signature-verified and idempotent (duplicate → exactly one ticket).
- Safe DB writes; bookings/holds/payments stay consistent.

### RAG Quality
- Policy/logistics answers are grounded in venue docs, not hallucinated.

### Memory Quality
- Maintains cart + hold + approval state within a session.
- Returning users see preference-weighted suggestions, not a flat catalog.

### User Experience
- One conversation, < 2 minutes to ticket.
- Inline event cards, seat map, and ticket card render in chat.
- Bilingual (Arabic/English code-switching) parsed correctly.

### Personalisation & Sentiment
- Preference-weighted suggestions improve relevance vs a flat catalog.
- Sentiment is classified (engaged/neutral/frustrated) accurately on a labelled set.
- On detected frustration, the agent visibly changes strategy.

### Technical Quality
- Clean schema; modular Python tools; reliable FastAPI backend.
- Clear separation between agent, tools, fulfilment, and database.
- GitHub repo with docs; tests for tools, quote math, holds, webhook idempotency.
- Demo reproducible from a clean clone with one command (Moyasar sandbox).

## 12. Deliverables

- Booking agent (single-agent MVP; multi-agent optional).
- Natural-language booking workflow (search → quote → seat → hold → confirm → pay → ticket).
- SQL-backed schema (events, venues, seats, members, bookings, items, holds, payments, tickets, prefs, logs).
- Atomic seat-hold system with TTL + sweeper.
- HITL confirmation-before-payment workflow.
- Moyasar sandbox payment session + signature-verified, idempotent webhook.
- PDF ticket with HMAC-signed QR + email delivery + in-chat ticket card.
- Seat-map image renderer.
- Preference learning + sentiment detection.
- Chat interface (Streamlit) + FastAPI backend.
- GitHub repository + documentation + demo.

## 13. Stretch Goals

- LangGraph multi-agent orchestration (Catalog / Pricing / Hold / Payment / Fulfilment / Recommender).
- Voice booking (Whisper speech-to-text).
- WhatsApp Business API channel (forward a poster, book in-thread).
- Group-seating adjacency optimiser.
- Refund / cancellation / exchange flow.
- Waitlist for sold-out events.
- Arabic-first prompt pack.
- Calendar invite (.ics) attachment.
- Human-support handoff on persistent frustration.
- Dynamic-pricing assistant for organisers.

## 14. Resume Framing

### Resume Statement

> Built an agentic event-ticket booking concierge that takes a user from
> natural-language intent to a paid, emailed ticket in one chat — handling
> event search, member-discount pricing, visual seat selection, atomic
> time-bounded seat holds, human-in-the-loop payment confirmation, gateway
> webhooks, and HMAC-signed QR tickets, using LLMs, SQL tools, and
> personalisation + sentiment adaptation.

### Resume Bullet Points

- Designed a conversational booking agent that maps bilingual intent to events,
  seats, members, bookings, payments, and tickets via typed Python tools.
- Implemented atomic, TTL-bounded seat holds guaranteeing no double-sold seat
  under concurrency, with a background expiry sweeper.
- Built an HITL confirmation gate and a signature-verified, idempotent payment
  webhook so duplicate deliveries produce exactly one ticket.
- Generated tamper-evident PDF tickets with server-signed HMAC QR codes and
  automated email delivery.
- Added per-user preference learning and per-turn sentiment detection that
  re-ranks suggestions and adapts strategy when users are frustrated.

## 15. MVP Scope

### Must include
- Single booking agent + chat interface (Streamlit).
- SQLite/PostgreSQL schema seeded with a multi-event catalog.
- Event search + disambiguation from natural language.
- Email-based member lookup → discount + ticket cap.
- Category pricing + quote (base + discount + VAT 15% + total).
- Seat-map render + seat selection.
- Atomic seat hold with 10-minute TTL.
- HITL confirmation before payment.
- Moyasar sandbox payment session + webhook (verified + idempotent).
- PDF + HMAC QR ticket + email + in-chat ticket card.
- Preference-weighted suggestions + sentiment detection.

### MVP Should Not Require
- Real-money payments or production gateway.
- Secondary-market resale / dynamic pricing.
- Full web CRM dashboard / React frontend.
- Voice or WhatsApp channels.
- Complex authentication / multi-tenant org management.

## 16. Recommended Tools & Resources

### Core Tools
- Python 3.11+, FastAPI, LangChain (→ LangGraph stretch), SQLAlchemy 2 + Alembic.
- SQLite / PostgreSQL, Streamlit (or Gradio).

### Booking-Specific
- Moyasar (sandbox) — Mada / Apple Pay / STC Pay.
- Pillow (seat map + ticket image), `qrcode` (HMAC payload), ReportLab / WeasyPrint (PDF).
- SMTP / SendGrid / Resend for email.
- Redis (optional) for hold TTLs and session state.

### Optional / Stretch
- Chroma / FAISS / BM25 (venue FAQ RAG).
- Whisper (voice), WhatsApp Business API, `.ics` generator.

### LLM APIs
- OpenAI, Anthropic, Gemini; Ollama optional offline.

## 17. Key Research Topics

- Event/seat data models and venue layouts.
- Tool calling & structured extraction.
- Concurrency & atomic seat reservations (row locks / Redis SETNX / TTL).
- Human-in-the-loop approval workflows.
- Payment gateways, webhooks, signature verification, idempotency.
- Ticket fraud prevention (HMAC-signed QR).
- Agent memory (session + persistent preferences).
- Recommendation / preference weighting.
- Sentiment classification and adaptive dialogue strategy.
- Bilingual (Arabic/English) NLU and VAT/ZATCA + PDPL compliance.
- Multi-agent orchestration (LangGraph).

## Final Summary

This project demonstrates:

**Agents + Conversational Commerce + SQL Tools + Atomic Reservations + Human Approval + Payments/Webhooks + Signed Tickets + Personalisation + Sentiment Adaptation**

### Suggested Project Positioning

> An AI concierge for live events in Saudi Arabia: ask in Arabic or English,
> get personalised suggestions, pick your seat from a live map, get your member
> discount applied automatically, confirm, pay via Mada, and receive a signed
> ticket in your inbox — all in one conversation.
