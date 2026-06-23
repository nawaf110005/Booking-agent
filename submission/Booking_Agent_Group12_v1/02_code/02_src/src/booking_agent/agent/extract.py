"""Rule-based slot extractor (offline fallback for the LLM).

Deterministic and dependency-free so the chat books tickets even with no API
key. The LLM extractor in `llm.py` overlays richer NLU when a key is set.
"""

from __future__ import annotations

import re

from booking_agent.agent.schemas import BookingParams

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
SEAT_RE = re.compile(r"\b([A-Za-z]{1,2}\d{1,3})\b")
HASH_ID_RE = re.compile(r"#\s*(\d+)")
EVENT_NUM_RE = re.compile(r"\bevent\s+(\d+)\b")
# Arabic ticket/seat words so "٤ تذاكر" / "تذكرتين" parse like "4 tickets".
QTY_RE = re.compile(
    r"\b(\d+)\s*(?:x|×)?\s*(?:vip|gold|silver|standing|tickets?|seats?|pax|people|persons?"
    r"|تذاكر|تذكرة|تذكره|بطاقات|مقاعد|اشخاص|أشخاص)\b"
)
ALL_DIGITS_RE = re.compile(r"^\s*\d+\s*$")

# Western digits for Arabic-Indic numerals (٠-٩ and ۰-۹), so quantities written in
# Arabic script ("٤") are parsed too. Applied to a copy used only for number parsing.
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

CITY_MAP = {
    "riyadh": "Riyadh",
    "الرياض": "Riyadh",
    "jeddah": "Jeddah",
    "jedda": "Jeddah",
    "جدة": "Jeddah",
}

# Map user words to a catalog search query that the events tool will match.
# Includes common Arabic spellings so the offline fallback understands Arabic too.
EVENT_KEYWORDS = {
    "coldplay": "coldplay",
    "كولدبلاي": "coldplay",
    "كولد بلاي": "coldplay",
    "derby": "derby",
    "al-hilal": "derby",
    "al hilal": "derby",
    "hilal": "derby",
    "al-nassr": "derby",
    "al nassr": "derby",
    "nassr": "derby",
    "football": "derby",
    "soccer": "derby",
    "ديربي": "derby",
    "الهلال": "derby",
    "النصر": "derby",
    "كرة القدم": "derby",
    "مباراة": "derby",
    "leap": "leap",
    "tech conference": "leap",
    "conference": "leap",
    "مؤتمر": "leap",
    "soundstorm": "soundstorm",
    "mdlbeast": "soundstorm",
    "festival": "soundstorm",
    "ساوندستورم": "soundstorm",
    "مهرجان": "soundstorm",
}

CATEGORIES = ("vip", "gold", "silver", "standing")
# Arabic category words -> canonical English category.
CATEGORY_AR = {
    "في اي بي": "vip",
    "ذهبي": "gold",
    "ذهبية": "gold",
    "فضي": "silver",
    "فضية": "silver",
    "واقف": "standing",
    "وقوف": "standing",
}

BROWSE_PHRASES = (
    "what's on", "whats on", "what is on", "show me", "browse", "events",
    "this weekend", "what do you have", "anything", "recommend",
)
CONFIRM_WORDS = (
    "confirm", "yes", "yeah", "yep", "sure", "ok", "okay", "proceed",
    "pay", "go ahead", "do it", "نعم", "اكد", "أكد",
)
CANCEL_WORDS = ("cancel", "no", "nope", "never mind", "stop", "لا", "الغاء", "إلغاء")

