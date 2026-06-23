# Feature Specification: Conversational, Event-Aware Booking Assistant

**Feature Branch**: `009-conversational-event-assistant`

**Created**: 2026-06-23

**Status**: Draft

**Input**: User description: "Make the booking agent converse like a knowledgeable, personable human concierge that guides users to book an event. Fix natural-language questions with typos/misspellings/odd spacing being misunderstood (e.g. 'dose cold play will be here in saudi' returns the unrelated PAYMENT FAQ). Understand fuzzy queries, recognize event-availability questions, use semantic search over events + FAQ with a relevance threshold, suggest similar events, and make booking personalized and human — while keeping the safety gates and an offline fallback."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask whether an event is available, in plain (imperfect) language (Priority: P1)

A visitor types a natural question — possibly misspelled, oddly spaced, or mixing Arabic and English — asking whether a particular artist or event is happening (e.g. "dose cold play will be here in saudi", "هل في كولدبلاي؟", "do u have any football?"). The assistant understands the intent, checks the live catalog, and answers truthfully: if the event exists it confirms the details (date, venue, from-price) and offers to book it; if it does not, it says so plainly and offers the closest available alternatives of the same type.

**Why this priority**: This is the reported failure and the core of the product. Today such a question can return a completely unrelated answer (the payment blurb), which destroys trust. Getting this right is the difference between a usable concierge and a broken one.

**Independent Test**: Send a batch of misspelled / oddly-spaced / bilingual event questions for both existing and non-existing events; verify each gets a correct, on-topic answer (confirm + offer to book, or "not available" + relevant alternatives) and never an unrelated FAQ.

**Acceptance Scenarios**:

1. **Given** the catalog contains a Coldplay concert, **When** the user asks "dose cold play will be here in saudi", **Then** the assistant confirms the Coldplay event (date, venue, from-price) and offers to book it — and does NOT return the payment or any unrelated answer.
2. **Given** the catalog has no "Taylor Swift" event, **When** the user asks "is taylor swift coming?", **Then** the assistant says it isn't on the calendar and suggests the most similar available events (other concerts).
3. **Given** a user writes "كولدبلاي موجود؟" (Arabic), **When** the message is processed, **Then** the assistant answers in Arabic with the same correctness as the English path.

---

### User Story 2 - Trustworthy answers that never fire on a coincidental word (Priority: P1)

When the assistant answers a question from its knowledge base (payment, refunds, parking, membership, etc.), it only does so when the question is genuinely about that topic. A single incidental shared word (e.g. "here", "the", "in") must never cause an unrelated knowledge-base answer to be returned.

**Why this priority**: This is the second half of the reported bug. Loose matching makes every other answer suspect; a relevance bar is required for the assistant to be trusted at all.

**Independent Test**: Feed questions whose only overlap with a knowledge-base entry is a common/stopword term; verify none of them return that entry. Feed clearly on-topic questions; verify they still return the right entry.

**Acceptance Scenarios**:

1. **Given** a knowledge-base entry about payment that contains the word "here", **When** the user asks an event question containing "here" but nothing about payment, **Then** the payment entry is NOT returned.
2. **Given** a genuine payment question ("how do I pay?"), **When** it is processed, **Then** the payment answer IS returned.
3. **Given** a question with no sufficiently relevant knowledge-base match, **When** it is processed, **Then** the assistant gives an honest "I'm not sure about that, but here's what I can help with" response rather than a wrong match.

---

### User Story 3 - Discover the right event with similar-event suggestions (Priority: P2)

A user who doesn't know exactly what they want, or whose exact request isn't available, is guided to a good choice. The assistant understands the *type* of event the user is after (concert, football, comedy, festival, conference) and proactively recommends the closest available options, ranked by relevance to what they asked and what they've shown interest in.

**Why this priority**: Turns dead-ends ("we don't have that") into bookings ("but you'd love this") and is the heart of a concierge experience. Depends on robust understanding (US1) being in place first.

**Independent Test**: Ask for an unavailable event or a vague category; verify the assistant returns a short, ranked list of genuinely similar/relevant available events with a one-line reason, and that selecting one continues into the booking flow.

**Acceptance Scenarios**:

1. **Given** no Coldplay event exists but other concerts do, **When** the user asks for Coldplay, **Then** the assistant offers the nearest concert alternatives and lets the user book one in the same conversation.
2. **Given** a user asks "anything fun this weekend?", **When** processed, **Then** the assistant asks a light clarifying question or suggests a small ranked set spanning the user's likely interests.

---

### User Story 4 - Personalized, human-feeling conversation (Priority: P2)

Across the conversation the assistant feels like a helpful person, not a form: it greets the user by name once known, references their membership tier and the discount it unlocks, remembers their interests and past bookings, adapts its tone when the user is frustrated, and weaves recommendations in naturally — all while moving the booking forward.

**Why this priority**: This is the stated goal ("make booking experience more personalized") and the differentiator, but it builds on correct understanding and discovery.

**Independent Test**: Run a multi-turn conversation for a known member with prior bookings; verify the assistant uses the name and tier correctly, recalls interests/history, adapts to a frustrated message, and consistently nudges toward the next booking step.

**Acceptance Scenarios**:

1. **Given** a returning Platinum member named Nawaf, **When** they start a chat, **Then** the assistant greets them by name, notes their tier/discount, and references a relevant past interest without being asked.
2. **Given** the user expresses frustration, **When** the next reply is produced, **Then** its tone acknowledges the frustration and offers a concrete next step.

---

### Edge Cases

