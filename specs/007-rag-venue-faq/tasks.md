---
description: "Task list for RAG over Venue FAQ & Policy"
---

# Tasks: RAG over Venue FAQ & Policy

**Input**: Design documents from `/specs/007-rag-venue-faq/`

**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: Included — Constitution VI makes tests mandatory for `rag_search` before F002 wiring.

**Organization**: Grouped by user story so each can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (refund citation), US2 (venue-specific), US3 (Chroma upgrade), US4 (no-match)

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Add `rank-bm25` to `pyproject.toml` default dependencies; add `chromadb` and `sentence-transformers` under `[project.optional-dependencies] rag-chroma` in `src/booking_agent/` `pyproject.toml`
- [ ] T002 [P] Extend `src/booking_agent/config.py` — add `RAG_BACKEND`, `RAG_CORPUS_DIR`, `RAG_MIN_SCORE`, `RAG_TOP_K`, `RAG_EMBEDDING_MODEL` settings with documented defaults
- [ ] T003 [P] Create `src/booking_agent/rag/__init__.py` — package stub exporting `rag_search`, `build_corpus`, `reload_corpus`

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No retriever or tool work can begin until corpus loading and the `RagResult` / `Passage` types exist.

- [ ] T004 Define `Passage` dataclass and `RagResult` Pydantic model in `src/booking_agent/rag/corpus.py` — fields: `text`, `source`, `venue_slug`; `RagResult` fields: `passage`, `source`, `score`
- [ ] T005 [P] Define `Retriever` ABC in `src/booking_agent/rag/retriever.py` — methods: `build(passages) -> None` and `retrieve(query, venue_slug, top_k) -> list[RagResult]`
- [ ] T006 Implement corpus loader in `src/booking_agent/rag/corpus.py` — `load_corpus(corpus_dir: Path) -> list[Passage]`; splits each `.md` on H2/H3 headings; derives `venue_slug` from filename stem; skips files shorter than 20 chars with a warning; handles missing directory gracefully
- [ ] T007 [P] Create `tests/test_rag/__init__.py` and `tests/test_rag/conftest.py` — pytest fixture that writes a minimal corpus of three `.md` files (bilingual content, at least one heading per topic) to a `tmp_path` directory and returns the `list[Passage]`

**Checkpoint**: Corpus types and loader ready — retriever and tool can now be built in parallel.

## Phase 3: User Story 1 — Refund-policy answer with citation (Priority: P1)

**Goal**: `rag_search("refund policy")` returns a passage from `refund-policy.md` with a cited source; the no-hallucination contract is enforceable in tests.

- [ ] T008 [P] [US1] Write `tests/test_rag/test_retriever_bm25.py` FIRST — happy-path test: seed corpus with `refund-policy.md` content; assert `BM25Retriever.retrieve("refund policy", None, 3)` returns ≥ 1 result with `source` ending in `refund-policy.md` — must FAIL before implementation
- [ ] T009 [P] [US1] Write `tests/test_rag/test_tool.py` citation test FIRST — mock `BM25Retriever.retrieve` to return a known result; call `rag_search("refund policy")`; assert return is `list[RagResult]` with correct fields — must FAIL before implementation
- [ ] T010 [US1] Implement `BM25Retriever` in `src/booking_agent/rag/retriever.py` — `build` tokenises passage texts; `retrieve` scores with `BM25Okapi`, applies `RAG_MIN_SCORE` filter, returns top-k sorted descending; handles empty result list
- [ ] T011 [US1] Implement `rag_search` in `src/booking_agent/rag/tool.py` — validates query (non-empty, max 500 chars); loads/reuses built retriever; calls `retrieve`; logs call per FR-009; returns `list[RagResult]`; raises `ValidationToolError` on invalid input
- [ ] T012 [US1] Author `docs/venue-faq/refund-policy.md` — bilingual (Arabic + English) refund, cancellation, and exchange policy; structured with H2/H3 headings per topic
- [ ] T013 [US1] Make `test_retriever_bm25.py` happy-path and `test_tool.py` citation tests green

**Checkpoint**: `rag_search("refund policy")` returns a cited result; US1 independently testable.

## Phase 4: User Story 2 — Venue-specific parking and accessibility (Priority: P2)

**Goal**: `rag_search("parking", venue="kingdom-arena")` returns only Kingdom Arena passages.

- [ ] T014 [P] [US2] Write `tests/test_rag/test_retriever_bm25.py` venue-filter tests FIRST — seed corpus with two venue files; assert venue filter scopes results correctly and falls back to global on no-match — must FAIL
- [ ] T015 [US2] Extend `BM25Retriever.retrieve` to apply `venue_slug` pre-filter: keep only passages where `passage.venue_slug == venue_slug` before BM25 scoring; if filtered set is empty, log warning and fall back to full corpus
- [ ] T016 [US2] Author `docs/venue-faq/kingdom-arena.md` — bilingual venue-specific FAQ: parking (sections, hours, fees), accessibility (wheelchair ramps, companion seats, accessible toilets), gates (numbers, opening time), transport (bus, metro, ride-hail drop-off)
- [ ] T017 [P] [US2] Author `docs/venue-faq/al-awwal-park.md` — bilingual venue-specific FAQ matching the same topic structure as `kingdom-arena.md` with distinct content
- [ ] T018 [P] [US2] Author remaining corpus files in `docs/venue-faq/` — `parking.md`, `gates-entry.md`, `accessibility.md`, `prohibited-items.md`, `directions-transport.md`, `age-rating.md`, `dress-code.md`, `re-entry.md` — each bilingual with H2/H3 headings
- [ ] T019 [US2] Make venue-filter tests green; verify `rag_search("parking", venue="al-awwal-park")` returns different passages than `venue="kingdom-arena"`

