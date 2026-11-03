"""Events in Firestore.

Data model: users/{userId}/events/{eventId}, a sub-collection per user. Reading
"this user's last 50 events, newest first" is then a single-field order_by on
timestamp, which Firestore indexes automatically (no composite index to create).
"""

from google.cloud import firestore


class FirestoreEventRepository:
    def __init__(self, project=None):
        self.db = firestore.Client(project=project)

    def _col(self, user_id):
        return self.db.collection("users").document(user_id).collection("events")

    def add(self, user_id, data):
        ref = self._col(user_id).document()
        record = {**data, "userId": user_id}
        ref.set(record)
        return {**record, "id": ref.id}

    def list(self, user_id, limit=50):
        query = self._col(user_id).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        return [{**doc.to_dict(), "id": doc.id} for doc in query.stream()]
