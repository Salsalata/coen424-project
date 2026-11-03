"""The only route of this service. It does not know whether v1 or v2 answers:
the service layer decides, and the response shape is the same."""

from flask import Blueprint, abort, current_app, jsonify, request

from .service import AgentUnavailable

bp = Blueprint("recommendations", __name__)


def _limit():
    raw = request.args.get("limit", "5")
    try:
        value = int(raw)
    except ValueError:
        abort(400, description="limit must be an integer")
    if not 1 <= value <= 10:
        abort(400, description="limit must be between 1 and 10")
    return value


@bp.get("/users/<user_id>/recommendations")
def list_recommendations(user_id):
    service = current_app.extensions["recommendations"]
    try:
        return jsonify(service.recommend(user_id, _limit()))
    except AgentUnavailable as exc:
        abort(503, description=str(exc))
