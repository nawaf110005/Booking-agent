# Feature Specification: RAG over Venue FAQ & Policy

**Feature Branch**: `007-rag-venue-faq`

**Created**: 2026-06-07

**Status**: Approved

**Input**: User description: "Ground policy/logistics answers in a small bilingual corpus under docs/venue-faq/ so the agent never hallucinates policy. Topics: refunds/cancellation/exchange, parking, gates/entry, accessibility, prohibited items, directions/transport, age rating, dress code, re-entry. Default retriever is in-memory BM25 (no model download, runs offline); Chroma + embeddings is a documented drop-in upgrade behind a config flag. A rag_search(query, venue?) tool returns top passages with their source; the F002 agent routes the ask_policy intent to it and answers grounded, quoting/citing the source document."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Refund-policy question answered from corpus with citation, not invented (Priority: P1)

As a buyer mid-booking, I can ask "Can I get a refund if I can't make it?" and the agent replies with the exact policy text sourced from `docs/venue-faq/refund-policy.md`, quoting the source file name — never inventing a policy that does not exist in the corpus.

**Why this priority.** RAG quality is an explicit evaluation criterion ("Policy/logistics answers are grounded in venue docs, not hallucinated"). A hallucinated refund policy is a legal and trust risk; this story is the minimum viable grounding guarantee.

**Independent test.** Call `rag_search("refund policy")` against a seeded corpus; assert the top result's `source` field contains `refund-policy.md` and the passage text matches known corpus content. Then instruct a test agent to answer the question and assert the answer contains the cited source.

**Acceptance scenarios.**

1. **Given** `docs/venue-faq/refund-policy.md` exists in the corpus and the retriever is initialised, **When** `rag_search("refund if I can't attend")` is called, **Then** the result list is non-empty, `result[0].source` ends with `refund-policy.md`, and `result[0].passage` contains policy text from that file.
2. **Given** the agent receives the intent `ask_policy` with query "Can I get a refund?", **When** it calls `rag_search` and composes its reply, **Then** the agent's answer includes a citation of the form `(Source: refund-policy.md)` and does not assert any refund rule not present in the corpus.
3. **Given** both Arabic and English queries for the same policy topic, **When** `rag_search("استرداد التذكرة")` is called, **Then** the retriever returns the same or equivalent passage as for the English query, demonstrating bilingual coverage.

### User Story 2 — Venue-specific parking and accessibility question answered per venue (Priority: P2)

As a buyer who has selected a specific venue, I can ask "Where do I park at Kingdom Arena?" or "Is Kingdom Arena wheelchair accessible?" and the agent retrieves the passage for that venue from the corpus, not a generic answer.

**Why this priority.** Venue-specific logistics (parking, accessibility, gates, transport) vary per venue and are the second most common policy query type; a wrong answer at this level creates real-world problems at the event.

**Independent test.** Seed at least two venues in `docs/venue-faq/` with differing parking details. Call `rag_search("parking", venue="kingdom-arena")` and assert the returned passages are scoped to Kingdom Arena. Call again with `venue="another-venue"` and assert different passages are returned.

**Acceptance scenarios.**

1. **Given** `docs/venue-faq/kingdom-arena.md` and `docs/venue-faq/al-awwal-park.md` both exist with distinct parking sections, **When** `rag_search("parking", venue="kingdom-arena")` is called, **Then** all returned passages have `source` containing `kingdom-arena.md` and none reference `al-awwal-park`.
2. **Given** a buyer query "Is there disabled access at Kingdom Arena?", **When** the agent routes `ask_policy` with the venue context, **Then** the answer cites `kingdom-arena.md` and includes specific accessibility details from that file.
3. **Given** the corpus contains an Arabic section for accessibility, **When** a buyer asks "هل يوجد دخول للمعاقين؟", **Then** the retriever returns a relevant passage with the Arabic or bilingual content from the venue file.

### User Story 3 — Chroma upgrade path documented and selectable by config flag without changing the tool contract (Priority: P2)