- **Typos / misspellings**: "coldpaly", "cold play", missing/extra spaces, wrong vowels — all map to the right event when one is clearly intended.
- **Bilingual / mixed script**: Arabic, English, and mixed messages are understood and answered in the user's language.
- **Unknown or unavailable event**: handled with an honest "not available" plus relevant alternatives — never a fabricated event or an unrelated FAQ.
- **Ambiguous query** (e.g. just "music", "show"): assistant asks one focused clarifying question or offers a small ranked set rather than dumping the whole catalog.
- **Coincidental single-word overlap** with a knowledge-base entry: must not trigger that entry.
- **Off-topic / chit-chat** (weather, jokes, "write me code"): answered briefly and warmly, then steered back to events; clearly declined when out of scope.
- **No provider available (offline)**: a deterministic rule-based path still understands common events, intents, and FAQs and still books end-to-end.
- **Mid-booking questions**: a question asked during an active booking is answered without losing the booking or its step.
- **Safety**: none of this weakens confirm-before-pay, atomic holds, or exact-money guarantees.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The assistant MUST interpret event queries that contain misspellings, missing/extra spaces, or alternate spellings and resolve them to the intended catalog event when one is clearly intended (English and Arabic).
- **FR-002**: The assistant MUST recognize event-availability questions ("is X here / coming / available?", "do you have Y?", "any Z?") and route them to a catalog lookup rather than to generic FAQ matching.
- **FR-003**: When a requested event exists, the assistant MUST state its real details (title, date, venue, from-price) and offer to start booking it.
- **FR-004**: When a requested event does NOT exist, the assistant MUST say so plainly and present the most relevant available alternatives (same type/genre, ranked), never inventing an event.
- **FR-005**: Knowledge-base (FAQ) answers MUST only be returned when the question meets a minimum relevance bar; a match on a single common/stopword term MUST NOT return an entry.
- **FR-006**: The assistant MUST match events and FAQ entries by meaning (semantic similarity), not only exact keywords, so fuzzy/typo'd questions still find the right content.
- **FR-007**: The assistant MUST be able to identify the *type* of event a user is interested in and recommend similar available events ranked by relevance to the request and the user's known interests.
- **FR-008**: The assistant MUST personalize replies using known context — name, membership tier and its discount, learned interests, past bookings, and per-turn sentiment — when that context is available.
- **FR-009**: The assistant MUST answer questions asked mid-booking without discarding the active booking or its current step.
- **FR-010**: The assistant MUST operate in both Arabic and English, replying in the user's language, including for suggestions and alternatives.
- **FR-011**: A deterministic, provider-free fallback MUST still understand common events, core intents, and FAQs and complete a booking when no language/semantic provider is configured or reachable.
- **FR-012**: The feature MUST NOT weaken existing guarantees: explicit human confirmation before any payment, all-or-nothing time-bounded seat holds, and exact integer money math.
- **FR-013**: The assistant MUST decline clearly-out-of-scope requests (non-ticketing tasks) in-character and redirect to events, rather than ignoring them or answering with an unrelated canned reply.
- **FR-014**: When a query is too ambiguous to act on, the assistant MUST ask one focused clarifying question or present a small ranked set, rather than returning the entire catalog or a wrong guess.

### Key Entities *(include if feature involves data)*

- **Event**: A bookable live event — title, type/genre (concert, football, comedy, festival, conference), city, venue, date/time, from-price, and a semantic representation used for similarity/fuzzy matching.
- **Knowledge entry**: A unit of platform/venue FAQ knowledge (payment, refunds, parking, membership, accessibility…) with a topic and a relevance representation, returned only above a relevance threshold.
- **User profile / memory**: Per-user context — identity (name, email), membership tier and entitlements, learned interests/genres, past bookings, and recent sentiment — used to personalize and recommend.
- **Conversation turn**: One user message and its resolved understanding — language, intent, target event or topic, and confidence — that drives the reply.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a curated set of natural event questions (including ≥20 misspelled / oddly-spaced / bilingual variants), at least 95% receive a correct, on-topic answer (confirm-and-offer-to-book, or honest "not available" + relevant alternatives).
- **SC-002**: Zero questions in the evaluation set return an unrelated knowledge-base answer caused by a coincidental single-word overlap (the reported failure occurs 0 times).
- **SC-003**: For requests whose exact event is unavailable, at least 90% receive at least one genuinely relevant alternative of the same type.
- **SC-004**: For known members, personalized elements (correct name, tier/discount, a relevant interest or past booking) appear appropriately in at least 90% of opening replies.
- **SC-005**: With no language/semantic provider configured, the assistant still resolves the common seeded events and completes a booking end-to-end (offline parity preserved).
- **SC-006**: Existing safety guarantees remain at 100%: no payment is issued without explicit confirmation, no seat hold is partial, and quoted totals remain exact to the halala.
- **SC-007**: Users reach a booking (or a clearly-offered alternative) from an imperfect first question in the large majority of attempts, measured by task-completion on the evaluation conversations.

## Assumptions

- The live catalog (events with type/genre, venue, date, price) is the single source of truth for availability; the assistant never fabricates events.
- "Similar" is judged primarily by event type/genre and the user's known interests; the exact distance metric is an implementation detail for planning.
- Semantic matching may use an embedding/vector capability when available, but the system must degrade gracefully to deterministic matching when it is not — no hard dependency that breaks the offline demo.
- Personalization uses data the system already captures (member tier, interaction/booking history, sentiment); no new sensitive data collection is introduced.
- Arabic support targets common Saudi-dialect and MSA phrasings for events, intents, and FAQs; exhaustive dialect coverage is not required for v1.
- Existing conversation/session, money, hold, and payment mechanisms are reused; this feature changes understanding, retrieval, and personalization — not the booking primitives.
