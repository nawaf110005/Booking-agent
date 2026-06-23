"""Per-turn sentiment classification (adapt on frustration).

Rule-based and dependency-free so it runs offline and is deterministic in tests;
the agent consumes it every turn, stores it in session memory, and logs it to the
interaction log so frustration is visible and the strategy can adapt.
"""

from __future__ import annotations

_FRUSTRATED = ("this is dumb", "useless", "ridiculous", "frustrat", "angry", "ugh",
               "forget it", "never mind", "come on", "seriously", "stop ignoring",
               "not working", "doesn't work", "won't work", "hate this")
_NEGATIVE = ("bad", "worst", "hate", "annoy", "terrible", "awful", "slow", "confusing",
             "confused", "wrong", "broken", "disappoint")
_POSITIVE = ("thanks", "thank you", "great", "awesome", "perfect", "love", "nice",
             "cool", "amazing", "good", "yes please", "wonderful")


def classify_sentiment(message: str | None) -> str:
    """One of: 'frustrated', 'negative', 'positive', 'neutral'."""
    text = (message or "").lower()
    if not text.strip():
        return "neutral"
    if any(w in text for w in _FRUSTRATED):
        return "frustrated"
    if any(w in text for w in _NEGATIVE):
        return "negative"
    if any(w in text for w in _POSITIVE):
        return "positive"
    return "neutral"


def is_unhappy(sentiment: str | None) -> bool:
    return sentiment in ("frustrated", "negative")