# Platform questions (FAQ / meta / pricing / policy) -> route to the answerer.
ASK_KEYWORDS = (
    "discount", "member", "membership", "loyalty", "refund", "vat", "tax", "cost",
    "how much", "how do", "how does", "how many", "what is", "what are you",
    "who made", "who built", "who created", "who implemented", "who developed",
    "is there", "are there", "parking", "policy", "accessib", "payment",
    "mada", "apple pay", "stc pay", "what can you", "about you",
    "describe", "description", "detail", "tell me about", "what time",
    "when is", "where is", "venue", "located", "location", "about it", "about this",
    # Arabic question / FAQ words.
    "كم", "سعر", "السعر", "كيف", "وش", "ايش", "متى", "وين", "أين", "خصم",
    "عضوية", "تخفيض", "ضريبة", "دفع", "استرجاع", "موقع", "مكان",
)
# Event-type words; a question containing one is a discovery question.
TYPE_WORDS = (
    "football", "soccer", "match", "matches", "game", "concert", "gig",
    "theatre", "theater", "play", "comedy", "festival", "sports", "conference",
)

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
}


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def heuristic_extract(message: str, step: str = "") -> BookingParams:
    text = message or ""
    params = BookingParams()

    # Email first, then strip it so it can't pollute seat/number parsing.
    m = EMAIL_RE.search(text)
    if m:
        params.email = m.group(0).lower()
    cleaned = EMAIL_RE.sub(" ", text)
    low = cleaned.lower().strip()
    # Number parsing uses a copy with Arabic-Indic digits folded to ASCII ("٤" -> "4").
    low_n = low.translate(_AR_DIGITS)

    # Event id from a card click (#3) or "event 3".
    m = HASH_ID_RE.search(cleaned) or EVENT_NUM_RE.search(low)
    if m:
        params.event_id = int(m.group(1))

    # City.
    for kw, city in CITY_MAP.items():
        if kw in low:
            params.city = city
            break

    # Category (English word-boundary match, then Arabic substrings).
    for cat in CATEGORIES:
        if _has_word(low, cat):
            params.category = cat
            break
    if not params.category:
        # Word-boundary match (not substring) so "واقف" (standing) doesn't fire on
        # "مواقف" (parking) and "فضي" (silver) doesn't fire inside other words.
        for kw, cat in CATEGORY_AR.items():
            if _has_word(low, kw):
                params.category = cat
                break

    # Event query keyword.
    for kw, query in EVENT_KEYWORDS.items():
        if kw in low:
            params.event_query = query
            break

    # Unknown event name: if no known event matched, capture what the user is after —
    # "ticket(s)/seats for|to X" or "see/watch X" — so the agent can say "I couldn't
    # find X" instead of ignoring the request or answering an unrelated FAQ.
    if not params.event_query:
        m_ev = re.search(
            r"\b(?:tickets?|seats?|book|attend)\s+(?:for|to)\s+(?:the\s+|a\s+)?([a-z0-9][\w '&\-]*)", low
        ) or re.search(r"\b(?:see|watch)\s+(?:the\s+|a\s+)?([a-z0-9][\w '&\-]*)", low)
        if m_ev:
            cand = re.sub(r"\s+(in|on|this|tonight|today|tomorrow|please)\b.*$", "", m_ev.group(1)).strip(" ?.!,-")
            cand = " ".join(cand.split()[:4])
            if cand and cand not in CATEGORIES and not _has_word(low, "cancel"):
                params.event_query = cand

    # Seat ids (e.g. "G3, G4"). Exclude pure category words.
    seats = [s.upper() for s in SEAT_RE.findall(cleaned)]
    if seats:
        params.seat_ids = seats

    # Quantity: "4 tickets" / "٤ تذاكر", a number word, or a bare integer.
    if (mq := QTY_RE.search(low_n)):
        params.quantity = int(mq.group(1))
    elif low in NUMBER_WORDS:
        params.quantity = NUMBER_WORDS[low]
    elif ALL_DIGITS_RE.match(low_n):
        params.quantity = int(low_n.strip())

    # Temporal window for discovery ("this weekend", "today", …).
    if "weekend" in low:
        params.when = "weekend"
    elif "tomorrow" in low or "بكرة" in low or "غدا" in low:
        params.when = "tomorrow"
    elif "this week" in low or "هذا الأسبوع" in low:
        params.when = "week"
    elif _has_word(low, "today") or "اليوم" in low:
        params.when = "today"

    # Intent verbs. Questions never count as cancel/confirm (so "how do I pay?"
    # is a question, not a confirmation).
    is_question = text.strip().endswith(("?", "؟"))
    has_slot = bool(params.category or params.seat_ids or params.quantity or params.event_id)
    browse_phrase = any(p in low for p in BROWSE_PHRASES)
    faq = any(k in low for k in ASK_KEYWORDS)
    type_q = is_question and any(w in low for w in TYPE_WORDS)
    # A bare question that isn't an explicit catalog browse → answer it.
    generic_q = is_question and not browse_phrase and not params.event_query

    if not is_question and any(_has_word(low, w) for w in CANCEL_WORDS):
        params.intent = "cancel"
    elif not is_question and any(_has_word(low, w) for w in CONFIRM_WORDS):
        params.intent = "confirm"
    elif not has_slot and (faq or type_q or generic_q):
        params.intent = "ask"
    elif browse_phrase or params.when:
        params.intent = "browse"

    return params
