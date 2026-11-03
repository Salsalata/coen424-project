"""Event routes: /api/v1/users/{userId}/events (a sub-collection of a user,
nested one level as the lecture recommends, slide 5)."""

from flask import Blueprint, current_app, jsonify

from ..http_helpers import int_arg, json_body
from .service import validate_event

bp = Blueprint("events", __name__)


def events():
    return current_app.extensions["event_repo"]


def products():
    return current_app.extensions["product_repo"]


@bp.get("/users/<user_id>/events")
def list_events(user_id):
    limit = int_arg("limit", default=50, low=1, high=100)
    items = events().list(user_id, limit)
    return jsonify({"items": items, "total": len(items)})


@bp.post("/users/<user_id>/events")
def create_event(user_id):
    data = validate_event(json_body(), product_exists=lambda pid: products().get(pid) is not None)
    return jsonify(events().add(user_id, data)), 201
