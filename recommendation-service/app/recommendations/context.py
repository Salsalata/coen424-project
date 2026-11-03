"""What we know about one request: the catalog and the user's recent events.
Fetched once per request; used by v1's rules and by the validator."""

from dataclasses import dataclass, field

EVENT_WEIGHT = {"purchase": 3, "cart": 2, "view": 1}


@dataclass
class UserContext:
    user_id: str
    products: dict  # product id -> product
    events: list  # newest first
    purchased: set = field(default_factory=set)
    category_scores: dict = field(default_factory=dict)

    @property
    def available(self):
        """Products we are allowed to recommend: everything not yet bought."""
        return [p for pid, p in self.products.items() if pid not in self.purchased]


def load_context(catalog, user_id):
    products = {p["id"]: p for p in catalog.list_products(limit=100)}
    events = catalog.list_events(user_id, limit=50)
    purchased = {e["productId"] for e in events if e["type"] == "purchase"}
    scores = {}
    for e in events:
        product = products.get(e["productId"])
        if product:
            scores[product["category"]] = scores.get(product["category"], 0) + EVENT_WEIGHT.get(e["type"], 0)
    return UserContext(user_id, products, events, purchased, scores)