**Checkpoint**: Venue-scoped retrieval working; US2 independently testable with two venue files.

## Phase 5: User Story 3 — Chroma upgrade path via config flag (Priority: P2)

**Goal**: `RAG_BACKEND=chroma` switches retriever transparently; BM25 path never imports Chroma.

- [ ] T020 [P] [US3] Write `tests/test_rag/test_tool.py` backend-flag tests FIRST — mock the `ChromaRetriever` class; assert `RAG_BACKEND=bm25` never imports `chromadb`; assert `RAG_BACKEND=chroma` calls `ChromaRetriever.retrieve`; assert returned `RagResult` schema is identical — must FAIL
- [ ] T021 [US3] Implement `ChromaRetriever` in `src/booking_agent/rag/retriever.py` — lazy import of `chromadb` and `sentence_transformers` inside `__init__`; `build` creates/loads Chroma collection; `retrieve` queries with embedding; respects `RAG_MIN_SCORE`; raises `ImportError`-derived exception with clear message if `chromadb` not installed
- [ ] T022 [US3] Extend `rag_search` factory in `src/booking_agent/rag/tool.py` — `if settings.RAG_BACKEND == "chroma": retriever = ChromaRetriever(...)` else `retriever = BM25Retriever(...)`; Chroma init failure logs warning and falls back to BM25
- [ ] T023 [P] [US3] Add `RAG_BACKEND` and Chroma config to `.env.example` with documented instructions for the upgrade path
- [ ] T024 [US3] Make backend-flag tests green; verify with `import sys` assertion that `chromadb` is not in `sys.modules` after a BM25 call

**Checkpoint**: Both backends selectable by config; tool contract unchanged; US3 independently testable.

## Phase 6: User Story 4 — No-match honest reply (Priority: P2)

**Goal**: `rag_search` on an out-of-corpus topic returns an empty list; agent says it doesn't know.

- [ ] T025 [P] [US4] Write `tests/test_rag/test_retriever_bm25.py` no-match tests FIRST — query with zero token overlap; assert returned list is empty or all scores == 0.0 — must FAIL
- [ ] T026 [P] [US4] Write `tests/test_rag/test_corpus.py` edge-case tests — empty corpus dir returns `[]`; malformed file is skipped with warning; missing directory logs warning and returns `[]`
- [ ] T027 [US4] Verify `BM25Retriever.retrieve` filters out zero-score results when `RAG_MIN_SCORE == 0.0`; ensure empty list is returned, not a list of zero-score results
- [ ] T028 [US4] Make no-match and corpus edge-case tests green

**Checkpoint**: All four user stories independently testable; no-hallucination contract proven.

## Phase 7: Polish & Cross-Cutting

- [ ] T029 [P] Write `tests/test_rag/test_tool.py` validation edge-case tests — empty query raises `ValidationToolError`; query > 500 chars is truncated with warning; `top_k <= 0` defaults to 3 with warning
- [ ] T030 [P] Write `tests/test_rag/test_corpus.py` bilingual tokenisation test — Arabic-only query against Arabic corpus passage; assert non-empty result
- [ ] T031 Run full test suite; enforce `pytest-cov` >= 85% on `src/booking_agent/rag/`; fix any coverage gaps
- [ ] T032 [P] Run `ruff check src/booking_agent/rag/ tests/test_rag/` and resolve all linting issues
- [ ] T033 [P] Add `rag_search` as a LangChain `Tool` registration stub in `src/booking_agent/agent/tools_registry.py` (or equivalent F002 wiring point) with name `rag_search` and description per FR-003

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** blocks all story phases.
- After Phase 2 checkpoint: **US1 (Phase 3)**, **US2 (Phase 4)**, **US3 (Phase 5)**, **US4 (Phase 6)** can proceed in parallel across different team members (all touch different files).
- **Polish (Phase 7)** after all story phases.
- T010 and T011 (BM25 implementation + tool) must complete before T015 (venue filter extension).
- T021 and T022 (Chroma retriever + factory) are independent of US2 and US4.

## Implementation Strategy

MVP-first: deliver US1 (citation guarantee) before any other story. US2/US3/US4 add coverage depth and the upgrade path. The BM25 path is the critical offline demo path — it must work from a clean clone with no downloads. Chroma is implemented only after BM25 tests are green.

## Notes

- All checkboxes are UNCHECKED; implementation has not begun.
- Constitution VI: write tests FIRST for all retriever and tool tasks; verify they fail before coding the implementation.
- The `docs/venue-faq/*.md` corpus files are deliverables of this feature; their contents are not specified in this tasks list — they are authored prose in Phase 4 (T012, T016, T017, T018).
- `rag_search` MUST NOT be wired into F002 (T033) until its own tests are green (SC-003, SC-006).
- BM25 tokenisation on Arabic: whitespace split is sufficient for MVP; a dedicated Arabic tokeniser is a future upgrade noted in Assumptions.
