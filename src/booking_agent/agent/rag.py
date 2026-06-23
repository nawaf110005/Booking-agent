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
    {"topic": "payment checkout virtual sandbox", "text": "Payment is a secure virtual "
     "checkout — a sandbox here, so no real charge. You review the full total and approve "
     "it before anything is paid, then you get your QR ticket."},
]

_STOP = {"the", "a", "an", "is", "are", "do", "does", "i", "you", "to", "of", "on", "in",
         "at", "and", "or", "my", "me", "can", "what", "whats", "s", "it", "this", "that",
         "for", "with", "there", "any", "how", "when", "where", "your", "we", "be", "about",
         "tell", "please", "want", "would", "get", "like", "some", "will",
         # filler/location words — must never anchor an FAQ match (the "here"→payment bug)
         "here", "coming", "come", "available", "saudi", "arabia", "ksa", "near", "soon",
         "now", "back", "again", "really", "just", "also", "still", "yet", "happening",
         # generic booking words — too vague to anchor an FAQ match
         "ticket", "tickets", "book", "booking", "event", "events", "show", "shows",
         "seat", "seats", "need", "buy", "see", "watch", "find", "looking", "go", "going"}
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _STOP and len(t) > 1}


def retrieve(query: str, k: int = 2, min_overlap: int = 1) -> list[str]:
    """Top-k knowledge snippets whose tokens overlap the query (>= min_overlap).

    Content-rich queries (>= 4 meaningful tokens) require at least 2 overlapping
    tokens, so a single coincidental word can't return an unrelated FAQ entry.
    Short questions ("parking?", "refund") still match on one token.
    """
    q = _tokens(query)
    if not q:
        return []
    need = max(min_overlap, 2 if len(q) >= 4 else 1)
    scored = []
    for doc in KNOWLEDGE_BASE:
        overlap = len(q & _tokens(doc["topic"] + " " + doc["text"]))
        if overlap >= need:
            scored.append((overlap, doc["text"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:k]]
