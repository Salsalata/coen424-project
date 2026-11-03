"""Load sample products from data/products.json at startup (memory storage)."""

import json

from .products.service import validate_product


def load_seed_file(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["products"]


def seed_products(repo, path):
    for item in load_seed_file(path):
        product_id = item.pop("id")
        repo.add(validate_product(item), product_id=product_id)
