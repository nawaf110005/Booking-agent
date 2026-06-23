# AI Event-Ticket Booking Agent — Full Project Requirements (Agentic AI Bootcamp)

Project codename: **Tazkara** · A chat-first AI concierge for booking live-event tickets in Saudi Arabia.

---

## 1. Business Context

### Client
A live-events promoter, venue operator, ticketing startup, or experience platform in Saudi Arabia that sells tickets for concerts, sports, theatre, comedy, conferences, and festivals — and wants to make buying a ticket as easy as sending a message.

### Industry
Live events / ticketing / e-commerce checkout automation / conversational commerce.

### Why This Problem Matters
Buying event tickets online is slow and high-friction, and a lot of revenue is lost at checkout:

- Users hunt through catalogs, filters, and event pages to find one show
- Member/loyalty discounts are buried five clicks deep and often missed
- Seat selection is a clunky zoom-and-pan map
- Carts time out, seats get double-sold, or two buyers grab the same seat
- Checkout is a multi-step form (account → seats → quote → pay)
- Most of the funnel is abandoned before payment

Big ticketing platforms are powerful but generic, ad-heavy, and not conversational.

This project builds a **headless AI ticketing concierge** that lets a person go from *"I want to see Coldplay"* to a **signed QR ticket in their inbox** in a single natural-language conversation — search, member discount, seat selection, hold, confirmation, payment, and fulfilment, all in chat.

---

## 2. Problem Statement

Ticket buyers and operators face these pain points:

- Finding the right event takes too many clicks and filters
- Member discounts and ticket caps aren't applied automatically
- Quotes (base price + discount + VAT) are opaque and sometimes wrong to the halala
- Seat maps are hard to use and don't show where you'll actually sit
- Two buyers can race for the same seat (no atomic reservation)
- Holds expire silently and lose the user's place
- Checkout is a form marathon, so people drop off
- No clear human confirmation step before money moves
- Tickets are easy to forge without tamper-evidence

Traditional ticketing requires users to click through pages, modals, and forms.

We need an agent that:

> **Listens → Finds the event → Identifies the member → Quotes exactly → Shows seats → Holds atomically → Confirms (human-in-the-loop) → Takes payment → Delivers a signed ticket**

---

## 3. Project Objectives

The system should:

- Let users find and book event tickets entirely through chat (or voice, as a stretch)
- Understand messy, natural, possibly misspelled requests ("4 gold for cold play in riyadh")
- Identify the buyer by email and apply their membership tier discount and ticket cap automatically
- Produce exact, itemised quotes (base + member discount + 15% VAT) with no floating-point drift
- Present a live, interactive seat map and let users pick seats and switch sections
- Hold seats atomically for a fixed time window (all-or-nothing, no double-booking)
- Always ask for explicit human confirmation before issuing any payment
- Take payment and deliver a tamper-evident QR ticket
- Answer questions about events, pricing, membership, venues, and policies
- Suggest similar/relevant events when the exact request isn't available
- Personalize the experience (name, tier, interests, past bookings, sentiment)
- Keep working (book end-to-end) even with no LLM key, via a deterministic fallback

---

## 4. Target Users

### Primary Users
- Concert-goers and sports fans
- Members / loyalty cardholders (tiered discounts)
- Casual browsers ("what's on this weekend?")
- Group buyers (friends/family booking multiple seats)
- Mobile-first users who'd rather chat than fill forms

### Internal Users
- Event operators / promoters (catalog + inventory)
- Venue / box-office staff
- Finance/ops (VAT-exact revenue, audit trail)
- Support teams (booking history, hold/seat status)

---

## 5. Agentic AI Use Case

This is not a simple booking form.

The agent must:

