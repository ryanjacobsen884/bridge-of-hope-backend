"""FX helpers.

Fee estimates only, shown to the donor before submission (per spec: "Cover
the fee" checkbox must show a real number). Not used for settlement
accounting — `donations.fx_rate`/`settled_kes_minor` are populated from the
actual provider payload at confirmation time, never guessed.
"""
from __future__ import annotations

# Card-processing fee approximation (percentage + fixed, in the charge currency).
# Matches the placeholder used in the approved give.html: 3.9% + $0.30-equivalent.
_FEE_PERCENT = 0.039
_FEE_FIXED_MINOR = {"USD": 30, "GBP": 25, "KES": 0}


def estimate_cover_fee_minor(amount_minor: int, currency: str) -> int:
    fixed = _FEE_FIXED_MINOR.get(currency.upper(), 30)
    return round(amount_minor * _FEE_PERCENT) + fixed
