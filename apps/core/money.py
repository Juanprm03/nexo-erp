"""Centralized monetary rounding.

Every monetary calculation in the project must round through
`quantize_money()` — never call `.quantize()` ad hoc in a model or
service, so the rounding rule stays a single, auditable decision.

Rule: 2 decimal places, ROUND_HALF_UP (conventional "round half away from
zero" — what a human invoicing clerk expects, e.g. 1.005 -> 1.01), not
Python's Decimal default (ROUND_HALF_EVEN / "banker's rounding"), which
would silently round some invoice totals down in a way that's surprising
on customer-facing documents.

Rounding strategy for invoices specifically (see apps/sales/services.py):
each line's subtotal/tax_amount/total is rounded individually (round-per-
line), and the invoice's totals are the sum of the already-rounded line
totals (never sum-then-round) — so the total displayed on the invoice
always reconciles exactly with the sum of the line amounts shown to the
customer.
"""

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
