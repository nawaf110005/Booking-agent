"""Date-window helpers for natural-language discovery ("this weekend", etc.).

The weekend is the Saudi **Friday–Saturday** (not Sat–Sun). Shared by the agent
(to filter the catalog) and the seed (to guarantee a real weekend event exists).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def weekend_range(now: datetime) -> tuple[date, date]:
    """The current/upcoming Saudi weekend (Friday, Saturday) as inclusive dates."""

    wd = now.weekday()  # Mon=0 … Sun=6
    if wd == 5:  # Saturday -> this weekend's Friday was yesterday
        friday = now.date() - timedelta(days=1)
    elif wd == 4:  # Friday -> today
        friday = now.date()
    else:  # Sun–Thu -> the upcoming Friday
        friday = now.date() + timedelta(days=(4 - wd) % 7)
    return friday, friday + timedelta(days=1)


def when_range(when: str | None, now: datetime) -> tuple[date, date] | None:
    """Map a temporal keyword to an inclusive [from, to] date window, or None."""

    key = (when or "").strip().lower()
    today = now.date()
    if key == "weekend":
        return weekend_range(now)
    if key == "today":
        return today, today
    if key == "tomorrow":
        return today + timedelta(days=1), today + timedelta(days=1)
    if key in ("week", "this week"):
        return today, today + timedelta(days=7)
    return None


def when_label(when: str | None) -> str:
    key = (when or "").strip().lower()
    return {
        "weekend": "this weekend",
        "today": "today",
        "tomorrow": "tomorrow",
        "week": "this week",
    }.get(key, "right now")
