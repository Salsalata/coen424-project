"""recommendation-service: GET /api/v1/users/{userId}/recommendations.

The SAME code runs as v1 or v2; the environment variable RECOMMENDER picks
which decision-maker is used. On Cloud Run, v1 and v2 are two revisions of one
service, and Cloud Run's traffic split is the strangler facade.
"""

from flask import Flask

from .catalog_client import CatalogClient
from .config import Config
from .errors import register_error_handlers
from .recommendations.routes import bp as recommendations_bp
from .recommendations.service import build_recommendation_service


def create_app(config=Config, catalog=None, model=None):
    app = Flask(__name__)
    app.config.from_object(config)

    catalog = catalog or CatalogClient(app.config["CATALOG_URL"], timeout=app.config["CATALOG_TIMEOUT"])
    app.extensions["recommendations"] = build_recommendation_service(app.config, catalog, model)

    register_error_handlers(app)
    app.register_blueprint(recommendations_bp, url_prefix="/api/v1")

    # CORS: lets browser pages on other sites (SwaggerHub's "Try it out") call
    # this public API. Flask answers the browser's OPTIONS pre-check itself;
    # this hook adds the headers that say which origins, methods and headers
    # are allowed. No cookies or credentials are involved.
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Expose-Headers"] = "Location"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "recommender": app.config["RECOMMENDER"]}

    return app
