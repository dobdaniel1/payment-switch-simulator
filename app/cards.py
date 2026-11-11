import hashlib
import hmac
from datetime import date


def luhn_valid(pan: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(pan)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def mask_pan(pan: str) -> str:
    return pan[:6] + "*" * (len(pan) - 10) + pan[-4:]


def hash_pan(pan: str, key: str) -> str:
    """Keyed hash so the same card can be matched without storing the PAN."""
    return hmac.new(key.encode(), pan.encode(), hashlib.sha256).hexdigest()


def is_expired(expiry_yymm: str, today: date) -> bool:
    """Cards are valid through the last day of the expiry month."""
    year, month = 2000 + int(expiry_yymm[:2]), int(expiry_yymm[2:])
    return (year, month) < (today.year, today.month)