As a developer, I can set `RAG_BACKEND=chroma` in `.env` and the system switches from in-memory BM25 to Chroma + sentence-transformer embeddings, with `rag_search` returning identically shaped results — no change to the agent's tool-calling code.

**Why this priority.** The constitution and requirements explicitly document Chroma as an upgrade path; the flag-controlled interface isolation is what keeps the agent's tool contract stable and allows offline-first operation in demos without model downloads.

**Independent test.** Run `rag_search("refund")` with `RAG_BACKEND=bm25` (default) and with `RAG_BACKEND=chroma` (stub/mock embeddings). Assert both return `RagResult` objects with identical fields (`passage`, `source`, `score`). Assert that when `RAG_BACKEND=bm25`, no sentence-transformers or Chroma import is triggered.

**Acceptance scenarios.**

1. **Given** `RAG_BACKEND` is unset or set to `bm25`, **When** `rag_search("parking")` is called, **Then** the BM25 retriever is used, no model is downloaded, and results are returned in under 200ms with no network calls.
2. **Given** `RAG_BACKEND=chroma` and a valid Chroma collection is initialised, **When** `rag_search("parking")` is called, **Then** the Chroma retriever is used and the returned `RagResult` schema is identical to the BM25 case.
3. **Given** `RAG_BACKEND=chroma` but the Chroma collection is not yet built, **When** the system starts, **Then** it logs a clear error and falls back to BM25 with a warning rather than crashing.

### User Story 4 — No-match case: agent says it does not have that information (Priority: P2)

As a buyer, if I ask about a topic not covered in the corpus (e.g., backstage access, media credentials), the agent responds honestly that it does not have that information and suggests contacting the venue directly — rather than fabricating an answer.

**Why this priority.** A RAG system that halluccinates when it cannot retrieve is worse than one that stays silent. The no-match path must be explicit and testable.

**Independent test.** Call `rag_search("backstage access VIP passes")` against the seeded corpus; assert the result list is empty or all scores are below `RAG_MIN_SCORE`. Then instruct a test agent to answer and assert it contains a phrase such as "I don't have that information" and does not invent a policy.

**Acceptance scenarios.**

1. **Given** no document in the corpus covers "media credentials", **When** `rag_search("media credentials")` is called, **Then** the function returns an empty list or a list where every result's `score` is below `RAG_MIN_SCORE` (configurable, default 0.0 for BM25 empty).
2. **Given** the retriever returns an empty result, **When** the agent constructs its reply for `ask_policy`, **Then** the reply includes a statement that the information is not available in the current corpus and advises contacting the venue.

### Edge Cases

- Query is an empty string: `rag_search("")` raises `ValidationToolError`, not an unhandled exception.
- Corpus directory `docs/venue-faq/` is empty or missing: `corpus.py` logs a warning and `rag_search` returns an empty list rather than crashing.
- A venue-faq markdown file is malformed (no headings, binary content): the loader skips the file, logs a warning, and continues loading the rest.
- Very long query (> 500 characters): truncated to 500 chars with a warning before retrieval.
- `venue` filter matches no file in the corpus: treated as no filter (global search) with a warning logged.
- Bilingual query mixing Arabic and English in one string (e.g., "refund سياسة"): handled without error; BM25 tokenises both scripts.
- `top_k` parameter of 0 or negative: defaults to 3 with a warning.
- Concurrent calls to `rag_search` from multiple agent threads: the in-memory BM25 index is read-only after build, so concurrent reads are safe without locking.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load all `docs/venue-faq/*.md` files at startup into a corpus, splitting each file into passages by heading (H2/H3) and storing `source` (filename) and `text` per passage.
- **FR-002**: System MUST provide a BM25 in-memory retriever (default) that indexes the corpus at startup with no network access, no model download, and no external service dependency.
- **FR-003**: System MUST provide a `rag_search(query: str, venue: str | None = None, top_k: int = 3) -> list[RagResult]` tool that returns passages ranked by relevance, each with `passage: str`, `source: str`, and `score: float`.
- **FR-004**: When `venue` is provided, `rag_search` MUST filter results to passages whose `source` filename matches the venue slug before ranking; if no match, it falls back to global search with a logged warning.
- **FR-005**: System MUST support a `RAG_BACKEND` config flag (`bm25` | `chroma`) that switches the retriever implementation without changing the `rag_search` tool signature or return type.
- **FR-006**: When `RAG_BACKEND=chroma`, the system MUST initialise a Chroma collection with sentence-transformer embeddings (e.g., `all-MiniLM-L6-v2` or OpenAI embeddings); this MUST NOT be imported or executed when `RAG_BACKEND=bm25`.
- **FR-007**: When `rag_search` returns an empty list (score below threshold or no passages), the agent MUST NOT fabricate policy; it MUST reply that the information is not available and suggest contacting the venue.
- **FR-008**: The corpus MUST include bilingual (Arabic and English) content for each policy topic; the BM25 retriever MUST handle both scripts without error.
- **FR-009**: Every call to `rag_search` MUST be logged (per Constitution VII) with: timestamp, tool name, query (truncated if > 200 chars), venue filter, number of results, and top result source.
- **FR-010**: The `rag_search` tool MUST have unit tests (happy path, no-match, bilingual query, venue filter, empty corpus) passing with the BM25 backend before it is wired into the F002 agent.

