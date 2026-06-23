"""Exact money helpers (Constitution IV).

All amounts are integer minor units (halalas; 1 SAR = 100 halalas). Percentages
are integer basis points (1500 = 15%). Rounding is half-up. No floats touch the
arithmetic, so quotes are reproducible to the halala.
"""

from __future__ import annotations

HALALA_PER_SAR = 100


def pct_bps(amount: int, bps: int) -> int:
    """`amount * bps / 10000`, rounded half-up, as integer halalas.

    Assumes non-negative inputs (all money in this system is non-negative).
    """

    return (amount * bps + 5_000) // 10_000


def to_sar(halalas: int) -> float:
    """Halalas -> SAR as a float, for display only (never for arithmetic)."""

    return halalas / HALALA_PER_SAR


def sar_str(halalas: int, currency: str = "SAR") -> str:
    """Human-readable amount, e.g. 312800 -> '3,128.00 SAR'."""

    return f"{halalas / HALALA_PER_SAR:,.2f} {currency}"
