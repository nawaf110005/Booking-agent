"""End-to-end smoke of the *agent loop* (no API key, no network).

Drives `policy.respond` through a full booking — search → member → quote → seat
map → atomic hold → HITL confirm → pay → ticket — then prints the observable
reasoning trace (tool calls + state transitions, PII redacted). Handy as a demo
and as a quick regression check after touching the agent.

Run:  python scripts/agent_smoke.py
"""

from __future__ import annotations

import contextlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from booking_agent.agent import observability as obs
from booking_agent.agent.policy import respond
from booking_agent.agent.state import ConversationState
from booking_agent.db import models  # noqa: F401
from booking_agent.db.base import Base
from booking_agent.db.seed import seed_demo
from booking_agent.tools.payments import pay_booking


def main() -> int:
    engine = create_engine("sqlite://", future=True,
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False, future=True)()
    seed_demo(db)
    db.commit()
    obs.reset()

    st = ConversationState(session_id="smoke")
    script = [
        "4 gold tickets for Coldplay in Riyadh, nawaf@example.com",
        "G3, G4, G5, G6",
        "confirm",
    ]
    print("=== agent loop smoke ===\n")
    for msg in script:
        r = respond(db, st, msg)
        print(f'User : {msg}')
        print(f'Agent: [{r["step"]}] {r["reply"].splitlines()[0]}\n')

    assert st.step == "payment" and st.booking_id, "did not reach payment"
    ticket = pay_booking(db, st.booking_id)
    print(f"Paid → ticket seats {ticket['seats']}, QR {ticket['qr_url']}\n")

    print("--- observable reasoning trace (Constitution VII) ---")
    for e in obs.events("smoke"):
        if e["kind"] == "tool_call":
            extra = {k: v for k, v in e.items()
                     if k not in {"ts", "kind", "session_id", "turn", "tool"}}
            print(f"  tool  t{e['turn']}  {e['tool']:<14} {extra}")
        else:
            print(f"  move  t{e['turn']}  {e['from']} -> {e['to']}")
    print("\n=== smoke complete ===")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
