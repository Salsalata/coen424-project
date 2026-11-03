"""Products in Firestore: same interface as the in-memory repository, but the
data is shared by every worker and instance and survives restarts. This plays
the role Redis plays in the lecture (slide 21), using Google Cloud's managed
NoSQL document database instead.

Data model: collection "products", one document per product, document id = product id.
"""

from google.cloud import firestore

from .repository import filter_products


class FirestoreProductRepository:
    def __init__(self, project=None):
        self.db = firestore.Client(project=project)
        self.col = self.db.collection("products")

    def list(self, category=None, max_price=None, limit=None):
        query = self.col
        if category:
            # A single-field filter needs no composite index; price and sorting
            # are applied in Python (the catalog is small).
            query = query.where(filter=firestore.FieldFilter("category", "==", category.lower()))
        products = [{**doc.to_dict(), "id": doc.id} for doc in query.stream()]
        return filter_products(products, None, max_price, limit)

    def get(self, product_id):
        doc = self.col.document(product_id).get()
        return {**doc.to_dict(), "id": doc.id} if doc.exists else None

    def add(self, data, product_id=None):
        ref = self.col.document(product_id) if product_id else self.col.document()
        ref.set(data)
        return {**data, "id": ref.id}

    def replace(self, product_id, data):
        self.col.document(product_id).set(data)
        return {**data, "id": product_id}

    def delete(self, product_id):
        ref = self.col.document(product_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True
