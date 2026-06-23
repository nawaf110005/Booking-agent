<!--
SYNC IMPACT REPORT
Version change: 0.0.0 → 1.0.0 (initial ratification)
Modified principles: (none — initial set)
Added sections:
  - Core Principles (8 principles)
  - Security, Privacy & Compliance
  - Technology Constraints
  - Development Workflow
  - Governance
Removed sections: (none)
Templates requiring updates:
  - .specify/templates/plan-template.md ⚠ pending (Constitution Check section references these principles by name; verify on next /speckit-plan run)
  - .specify/templates/spec-template.md ⚠ pending (clarify/approval steps align — verify on next /speckit-specify)
  - .specify/templates/tasks-template.md ⚠ pending (Test-First task ordering should be enforced — verify on next /speckit-tasks)
  - CLAUDE.md ✅ (pointer file, no changes needed)
Deferred TODOs: (none)
-->

# Booking-Agent Constitution

Booking-Agent is a headless AI event-ticket booking concierge. In one chat
thread it takes a user from intent ("I want a ticket for the Coldplay show")
to a confirmed, paid, emailed ticket — searching the catalog, applying member
discounts, rendering a seat map, holding seats atomically, confirming before
payment, redirecting to Moyasar, and delivering a signed PDF/QR ticket. The
constitution below governs what the project will and will not do. It is the
source of truth for downstream specs, plans, and tasks.

## Core Principles

### I. Confirmation Before Payment (NON-NEGOTIABLE)

The agent MUST present a structured booking summary — event, date, venue,
seats, base price, member discount, VAT (15%), total, and hold expiry — and
obtain explicit user approval before it creates a payment session or issues a
payment URL. No payment link is generated without that approval.

**Rationale.** Charging the wrong amount, the wrong seats, or the wrong event
is the most damaging failure this product can have. The bootcamp brief grades
human-in-the-loop (HITL) confirmation as a mandatory design requirement, and
Saudi PDPL/consumer expectations demand explicit consent before a financial
action. Removing this gate changes the product's category.

### II. Atomic, Time-Bounded Seat Holds (NON-NEGOTIABLE)

A seat hold MUST be all-or-nothing (either every requested seat is held or
none are), MUST carry a fixed TTL (10 minutes), and MUST guarantee that no two
bookings ever hold or confirm the same seat for the same event. Expired holds
are released by a sweeper and the seats returned to `available`.

**Rationale.** Double-selling a seat destroys trust instantly and is
unrecoverable at the door. Atomic holds with a visible timer are the
industry-standard mechanism and an explicit evaluation criterion
(concurrency safety: two users cannot hold the same seat).

### III. Tools Are Python Functions

Every capability the agent uses MUST be implemented as a typed Python function
in this repository — not a third-party ticketing SaaS. The function signature
and docstring are the contract; the agent reasons over signatures, not
internals. The one permitted external dependency is the **payment gateway**
(Moyasar sandbox), which MUST be isolated behind a single tool/adapter so the
rest of the system stays testable and runnable offline with a fake gateway.

**Rationale.** The MVP must not depend on WeBook, Platinumlist, or Ticketmaster
APIs. In-repo Python tools are testable, mockable, and reviewable, and keep the
demo reproducible from a clean clone.

### IV. Exact, Auditable Money & Discounts

All money MUST be computed server-side and stored as exact values (minor
units / `Decimal`), never floated in from the client. Every quote MUST itemise
base price, member-discount amount (by tier), VAT at 15%, and total. The
member discount and the per-tier ticket cap MUST be derived from the `members`
table via email lookup — never assumed or supplied by the user.

**Rationale.** Pricing bugs are silent revenue leaks and a graded
correctness item ("discount correctness across all tiers and quantities").
Server-authoritative math is the only defensible source of truth.

### V. Tamper-Evident Tickets & Exactly-Once Fulfilment

A ticket's QR code MUST encode a server-signed HMAC token (booking id + seat
ids + nonce), verified server-side at scan time — never a bare booking id.
Payment confirmation MUST flow through a signature-verified webhook guarded by
an idempotency key, so duplicate webhook deliveries produce **exactly one**
paid booking and **exactly one** ticket.

**Rationale.** Screenshotting a raw booking id must not grant entry, and
payment gateways retry webhooks — both are explicit evaluation criteria
("webhook robustness: duplicate deliveries result in exactly one ticket";
"ticket fraud prevention").

### VI. Test-First for Data & Money Operations

Every Python tool that writes to the database, computes a quote, or mutates a
seat/hold MUST have unit tests written and passing before it is wired into the
agent. SQL schemas are defined as migrations, not ad-hoc `CREATE` statements.
Tests use fixtures or an in-memory SQLite instance, never the demo DB.

**Rationale.** The agent is judged on "safe database writes," "discount
correctness," and "concurrency safety." Tests on tool functions are the
cheapest guarantee the agent can't corrupt a booking by calling a tool wrong.

### VII. Observable Reasoning

Every tool call the agent makes MUST be logged with: timestamp, tool name,
input arguments (PII redactable), output summary, and the triggering
user-message id. Every booking state transition (held → pending_payment →
paid / expired / cancelled) and every per-turn sentiment label MUST be
persisted to an append-only audit/interaction log.

