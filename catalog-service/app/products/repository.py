"""Product storage. The five methods (list, get, add, replace, delete) are the
repository's interface: any storage that implements them can be plugged in
(REST lecture, slides 15 and 21)."""


def _sort_key(product):
    return (-product.get("popularity", 0), product["id"])  # most popular first


def filter_products(products, category=None, max_price=None, limit=None):
    if category:
        products = [p for p in products if p["category"] == category.lower()]
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]
    products = sorted(products, key=_sort_key)
    return products[:limit] if limit else products


class InMemoryProductRepository:
    """A dict in the process: fine for tests and local runs. Data is lost on
    restart and NOT shared between workers or instances (lecture slide 20)."""

    def __init__(self):
        self._products, self._next_id = {}, 1

    def list(self, category=None, max_price=None, limit=None):
        return filter_products(list(self._products.values()), category, max_price, limit)

    def get(self, product_id):
        return self._products.get(product_id)

    def add(self, data, product_id=None):
        if product_id is None:
            while f"p{self._next_id:03d}" in self._products:
                self._next_id += 1
            product_id = f"p{self._next_id:03d}"
        return self.replace(product_id, data)

    def replace(self, product_id, data):
        self._products[product_id] = {**data, "id": product_id}
        return self._products[product_id]

    def delete(self, product_id):
        return self._products.pop(product_id, None) is not None


def make_product_repository(config):
    if config["STORAGE"] == "firestore":
        from .firestore_repository import FirestoreProductRepository

        return FirestoreProductRepository(config["GCP_PROJECT"])
    return InMemoryProductRepository()
