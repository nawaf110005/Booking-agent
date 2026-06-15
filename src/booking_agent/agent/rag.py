"""In-memory RAG over a small venue/FAQ knowledge base (spec 007; Week 2-3).

No external vector DB — a dependency-free, stopword-filtered token-overlap
retriever, enough to ground answers about venues, parking, entry, accessibility,
and policies. `retrieve()` mirrors a real retriever's signature so swapping in
Chroma/FAISS/BM25 later is a drop-in.
"""

from __future__ import annotations

import re

KNOWLEDGE_BASE: list[dict[str, str]] = [
    {"topic": "parking park car", "text": "Parking: Kingdom Arena and most Riyadh/Jeddah venues "
     "have on-site paid parking; arrive 60–90 minutes early on event nights as lots fill "
     "quickly. Ride-hailing drop-off points are signposted at each gate."},
    {"topic": "gates entry doors", "text": "Gates/doors usually open about 2 hours before "
     "showtime. Bring your QR ticket (phone or printed); each QR admits its named seats "
     "once, and re-entry isn't guaranteed."},
    {"topic": "accessibility wheelchair", "text": "Accessible, step-free seating is available "
     "at all listed venues; pick wheelchair spaces when choosing seats and staff will assist "
     "at the accessible gate."},
    {"topic": "prohibited items bags camera", "text": "Prohibited: professional cameras, "
     "outside food or drink, and large bags. Small bags are subject to search at security."},
    {"topic": "age policy children", "text": "Most concerts are all-ages; under-12s must be "
     "with an adult, and some festival stages are 18+. Check the event description for limits."},
    {"topic": "refund cancel exchange", "text": "This demo doesn't process refunds yet — a "
     "refund/cancellation flow is planned. You can release an unconfirmed seat hold anytime "
     "by saying 'cancel'."},
    {"topic": "payment mada apple pay stc", "text": "Payment goes through Moyasar (Mada / "
     "Apple Pay / STC Pay) — a sandbox here, so no real charge. You confirm the full total "
     "before any payment link is issued."},
]

_STOP = {"the", "a", "an", "is", "are", "do", "does", "i", "you", "to", "of", "on", "in",
         "at", "and", "or", "my", "me", "can", "what", "whats", "s", "it", "this", "that",
         "for", "with", "there", "any", "how", "when", "where", "your", "we", "be", "about",
         "tell", "please", "want", "would", "get", "like", "some", "will"}
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _STOP and len(t) > 1}


def retrieve(query: str, k: int = 2, min_overlap: int = 1) -> list[str]:
    """Top-k knowledge snippets whose tokens overlap the query (>= min_overlap)."""
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for doc in KNOWLEDGE_BASE:
        overlap = len(q & _tokens(doc["topic"] + " " + doc["text"]))
        if overlap >= min_overlap:
            scored.append((overlap, doc["text"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:k]]
