"""Problem Details errors (RFC 9457), as in catalog-service and the REST
lecture (slide 19). A catalog outage becomes 503: the server is not wrong,
a service it depends on is unavailable, so a client may retry later."""

from flask import jsonify
from werkzeug.exceptions import HTTPException, MethodNotAllowed

from .catalog_client import ApiError, CatalogUnavailable


def problem(status, title, detail):
    resp = jsonify({"type": "about:blank", "title": title, "status": status, "detail": detail})
    resp.status_code = status
    resp.mimetype = "application/problem+json"
    return resp


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def http_error(e):
        resp = problem(e.code, e.name, e.description)
        if isinstance(e, MethodNotAllowed) and e.valid_methods:
            resp.headers["Allow"] = ", ".join(e.valid_methods)
        return resp

    @app.errorhandler(CatalogUnavailable)
    @app.errorhandler(ApiError)
    def upstream_error(e):
        return problem(503, "Service Unavailable", f"catalog-service: {e}")

    @app.errorhandler(Exception)
    def unexpected(e):
        app.logger.exception(e)
        return problem(500, "Internal Server Error", "unexpected error")
