"""Event rules: a user viewed, added to cart, or bought an existing product."""

from datetime import datetime, timezone

from ..validation import ValidationError, check_fields

FIELDS = {"productId": str, "type": str}
TYPES = ("view", "cart", "purchase")


def now_iso():
    """UTC time as an ISO string; strings in this format sort in time order."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def validate_event(data, product_exists):
    check_fields(data, FIELDS, required=set(FIELDS))
    if data["type"] not in TYPES:
        raise ValidationError(f"type must be one of {list(TYPES)}")
    if not product_exists(data["productId"]):
        raise ValidationError(f"unknown productId: {data['productId']}")
    return {**data, "timestamp": now_iso()}