- Understand a free-form ticketing request from natural language
- Disambiguate which event the user means (e.g. Coldplay Riyadh vs Coldplay Jeddah)
- Resolve typos/spacing ("cold play", "coldpaly") to the right event
- Decide what slot is still missing (event, email, category, quantity, seats) and ask for it
- Look up membership and apply the correct discount + ticket cap
- Compute an exact quote and explain it
- Choose seats and hold them atomically with a time limit
- Summarize the order and **wait for explicit approval before charging**
- Create the booking, take payment, and issue a signed QR ticket
- Answer side questions (parking, refunds, payment, membership) without losing the booking
- Recommend similar events when the requested one isn't available

**Example user input:**

```
I want 4 Gold tickets for Coldplay in Riyadh, my email is nawaf@example.com
```

**The agent should extract / resolve:**

- Event: Coldplay — Music of the Spheres (Riyadh)
- Buyer email: nawaf@example.com → membership tier (e.g. Platinum, 15% off, up to 8 tickets)
- Category: Gold
- Quantity: 4 (validated against the tier's ticket cap)
- Quote: base × 4 − member discount + 15% VAT = exact total in halalas
- Next step: show the Gold seat map and ask for 4 seats
- Then: place a 10-minute atomic hold → confirm → pay → QR ticket

---

## 6. Agent Roles & Responsibilities

### MVP: Single-Agent System

| Component | Responsibility |
|---|---|
| Booking Agent | Understands the request, fills slots (event → email → category → quantity → seats), quotes exactly, shows the seat map, places an atomic hold, gets human confirmation, takes payment, and issues the ticket |

### Recommended Multi-Agent System

| Agent | Responsibility |
|---|---|
| Conversation / Intake Agent | Interprets messages, extracts slots and intent, handles chit-chat and Q&A |
| Catalog Agent | Searches events, disambiguates, and recommends similar events |
| Pricing Agent | Computes exact quotes (member discount + VAT) and enforces ticket caps |
| Seat & Hold Agent | Renders the seat map and places/releases atomic, time-bounded holds |
| Payment & Fulfilment Agent | Creates the booking after confirmation, takes payment, issues the signed QR ticket |
| Personalization Agent | Tracks interests/history/sentiment and tailors recommendations and tone |

---

## 7. RAG / Knowledge Base

### Knowledge Sources
- Venue information (Kingdom Arena, Jeddah Superdome, etc.)
- Parking, gates/doors, and entry rules
- Accessibility / wheelchair seating
- Prohibited items and security policy
- Age / family policy
- Refund and cancellation policy
- Payment methods and the checkout/sandbox flow
- Membership tiers, discounts, and ticket caps
- Event descriptions and line-ups

### Usage
RAG / knowledge retrieval is used when:

- Answering venue/policy questions (parking, gates, accessibility, prohibited items)
- Explaining membership, discounts, VAT, or how booking works
- Explaining payment and refunds
- Grounding the assistant's answers so it never invents a policy
- Recommending similar events by type/genre when the exact event isn't available

> Retrieval must use a **relevance threshold** so a single coincidental word never returns an unrelated answer (e.g. the word "here" must not return the payment policy). A vector DB (Chroma/FAISS) is optional; the system falls back to a stop-word-filtered token/keyword retriever so it works offline.

---

## 8. Tools & Tool Usage

### Key Principle
**Tools are Python functions — NOT separate applications.**

No external ticketing SaaS is required for the MVP. The agent calls plain, typed Python functions that read/write a small ticketing database and render assets locally. Payment runs through a virtual (sandbox) gateway.

### Tool Design Approach
Implement tools as:

- Pure, typed Python functions
- Backend modules (events, members, pricing, seatmap, holds, booking, payments, money)
- SQL / SQLAlchemy query functions
- Optional FastAPI endpoints over the same functions

### Example Booking Tools

| Tool | Purpose |
|---|---|
| `search_events(query, city, date_from, date_to)` | Find events in the catalog (with fuzzy matching) |
| `get_event_details(event_id)` | Full details for one event |
| `lookup_member_by_email(email)` | Resolve membership tier, discount, and ticket cap |
| `get_categories_with_pricing(event_id, tier)` | Seat categories with base + discounted prices |
| `compute_quote(event_id, category, quantity, tier)` | Exact itemised quote (base − discount + 15% VAT) |
| `seat_map_data(event_id, category)` | Live seat layout (available/held/sold) for the interactive map |
| `venue_layout(event_id)` | All sections by distance from the stage (VIP → Standing) |
| `render_seat_map(event_id, category)` | Rendered seat-map image (PNG) |
| `place_seat_hold(event_id, seat_ids, email)` | Atomic, all-or-nothing 10-minute hold |
| `release_expired_holds()` | Sweep and release timed-out holds |
| `create_booking_from_hold(...)` | Convert a held order into a booking (after confirmation) |
| `pay_booking(booking_id)` | Take payment via the virtual/sandbox gateway (idempotent) |
| `get_ticket_token(booking_id)` / `make_qr_png(token)` | Issue and render the HMAC-signed QR ticket |
| `compute pricing in halalas` (`tools/money.py`) | Exact integer money math (no floats) |

### Example Tool Flow: Booking a Ticket

```
User provides request
↓
extract slots (event, email, category, quantity)
↓
search_events() → disambiguate
↓
lookup_member_by_email() → tier discount + cap
↓
compute_quote() → exact total
↓
seat_map_data() / venue_layout() → user picks seats
↓
place_seat_hold() (atomic, 10-min TTL)
↓
Agent summarizes the order and asks for confirmation
↓
User approves (human-in-the-loop gate)
↓
create_booking_from_hold()
↓
pay_booking()
↓
issue HMAC-signed QR ticket
```

### Example Tool Flow: Asking About an Event

```
User asks: "Is Coldplay coming to Riyadh?"
↓
search_events()
↓
Agent answers from the live catalog:
- title, date, venue
- from-price
- offer to start booking (or suggest similar events if not found)
```

### Example Tool Flow: Answering a Policy Question

```
User asks: "Where do I park at the arena?"
↓
retrieve() over the venue/FAQ knowledge base (with relevance threshold)
↓
Agent returns the grounded parking answer (and never an unrelated policy)
```

---

## 9. Architecture

```
Chat / Voice Interface  (Next.js storefront + no-Node static site)
        ↓
FastAPI Backend  (/v1: chat, events, quote, holds, pay, seats, venue)
        ↓
Agent Orchestrator
   • multi_agent mode (default — orchestrator routes turns through role specialists:
       catalog → membership → pricing → seating, each an LLM Reason–Act–Observe tool loop)
   • tool_agent mode (single-agent alternative — one LLM loop over the full tool set)
   • Deterministic offline brain stands in for the LLM when no key is configured
        ↓
Python Ticketing Tools  (events, members, pricing, seatmap, holds, booking, payments, money)
        ↓
SQLite / PostgreSQL  (SQLAlchemy 2)
        ↓
Fulfilment (HMAC-signed QR ticket)  +  Optional Visualization Layer (seat map / charts)
```

### Frontend Requirement
A web chat UI is provided (Next.js + a no-Node static site), but React is not required for the agent itself. Acceptable interfaces include:

- Streamlit / Gradio
- Basic HTML/CSS chat
- FastAPI Swagger
- Command-line chat

---

## 10. Memory Design

### Short-Term Memory
Within the current session the agent remembers:

- The current event being booked
- Buyer email + resolved membership tier and cap
- Chosen category, quantity, and seats
- The active seat hold and its expiry timer
- The current step (greeting → email → category → quantity → seats → confirm → pay)
- Pending confirmation / approval state
- Learned interests and last-turn sentiment

### Long-Term Memory
Stored in the database:

- Events, venues, seats, and seat layouts
- Members and their tiers
- Bookings, booking items, and holds
- Payments and issued tickets
- Per-user preferences (interests) and interaction logs
- An audit log of every seat/booking state transition

### Suggested Tables

| Table | Purpose |
|---|---|
| `events` / `venues` | Catalog: title, type, city, venue, date, status |
| `seats` / `seat_layouts` | Per-event seats with category, price, and status |
| `members` | Buyer identity and membership tier |
| `bookings` / `booking_items` | Confirmed orders and their line items |
| `holds` | Active/expired atomic seat holds with TTL |
| `payments` | Payment records (idempotent) |
| `tickets` | Issued, HMAC-signed QR tickets |
| `user_preferences` / `interaction_log` | Personalization signals and history |
| `audit_log` | Observable trail of seat/booking transitions |

### Storage Options

| Memory Type | Storage |
|---|---|
| Session state | In-memory / Redis |
| Ticketing records | SQLite or PostgreSQL |
| Venue FAQ / policies | Vector DB (optional) + keyword fallback |
| Event/recommendation embeddings | Vector DB (optional) |

---

## 11. Evaluation Criteria

### Task Performance
- Correctly resolves the intended event (including typos/spacing)
- Applies the right membership discount and ticket cap
- Produces exact, correct quotes to the halala
- Places atomic holds with no double-booking
- Issues a valid, signed QR ticket after payment

### Agent Behavior
- Asks for the right missing slot, one at a time
- Never charges without explicit human confirmation
- Answers questions mid-booking without losing the flow
- Distinguishes book / browse / ask / confirm / cancel intents
- Recommends similar events when the exact one isn't available

### Tool Usage Quality
- Correct tool selection and sequence
- Safe, atomic database writes (holds and bookings)
- Accurate linking across events, members, bookings, and seats
- Validation before writing (cap, availability, expiry)

### RAG Quality
- Grounds venue/policy answers in the knowledge base
- Never returns an unrelated answer on a coincidental word match
- Suggestions are relevant to the user's request and interests

### Money & Safety Quality
- All amounts exact (integer halalas; 15% VAT; tier discount in basis points)
- All-or-nothing seat holds with a TTL
- Confirm-before-pay gate is never bypassed
- Tamper-evident (HMAC-signed) tickets

### Memory Quality
- Maintains current booking context across turns
- Tracks the hold timer and expiry correctly
- Recalls interests / past bookings for personalization

### User Experience
- Natural chat interaction from an imperfect first message
- Clear, interactive seat map with the user's section/position
- Clear confirmation summary before payment
- Fast, friendly, and works offline (deterministic fallback)

### Technical Quality
- Clean schema and modular Python tools
- Reliable FastAPI backend with typed errors → HTTP codes
- Clear separation between agent, tools, and database
- GitHub repo with documentation
- Tests for money, holds, and the booking flow

---

## 12. Deliverables

Build:

- Single booking agent (or multi-agent booking system)
- Natural-language booking workflow (search → confirm → pay → ticket)
- SQL-backed ticketing database (events, seats, members, bookings, holds, payments, tickets)
- Exact pricing engine (member discount + 15% VAT, integer math)
- Atomic, time-bounded seat-hold system
- Interactive seat map (clickable, venue-aware)
- Human-confirmation-before-payment workflow
- Virtual/sandbox payment + HMAC-signed QR ticket fulfilment
- Event/policy Q&A with retrieval
- Chat interface (web)
- FastAPI backend
- GitHub repository
- Demo

---

## 13. Stretch Goals

- Multi-agent orchestration using LangGraph (Catalog / Pricing / Hold / Payment / Fulfilment)
- Semantic/vector event search and similar-event recommendations
- Voice-based booking
- Real payment-provider webhook (signature-verified, idempotent)
- Email/SMS ticket delivery
- Personalization: learned interests, past-booking recall, sentiment-adaptive tone
- Group bookings and seat-together optimization
- Waitlists for sold-out events
- Dynamic/demand-based pricing insights for operators
- Operator dashboard (sales funnel, fill rate, revenue)
- WhatsApp / Slack-style chat interface

---

## 14. Resume Framing

### Resume Statement
Built an agentic event-ticketing concierge that turns natural-language requests into completed bookings — resolving events, applying member discounts with exact VAT math, holding seats atomically, gating payment behind human confirmation, and delivering tamper-evident QR tickets — using LLM tool-calling with a deterministic fallback, FastAPI, and SQL tools.

### Resume Bullet Points
- Designed a chat-first booking agent that fills slots (event → email → category → quantity → seats) from natural language and books end-to-end.
- Implemented an exact pricing engine (integer-halala math, member-tier discounts, 15% VAT) reproducible to the halala.
- Built atomic, time-bounded seat holds preventing double-booking under concurrency, with a TTL sweeper.
- Enforced a human-in-the-loop confirm-before-pay gate and tamper-evident HMAC-signed QR tickets.
- Built an interactive, venue-aware seat map and a retrieval-grounded event/policy Q&A with a deterministic offline fallback.

---

## 15. MVP Scope

Must include:

- Single booking agent
- Simple chat interface
- SQLite (or PostgreSQL) ticketing database
- Find and disambiguate an event from natural language
- Identify the member by email and apply discount + cap
- Exact quote (base + discount + VAT)
- Pick seats (interactive map) and place an atomic 10-minute hold
- Ask for confirmation before payment
- Take payment (virtual/sandbox) and issue a QR ticket
- Answer common event/policy questions
- Work end-to-end even with no LLM key (deterministic fallback)

### MVP Should Not Require
- Real HubSpot/Salesforce-style or third-party ticketing integrations
- A full operator web dashboard
- Complex authentication
- Voice interface
- Real money movement / live payment processor
- Email/SMS delivery infrastructure

---

## 16. Recommended Tools & Resources

### Core Tools
- Python 3.11
- FastAPI + Uvicorn
- SQLAlchemy 2 + SQLite/PostgreSQL (+ Alembic migrations)
- Pydantic / pydantic-settings
- Typer (CLI) + Rich
- Pillow (seat-map rendering) + qrcode (QR tickets)
- Next.js / Tailwind (or Streamlit / Gradio / static HTML) for the chat UI

### Optional Tools
- LangChain / LangGraph for multi-agent orchestration
- Chroma / FAISS for venue-FAQ and event RAG
- Redis for session memory
- Plotly / Matplotlib for operator charts
- ReportLab for PDF tickets
- Speech-to-text for voice input

### LLM APIs
Provider-agnostic — `anthropic` | `openai` | `nanogpt` | `google`, selected by
`BOOKING_AGENT_PROVIDER` + the matching key:

- Anthropic (Claude)
- OpenAI
- nano-gpt (OpenAI-compatible proxy) — **active config**: `gemini-2.5-flash-preview-04-17`
- Google (Gemini) — kept as a backup
- Local models via Ollama (optional)
- Deterministic offline brain when no provider is configured

---

## 17. Key Research Topics

Understand:

- Conversational commerce and chat-first checkout
- Agent slot-filling and intent detection
- Tool calling and tool design (functions, not apps)
- SQL database operations and transactional safety
- Atomic reservations / concurrency (no double-booking)
- Exact money math (minor units, VAT, discounts)
- Human-in-the-loop approval workflows
- Tamper-evident tickets (HMAC, QR)
- Agent memory (short-term session + long-term DB)
- Retrieval-augmented generation with relevance thresholds
- Multi-agent orchestration
- Personalization and recommendation

---

## Final Summary

This project demonstrates:

> Agents + Conversational Checkout + SQL Tools + Exact Money + Atomic Holds + Human Approval + Tamper-Evident Fulfilment + RAG + (Optional) Multi-Agent Workflows

---

## Suggested Project Positioning

This is a strong capstone because it feels like a practical replacement for a clunky multi-step ticketing checkout:

> A chat-first AI ticketing concierge that takes a user from "I want to see Coldplay" to a signed QR ticket in their inbox — search, member discount, live seat map, atomic hold, confirm-before-pay, and fulfilment — all in one conversation, instead of a five-step web form.
