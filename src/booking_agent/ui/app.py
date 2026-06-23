"""Minimal Streamlit chat UI for the Booking-Agent runnable slice (F001).

Drives the core booking loop in-process using the typed tools:
search -> member -> quote -> seat map -> atomic hold -> HITL confirmation.

The conversational LLM agent (intent/extraction/free-form chat) is F002; the
payment + ticket steps after confirmation are F003. This page demonstrates the
tool surface and the human-in-the-loop gate end to end without an API key.

Run:  streamlit run src/booking_agent/ui/app.py
"""

from __future__ import annotations

from datetime import datetime

from booking_agent.config import settings
from booking_agent.db import SessionLocal
from booking_agent.db.base import Base, ensure_aware, utcnow
from booking_agent.db.session import engine
from booking_agent.tools.errors import ToolError
from booking_agent.tools.events import search_events
from booking_agent.tools.holds import place_seat_hold
from booking_agent.tools.members import lookup_member_by_email
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote, get_categories_with_pricing
from booking_agent.tools.seatmap import render_seat_map

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Streamlit is not installed. Run: uv pip install -e '.[ui]'") from exc


def _ensure_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        from booking_agent.db.models import Event
        from booking_agent.db.seed import seed_demo

        if s.query(Event).count() == 0:
            seed_demo(s)
            s.commit()


def main() -> None:
    st.set_page_config(page_title="Booking-Agent", page_icon="🎫", layout="centered")
    _ensure_db()

    ss = st.session_state
    ss.setdefault("email", "nawaf@example.com")
    ss.setdefault("event_id", None)
    ss.setdefault("category", None)
    ss.setdefault("quantity", 2)
    ss.setdefault("hold", None)
    ss.setdefault("confirmed", False)

    st.title("🎫 Booking-Agent")
    st.caption("From “I want a ticket” to ticket in your inbox — one conversation.")

    llm_key = settings.anthropic_api_key or settings.openai_api_key
    if llm_key:
        st.info("🟢 LLM key detected — the conversational agent (F002) can be enabled.")
    else:
        st.warning("🟠 Rule-based slice (F001). The LLM chat agent is F002; payment/ticket is F003.")

    # --- Buyer / membership ---
    with st.sidebar:
        st.header("You")
        ss.email = st.text_input("Email", ss.email)
        member = None
        if ss.email:
            with SessionLocal() as s:
                member = lookup_member_by_email(s, ss.email)
            if member.is_member:
                st.success(
                    f"{member.tier.value.title()} member — {member.discount_label} off, "
                    f"up to {member.ticket_cap} tickets"
                )
            else:
                st.info("Not a member — standard pricing, up to 4 tickets")
        tier = member.tier if member else None
        cap = member.ticket_cap if member else 4

    # --- Step 1: find an event ---
    st.subheader("1) Find your event")
    query = st.text_input("What event are you looking for?", "Coldplay")
    with SessionLocal() as s:
        results = search_events(s, query) if query else []
    if results:
        labels = {f"{e.title} — {e.city} — {e.starts_at:%d %b %Y}": e.id for e in results}
        choice = st.radio("Matches", list(labels), index=0)
        ss.event_id = labels[choice]
    else:
        st.write("No matches — try another search.")
        return

    # --- Step 2: categories + quote ---
    st.subheader("2) Pick a category & quantity")
    with SessionLocal() as s:
        cats = get_categories_with_pricing(s, ss.event_id, tier)
    for c in cats:
        price = (
            f"~~{c.base_sar}~~ → **{c.discounted_sar}**"
            if c.discounted_price != c.base_price
            else f"**{c.base_sar}**"
        )
        st.markdown(f"- {c.category.value.title()}: {price}  ·  {c.available} available")

    cat_names = [c.category.value for c in cats]
    ss.category = st.selectbox("Category", cat_names, index=0)
    ss.quantity = st.number_input("How many tickets?", min_value=1, max_value=cap, value=min(ss.quantity, cap))

    try:
        with SessionLocal() as s:
            quote = compute_quote(s, ss.event_id, ss.category, int(ss.quantity), tier)
    except ToolError as exc:
        st.error(str(exc))
        return

    st.markdown("**Quote**")
    for line in quote.summary_lines():
        st.write(line)

    # --- Step 3: seat map + selection ---
    st.subheader("3) Choose seats")
    with SessionLocal() as s:
        try:
            png = render_seat_map(s, ss.event_id, ss.category)
            st.image(png, caption=f"{ss.category.title()} seat map (green=available, amber=held, grey=sold)")
        except ToolError as exc:
            st.warning(str(exc))
    seat_text = st.text_input(f"Enter {int(ss.quantity)} seat IDs (comma-separated, e.g. G12,G13)", "")
    seat_ids = [s.strip().upper() for s in seat_text.split(",") if s.strip()]

    # --- Step 4: atomic hold ---
    st.subheader("4) Hold your seats")
    if st.button("Hold seats (10-minute timer)"):
        if len(seat_ids) != int(ss.quantity):
            st.error(f"Please enter exactly {int(ss.quantity)} seat IDs.")
        else:
            try:
                with SessionLocal() as s:
                    hold = place_seat_hold(s, ss.event_id, seat_ids, ss.email)
                    s.commit()
                ss.hold = {
                    "token": hold.token,
                    "seat_ids": hold.seat_ids,
                    "expires_at": hold.expires_at.isoformat(),
                }
                ss.confirmed = False
                st.success(f"Held {', '.join(hold.seat_ids)} until {hold.expires_at:%H:%M:%S} UTC")
            except ToolError as exc:
                st.error(f"Could not hold those seats: {exc}")

    # --- Step 5: HITL confirmation (Constitution I) ---
    if ss.hold:
        st.subheader("5) Confirm before payment")
        expires = ensure_aware(datetime.fromisoformat(ss.hold["expires_at"]))
        remaining = int((expires - utcnow()).total_seconds())
        if remaining <= 0:
            st.error("⏰ Your hold expired. Please hold seats again.")
            ss.hold = None
            return
        st.metric("Hold expires in", f"{remaining // 60}m {remaining % 60}s")

        st.markdown(
            f"**{quote.event_title}**\n\n"
            f"- Seats: {', '.join(ss.hold['seat_ids'])}\n"
            f"- {int(ss.quantity)}× {ss.category.title()}\n"
            f"- Subtotal (after discount): {sar_str(quote.net_subtotal)}\n"
            f"- VAT 15%: {sar_str(quote.vat)}\n"
            f"- **Total: {sar_str(quote.total)}**"
        )
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirm & proceed to payment"):
            ss.confirmed = True
        if col2.button("✖ Cancel hold"):
            ss.hold = None
            st.rerun()

        if ss.confirmed:
            st.success(
                "Confirmed. In the full flow this is where the agent completes the "
                "virtual checkout (sandbox — no real charge) and emails your signed "
                "PDF/QR ticket. The HITL gate above is the non-negotiable "
                "Constitution Principle I."
            )


main()
