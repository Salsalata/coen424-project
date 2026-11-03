"""One error format for the whole API: Problem Details, RFC 9457
(REST lecture, slides 8 and 19)."""

from flask import jsonify
from werkzeug.exceptions import HTTPException, MethodNotAllowed

from .validation import ValidationError


def problem(status, title, detail):
    resp = jsonify({"type": "about:blank", "title": title, "status": status, "detail": detail})
    resp.status_code = status
    resp.mimetype = "application/problem+json"
    return resp


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def http_error(e):  # 400, 404, 405, 415
        resp = problem(e.code, e.name, e.description)
        if isinstance(e, MethodNotAllowed) and e.valid_methods:
            resp.headers["Allow"] = ", ".join(e.valid_methods)
        return resp

    @app.errorhandler(ValidationError)
    def validation_error(e):
        return problem(422, "Validation failed", str(e))

    @app.errorhandler(Exception)  # last resort: stack trace stays in the server log
    def unexpected(e):
        app.logger.exception(e)
        return problem(500, "Internal Server Error", "unexpected error")
