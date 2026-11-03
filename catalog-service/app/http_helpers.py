"""Small HTTP helpers shared by the route modules (REST lecture, slide 17)."""

from flask import abort, request


def json_body():
    """415 if the body is not JSON, 400 if it is malformed: checked before validation."""
    if not request.is_json:
        abort(415, description="JSON body required")
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="malformed JSON")
    return data


def int_arg(name, default, low, high):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        abort(400, description=f"{name} must be an integer")
    if not low <= value <= high:
        abort(400, description=f"{name} must be between {low} and {high}")
    return value
