from __future__ import annotations

import contextlib
import sys

# Force UTF-8 stdout so rich tables and Unicode (Arabic, arrows) don't crash the
# cp1252 Windows console.
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

import typer
from rich.console import Console
from rich.table import Table

from booking_agent.config import settings
from booking_agent.db import SessionLocal, engine
from booking_agent.db.base import Base
from booking_agent.db.enums import MemberTier
from booking_agent.db.seed import seed_demo
from booking_agent.tools.events import search_events
from booking_agent.tools.holds import release_expired_holds
from booking_agent.tools.members import lookup_member_by_email
from booking_agent.tools.money import sar_str
from booking_agent.tools.pricing import compute_quote

app = typer.Typer(help="Booking-Agent operations CLI.")
console = Console()


@app.command("init-db")
def init_db() -> None:
    """Create all tables (idempotent). Use Alembic for production migrations."""

    Base.metadata.create_all(bind=engine)
    console.print(f"[green]OK[/green] schema created at {settings.database_url}")


@app.command("seed")
def seed() -> None:
    """Load the deterministic demo catalog. Safe to re-run."""

    with SessionLocal() as session:
        seed_demo(session)
        session.commit()
    console.print("[green]OK[/green] demo catalog loaded")


@app.command("search")
def search(query: str = typer.Argument(..., help="Free-text event query")) -> None:
    """Search the events catalog."""

    with SessionLocal() as session:
        events = search_events(session, query)
    if not events:
        console.print(f"[yellow]No events match[/yellow] {query!r}")
        return
    table = Table(title=f"Events matching {query!r}")
    table.add_column("ID", justify="right")
    table.add_column("Title")
    table.add_column("When")
    table.add_column("Venue")
    table.add_column("City")
    for e in events:
        table.add_row(str(e.id), e.title, e.starts_at.strftime("%Y-%m-%d %H:%M"), e.venue, e.city)
    console.print(table)


@app.command("quote")
def quote(
    event_id: int = typer.Argument(..., help="Event ID"),
    category: str = typer.Argument(..., help="vip | gold | silver | standing"),
    quantity: int = typer.Argument(..., help="Number of tickets"),
    email: str = typer.Option(None, "--email", help="Buyer email (applies member discount)"),
) -> None:
    """Compute an itemised quote (base + member discount + VAT 15%)."""

    with SessionLocal() as session:
        tier: MemberTier | None = None
        if email:
            member = lookup_member_by_email(session, email)
            tier = member.tier
            if member.is_member:
                console.print(f"[cyan]{member.tier.value.title()} member[/cyan] — {member.discount_label} off, cap {member.ticket_cap}")
        q = compute_quote(session, event_id, category, quantity, tier)
    table = Table(title=f"Quote — {q.event_title}")
    table.add_column("Line")
    table.add_column("Amount", justify="right")
    for line in q.summary_lines():
        if ": " in line:
            label, _, amount = line.rpartition(": ")
        else:
            label, amount = line, ""
        table.add_row(label, amount)
    console.print(table)
    console.print(f"[bold green]TOTAL: {sar_str(q.total, q.currency)}[/bold green]")


@app.command("sweep")
def sweep() -> None:
    """Release expired seat holds (the TTL sweeper)."""

    with SessionLocal() as session:
        n = release_expired_holds(session)
        session.commit()
    console.print(f"[green]OK[/green] released {n} expired hold(s)")


if __name__ == "__main__":  # pragma: no cover
    app()
