"""Product rules: what a valid product looks like (REST lecture, slide 16)."""

from ..validation import ValidationError, check_fields

FIELDS = {
    "name": str,
    "category": str,
    "price": (int, float),
    "description": str,
    "popularity": int,
}
REQUIRED = {"name", "category", "price"}


def validate_product(data, partial=False):
    """Full check for POST; partial=True for PATCH (only the fields sent)."""
    check_fields(data, FIELDS, REQUIRED, partial)
    for name in ("name", "category"):
        if name in data and not data[name].strip():
            raise ValidationError(f"{name} must not be empty")
    if data.get("price", 0) < 0:
        raise ValidationError("price must be >= 0")
    if data.get("popularity", 0) < 0:
        raise ValidationError("popularity must be >= 0")
    if "category" in data:
        data = {**data, "category": data["category"].strip().lower()}
    if not partial:
        data = {"description": "", "popularity": 0, **data}
    return data
