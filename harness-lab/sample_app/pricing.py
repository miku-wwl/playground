"""Tiny example application used by the Harness learning exercise."""


def apply_discount(price: float, discount_percent: float) -> float:
    """Return a price after applying a percentage discount.

    This intentionally contains a bug for a later phase to fix.
    """
    return price * (1 + discount_percent / 100)