### Key Entities

- **Passage.** A chunk of text extracted from a corpus file; attributes: `text: str`, `source: str` (filename), `venue_slug: str | None` (derived from filename).
- **RagResult.** The DTO returned by `rag_search`; attributes: `passage: str`, `source: str`, `score: float`. Identical schema regardless of backend.
- **Corpus.** The in-memory list of `Passage` objects built from `docs/venue-faq/*.md` at startup; rebuilt on demand via `corpus.reload()`.
- **Retriever.** An abstract interface with a single method `retrieve(query, venue_slug, top_k) -> list[RagResult]`; implemented by `BM25Retriever` and `ChromaRetriever`.

## Success Criteria *(mandatory)*

- **SC-001**: `rag_search("refund policy")` returns at least one `RagResult` whose `source` ends with `refund-policy.md` and whose `passage` contains text present in that file.
- **SC-002**: `rag_search("backstage access VIP passes")` returns an empty list (or all results below `RAG_MIN_SCORE`) when the topic is absent from the corpus.
- **SC-003**: All `rag_search` unit tests pass with `RAG_BACKEND=bm25` in under 5 seconds total, with zero network calls and zero model downloads.
- **SC-004**: Switching to `RAG_BACKEND=chroma` (with a mock embedding function) does not change the schema of any `RagResult` returned; the tool contract is identical.
- **SC-005**: A bilingual query `rag_search("استرداد التذكرة")` returns a non-empty result list when Arabic refund content is present in the corpus.
- **SC-006**: Coverage on `src/booking_agent/rag/` >= 85% (`pytest-cov`).
- **SC-007**: The F002 agent routes the `ask_policy` intent to `rag_search` and its answer to a refund question contains a `(Source: ...)` citation string.

## Assumptions

- The corpus files `docs/venue-faq/*.md` are written manually and maintained as Markdown; their content is authoritative for MVP policy answers.
- BM25 is provided by the `rank-bm25` PyPI package (pure Python, no compiled extensions).
- Chroma and `sentence-transformers` are optional extras (`pip install booking-agent[rag-chroma]`) and MUST NOT be required for the default `bm25` path.
- The F002 agent spec (booking-agent feature 002) exposes an `ask_policy` intent slot; this feature provides the tool `rag_search` that F002 calls — F007 does not modify F002's agent prompt directly.
- Passage splitting by heading is sufficient for MVP; semantic chunking is a future upgrade.
- The corpus is small enough (< 50 passages at MVP) that full rebuild at startup is acceptable; no incremental indexing is required.
- Arabic text in the corpus is stored as UTF-8; BM25 tokenises on whitespace and handles Arabic script without a specialised tokeniser for MVP.
- `RAG_MIN_SCORE` defaults to 0.0 for BM25 (any non-zero BM25 score is a match); for Chroma it defaults to 0.3 (cosine similarity threshold).
- The audit log entry for `rag_search` reuses the existing `audit_log` table defined in F001; no schema change is required.
