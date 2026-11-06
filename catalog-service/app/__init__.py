"""catalog-service: products and user events.

App factory, as in the REST lecture (slide 14): create_app() wires the layers
together; nothing runs at import time.
"""

from flask import Flask

from .config import Config
from .errors import register_error_handlers
from .events.repository import make_event_repository
from .events.routes import bp as events_bp
from .products.repository import make_product_repository
from .products.routes import bp as products_bp
from .seed import seed_products


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    products = make_product_repository(app.config)
    events = make_event_repository(app.config)
    if app.config["SEED"]:
        seed_products(products, app.config["SEED_FILE"])
    app.extensions["product_repo"] = products
    app.extensions["event_repo"] = events

    register_error_handlers(app)
    app.register_blueprint(products_bp, url_prefix="/api/v1")
    app.register_blueprint(events_bp, url_prefix="/api/v1")

    # Not /healthz: Cloud Run reserves URL paths ending in "z" for itself.
    @app.get("/health")  # for the platform, not for clients
    def health():
        return {"status": "ok"}

    return app
