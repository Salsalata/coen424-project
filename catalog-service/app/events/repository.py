"""Event storage: add an event, list a user's recent events (newest first)."""

import itertools


class InMemoryEventRepository:
    def __init__(self):
        self._events, self._ids = {}, itertools.count(1)

    def add(self, user_id, data):
        event = {**data, "id": f"e{next(self._ids)}", "userId": user_id}
        self._events.setdefault(user_id, []).append(event)
        return event

    def list(self, user_id, limit=50):
        events = self._events.get(user_id, [])
        # Newest first; events in the same millisecond keep their arrival order
        ordered = sorted(enumerate(events), key=lambda pair: (pair[1]["timestamp"], pair[0]), reverse=True)
        return [event for _, event in ordered][:limit]


def make_event_repository(config):
    if config["STORAGE"] == "firestore":
        from .firestore_repository import FirestoreEventRepository

        return FirestoreEventRepository(config["GCP_PROJECT"])
    return InMemoryEventRepository()
