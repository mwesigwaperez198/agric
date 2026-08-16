"""Automated commission engine.

Splits a transaction into platform commission and farmer net before funds are
released from escrow.
"""

from api.app.config import settings


def split_transaction(total: float, rate: float | None = None) -> tuple[float, float]:
    """Returns (commission_amount, farmer_net)."""
    rate = settings.platform_commission_rate if rate is None else rate
    rate = max(0.0, min(rate, 0.5))
    commission = round(total * rate, 2)
    return commission, round(total - commission, 2)
