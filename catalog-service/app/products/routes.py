"""Product routes: translate between HTTP and Python and choose the status
code; no storage or validation logic here (REST lecture, slides 17-18)."""

from flask import Blueprint, abort, current_app, jsonify, request, url_for

from ..http_helpers import int_arg, json_body
from .service import validate_product

bp = Blueprint("products", __name__)


def repo():
    return current_app.extensions["product_repo"]


def with_href(product):
    return {**product, "href": url_for("products.get_product", product_id=product["id"])}


def find_or_404(product_id):
    product = repo().get(product_id)
    if product is None:
        abort(404, description=f"product {product_id} not found")
    return product


@bp.get("/products")
def list_products():
    category = request.args.get("category")
    max_price = request.args.get("max_price", type=float)
    limit = int_arg("limit", default=100, low=1, high=100)
    items = [with_href(p) for p in repo().list(category, max_price, limit)]
    return jsonify({"items": items, "total": len(items)})


@bp.get("/products/<product_id>")
def get_product(product_id):
    return jsonify(with_href(find_or_404(product_id)))


@bp.post("/products")
def create_product():
    product = repo().add(validate_product(json_body()))
    location = url_for("products.get_product", product_id=product["id"])
    return jsonify(with_href(product)), 201, {"Location": location}


@bp.patch("/products/<product_id>")
def patch_product(product_id):
    current = find_or_404(product_id)
    changes = validate_product(json_body(), partial=True)
    merged = {k: v for k, v in {**current, **changes}.items() if k != "id"}
    return jsonify(with_href(repo().replace(product_id, merged)))


@bp.delete("/products/<product_id>")
def delete_product(product_id):
    find_or_404(product_id)
    repo().delete(product_id)
    return "", 204
