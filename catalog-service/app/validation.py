"""Shared helpers for the service layer: plain Python, no Flask
(REST lecture, slide 16: the domain rules are testable without a server)."""


class ValidationError(Exception):
    pass


def check_fields(data, fields, required, partial=False):
    """fields: name -> allowed type(s). required: names needed when not partial."""
    if not isinstance(data, dict):
        raise ValidationError("body must be a JSON object")
    unknown = set(data) - set(fields)
    if unknown:
        raise ValidationError(f"unknown fields: {sorted(unknown)}")
    for name, ftype in fields.items():
        if name not in data:
            if name in required and not partial:
                raise ValidationError(f"{name} is required")
        elif isinstance(data[name], bool) or not isinstance(data[name], ftype):
            raise ValidationError(f"{name} has the wrong type")
    return data
