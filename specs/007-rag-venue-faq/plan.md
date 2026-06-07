# Implementation Plan: RAG over Venue FAQ & Policy

**Branch**: `007-rag-venue-faq` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-rag-venue-faq/spec.md`

## Summary

Add a grounded retrieval layer that answers policy and logistics questions from
a small bilingual Markdown corpus under `docs/venue-faq/`. The default backend
is pure-Python in-memory BM25 (no model download, fully offline). A Chroma +
embeddings backend is available behind a `RAG_BACKEND=chroma` config flag
without changing the `rag_search` tool contract. The F002 booking agent routes
`ask_policy` intent to `rag_search` and cites the source document in its reply.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `rank-bm25` (BM25 default); `chromadb`, `sentence-transformers` (optional extra `rag-chroma`); Pydantic v2; `python-frontmatter` (Markdown loading)

**Storage**: In-memory BM25 index (no persistence); optional Chroma persistent collection at `data/chroma/` when `RAG_BACKEND=chroma`

**Testing**: pytest, pytest-cov; BM25 tests require zero network access

**Target Platform**: Local backend (Windows/macOS/Linux); offline-capable for BM25 path

**Project Type**: Single Python project (`src/booking_agent/`); adds `rag/` sub-package

**Performance Goals**: `rag_search` responds in < 200ms on BM25 for a corpus of ≤ 50 passages; Chroma response ≤ 500ms

**Constraints**: BM25 path MUST NOT import `chromadb` or `sentence-transformers`; no network calls during retrieval; corpus rebuild at startup acceptable for MVP corpus size

**Scale/Scope**: MVP corpus ≤ 50 passages across ≤ 10 venue-faq Markdown files; bilingual Arabic/English content

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies |
|-----------|---------------------------|
| I. Confirmation Before Payment | RAG answers policy questions only; it never touches the payment flow or bypasses the HITL gate. ✅ |
| II. Atomic, Time-Bounded Holds | No seat or hold mutations; `rag_search` is a read-only lookup. ✅ |
| III. Tools Are Python Functions | `rag_search` is an in-repo typed Python function; corpus is local Markdown files; no external ticketing API dependency. ✅ |
| IV. Exact, Auditable Money | No money computation in this slice; RAG answers policy text only. ✅ |
| V. Tamper-Evident Tickets | No ticket or payment data touched; irrelevant to this slice. ✅ |
| VI. Test-First | `rag_search` unit tests (happy path, no-match, bilingual, venue filter, empty corpus) are written and must fail before the retriever is implemented. ✅ |
| VII. Observable Reasoning | Every `rag_search` call is logged with timestamp, tool name, query, venue filter, result count, and top source via the existing audit infrastructure. ✅ |
| VIII. MVP First | BM25 in-memory is the default; Chroma is a documented flag-controlled upgrade, not mixed in the MVP path. ✅ |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/007-rag-venue-faq/
├── plan.md              # This file
├── spec.md              # Feature spec
└── tasks.md             # Task breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
src/booking_agent/
└── rag/
    ├── __init__.py              # exports: rag_search, build_corpus, reload_corpus
    ├── corpus.py                # load docs/venue-faq/*.md → list[Passage]; passage splitting by H2/H3
    ├── retriever.py             # Retriever ABC; BM25Retriever (default); ChromaRetriever (optional)
    └── tool.py                  # rag_search(query, venue?, top_k) → list[RagResult]; logging; validation

docs/
└── venue-faq/
    ├── refund-policy.md         # Bilingual refund/cancellation/exchange policy
    ├── parking.md               # Bilingual parking and transport overview
    ├── gates-entry.md           # Bilingual gates, entry times, bag check
    ├── accessibility.md         # Bilingual accessibility and wheelchair info
    ├── prohibited-items.md      # Bilingual prohibited items list
    ├── directions-transport.md  # Bilingual transport and directions per venue
    ├── age-rating.md            # Bilingual age ratings per event category
    ├── dress-code.md            # Bilingual dress code policy
    ├── re-entry.md              # Bilingual re-entry policy
    ├── kingdom-arena.md         # Venue-specific FAQ for Kingdom Arena
    └── al-awwal-park.md         # Venue-specific FAQ for Al-Awwal Park

tests/
└── test_rag/
    ├── __init__.py
    ├── conftest.py              # fixture: tmp corpus dir + sample .md files
    ├── test_corpus.py           # passage loading, heading splits, bilingual content, missing dir
    ├── test_retriever_bm25.py   # BM25 happy path, no-match, venue filter, empty corpus, bilingual
    └── test_tool.py             # rag_search validation, logging, no-match reply path, RAG_BACKEND flag
```

**Structure Decision**: `src/booking_agent/rag/` is added as a sibling to the existing `db/`, `tools/`, `agent/` sub-packages established in F001. The corpus lives in `docs/venue-faq/` (Markdown, version-controlled). No new top-level project is introduced; this is a pure extension of the single-project layout.

## Phase 0 — Research / Decisions

- **BM25 library**: `rank-bm25` (MIT licence, pure Python, no compilation). Provides `BM25Okapi`. Tokenisation: whitespace split with lower-casing; handles Arabic script without a dedicated tokeniser for MVP.
- **Passage splitting**: Split each `.md` file on H2 (`## `) and H3 (`### `) boundaries. Each split section becomes one `Passage` with `source=filename` and `venue_slug` derived from the filename stem. Minimum passage length: 20 characters (discard headings that are empty stubs).
- **Chroma upgrade path**: `ChromaRetriever` is imported lazily inside a `try/except ImportError` block guarded by `if settings.RAG_BACKEND == "chroma"`. The BM25 path never executes that block. Chroma collection name: `venue-faq`. Embedding function: `sentence-transformers/all-MiniLM-L6-v2` by default, overridable via `RAG_EMBEDDING_MODEL`.
- **No-match threshold**: BM25 returns a score of 0.0 for a query with no token overlap. `RAG_MIN_SCORE=0.0` means any passage with score > 0 is a match; the tool returns an empty list if all scores are 0. For Chroma, `RAG_MIN_SCORE=0.3` (cosine similarity).
- **Logging**: Reuses the `audit_log` table pattern from F001. A single `INFO`-level log line per call is written with structured fields; PII in queries is not logged at DEBUG level.

## Phase 1 — Design Artifacts

- `RagResult` Pydantic model: `passage: str`, `source: str`, `score: float`. Returned by `rag_search` regardless of backend.
- `Passage` dataclass: `text: str`, `source: str`, `venue_slug: str | None`.
- `Retriever` ABC: `build(passages: list[Passage]) -> None` and `retrieve(query: str, venue_slug: str | None, top_k: int) -> list[RagResult]`.
- Config additions to `src/booking_agent/config.py`: `RAG_BACKEND: Literal["bm25", "chroma"] = "bm25"`, `RAG_CORPUS_DIR: Path = Path("docs/venue-faq")`, `RAG_MIN_SCORE: float = 0.0`, `RAG_TOP_K: int = 3`, `RAG_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"`.
- The `rag_search` tool is registered in the F002 agent tool list as a LangChain `Tool` object with name `rag_search` and description "Search venue FAQ and policy corpus. Use for any policy, logistics, parking, accessibility, refund, or rules question."

## Complexity Tracking

No constitution violations — table intentionally empty.
