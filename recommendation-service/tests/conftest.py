"""Shared test helpers: a fake catalog (no network) and scripted fake models."""

import pytest

from app.catalog_client import CatalogUnavailable
from app.recommendations.model import ModelTurn, ToolCall

PRODUCTS = [
    {"id": "p001", "name": "Mug", "category": "kitchen", "price": 8.99, "popularity": 95},
    {"id": "p002", "name": "Bamboo Glass Jar", "category": "kitchen", "price": 5.49, "popularity": 60},
    {"id": "p004", "name": "Chef Knife", "category": "kitchen", "price": 34.0, "popularity": 72},
    {"id": "p006", "name": "Sunglasses", "category": "accessories", "price": 19.99, "popularity": 88},
    {"id": "p013", "name": "Running Shoes", "category": "footwear", "price": 119.0, "popularity": 91},
    {"id": "p021", "name": "Water Bottle", "category": "sports", "price": 15.0, "popularity": 83},
    {"id": "p023", "name": "Wireless Earbuds", "category": "electronics", "price": 69.0, "popularity": 96},
]


class FakeCatalog:
    def __init__(self, events=None, down=False):
        self.events = events or {}
        self.down = down

    def _check(self):
        if self.down:
            raise CatalogUnavailable("connection refused")

    def list_products(self, category=None, max_price=None, limit=100):
        self._check()
        items = [p for p in PRODUCTS if (not category or p["category"] == category)
                 and (max_price is None or p["price"] <= max_price)]
        return sorted(items, key=lambda p: -p["popularity"])[:limit]

    def get_product(self, product_id):
        self._check()
        return next((p for p in PRODUCTS if p["id"] == product_id), None)

    def list_events(self, user_id, limit=50):
        self._check()
        return self.events.get(user_id, [])[:limit]


class FakeModel:
    """Plays back a fixed list of turns; each turn is a list of (tool name, args)."""

    name = "fake"

    def __init__(self, turns, tokens=(100, 20)):
        self.turns, self.tokens, self.seen = list(turns), tokens, []

    def run_turn(self, history, system, tools):
        self.seen.append(history[-1])
        calls = self.turns.pop(0) if self.turns else []
        return ModelTurn(calls=[ToolCall(n, a) for n, a in calls], input_tokens=self.tokens[0],
                         output_tokens=self.tokens[1], text="" if calls else "I think...")


# u1 bought the Mug and viewed Sunglasses
EVENTS = {"u1": [
    {"productId": "p006", "type": "view"},
    {"productId": "p001", "type": "purchase"},
]}


@pytest.fixture
def catalog():
    return FakeCatalog(EVENTS)