**Rationale.** The agent's value is in its decisions. Observability is what
lets the user and the bootcamp graders trust the system, and what makes the
seat-hold / payment / personalisation flows debuggable when they misbehave.

### VIII. MVP First, Multi-Agent Later

The default architecture is a single booking agent with a clear tool surface.
Multi-agent orchestration (LangGraph-style Catalog / Pricing / Hold / Payment
/ Fulfilment / Recommender agents) is a stretch goal. The project MUST ship the
single-agent MVP — search → quote → seat → hold → confirm → pay → ticket —
before any multi-agent work begins, and multi-agent work MUST NOT regress any
MVP capability.

**Rationale.** A working single-agent demo is worth more than a half-finished
multi-agent system. The brief classifies multi-agent as a stretch goal.

## Security, Privacy & Compliance

- **PDPL alignment.** Personal data (buyer email, name) is collected only when
  needed to look up membership and deliver a ticket. It is stored in the
  booking/members tables, never logged in plaintext at INFO level, and is
  redactable in tool-call logs.
- **Secrets.** API keys, the Moyasar secret, and the HMAC signing key live in
  `.env` (gitignored). They MUST NOT be committed. CI / pre-push scans the
  staged diff for secret patterns.
- **Webhook trust.** The payment webhook handler MUST verify the gateway
  signature before mutating any booking, and reject unsigned/invalid calls.
- **VAT / invoicing.** Quotes apply Saudi VAT at 15% as a separate line item,
  consistent with ZATCA expectations; the total shown at confirmation equals
  the amount charged.
- **Least privilege.** Admin-only operations (re-seed, force-release holds) are
  gated behind an admin token and are themselves logged.

## Technology Constraints

- **Language.** Python 3.11+.
- **Backend.** FastAPI, organised so the agent, tools, and database layers are
  separately importable modules.
- **Agent framework.** LangChain for the MVP; LangGraph reserved for the
  multi-agent stretch. Pick one idiom per layer; do not mix in the MVP.
- **Database.** SQLite for local dev and demo; PostgreSQL acceptable if it
  materially improves the demo. SQLAlchemy 2 is the ORM; Alembic for migrations.
- **Holds / TTL.** DB-backed `holds` table with `expires_at` + a background
  sweeper for the MVP; Redis `SETNX`+TTL is an acceptable upgrade.
- **Interface.** Streamlit (MVP chat UI, must render inline images for event
  cards, seat maps, and ticket cards), Gradio, FastAPI Swagger, or a CLI are
  acceptable. React/Next.js is a stretch, not required.
- **Payments.** Moyasar sandbox (Mada / Apple Pay / STC Pay). Isolated behind
  one adapter with a fake implementation for offline tests.
- **Fulfilment libraries.** Pillow (seat-map + ticket image), `qrcode` (HMAC
  payload), ReportLab or WeasyPrint (PDF), SMTP/SendGrid/Resend (email).
- **LLM provider.** OpenAI, Anthropic, or Gemini via API; Ollama acceptable for
  an offline demo. The agent MUST degrade gracefully (heuristic fallback) when
  no key is configured.
- **RAG (optional).** Chroma or FAISS / in-memory BM25 for venue FAQs and
  policies.
- **Excluded from MVP.** Real-money payments, secondary-market resale, dynamic
  pricing, full web CRM dashboard, voice input, WhatsApp channel, complex auth.

## Development Workflow

1. **Spec-kit drives every feature.** A change starts with `/speckit-specify`,
   then `/speckit-plan`, `/speckit-tasks`, and only then `/speckit-implement`.
   Skipping ahead is allowed only for trivial fixes (typo, dead-code removal).
2. **Constitution Check before plan.** Each plan MUST validate against this
   constitution. If a plan needs to violate a principle, it documents the
   exception and proposes an amendment in the same change.
3. **Tests before tools.** Per Principle VI, no DB-writing or money-computing
   tool is merged without unit tests.
4. **Confirmation + hold + idempotency in every write path.** Per Principles
   I, II, and V, the approval gate, atomic hold, and idempotent webhook are
   defaults; bypassing any requires an explicit, logged admin override.
5. **GitHub is the system of record.** Spec, plan, tasks, and code live in this
   repo. The full demo is reproducible from a clean clone against the Moyasar
   sandbox with one command.

## Governance

This constitution supersedes ad-hoc preferences. Amendments require:

- A short rationale in the commit message.
- A version bump (semver: MAJOR for principle removal/redefinition, MINOR for
  new principles or materially expanded guidance, PATCH for
  wording/clarification).
- A propagation check against `.specify/templates/plan-template.md`,
  `.specify/templates/spec-template.md`, and `.specify/templates/tasks-template.md`.

The bootcamp grading rubric (see `Requirements.md` §11 and `docs/proposal.md`)
is treated as an external constraint that this constitution MUST remain
consistent with. If they conflict, the rubric wins and this document is amended.

**Version**: 1.0.0 | **Ratified**: 2026-06-07 | **Last Amended**: 2026-06-07
