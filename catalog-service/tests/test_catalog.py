"""Contract tests for catalog-service: status codes, headers, error format
(REST lecture, slide 22). Run with: pytest -q"""

import pytest

from app import create_app
from app.config import TestConfig

MUG = {"name": "Travel Mug", "category": "Kitchen", "price": 12.5}


@pytest.fixture
def client():
    return create_app(TestConfig).test_client()  # fresh app + fresh data per test


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_list_is_seeded_and_sorted_by_popularity(client):
    body = client.get("/api/v1/products").get_json()
    assert body["total"] == 24
    pops = [p["popularity"] for p in body["items"]]
    assert pops == sorted(pops, reverse=True)
    assert body["items"][0]["href"] == f"/api/v1/products/{body['items'][0]['id']}"


def test_filter_by_category_and_price(client):
    items = client.get("/api/v1/products?category=kitchen&max_price=10").get_json()["items"]
    assert {p["id"] for p in items} == {"p001", "p002"}


def test_bad_limit_is_400_problem(client):
    resp = client.get("/api/v1/products?limit=0")
    assert resp.status_code == 400
    assert resp.content_type == "application/problem+json"


def test_create_then_get(client):
    resp = client.post("/api/v1/products", json=MUG)
    assert resp.status_code == 201
    created = client.get(resp.headers["Location"]).get_json()
    assert created["name"] == "Travel Mug"
    assert created["category"] == "kitchen"  # normalized
    assert created["popularity"] == 0  # default


def test_invalid_product_is_422_problem(client):
    resp = client.post("/api/v1/products", json={"name": "X", "category": "kitchen", "price": -1})
    assert resp.status_code == 422
    assert resp.content_type == "application/problem+json"
    assert resp.get_json()["detail"] == "price must be >= 0"


def test_unknown_field_is_422(client):
    resp = client.post("/api/v1/products", json={**MUG, "colour": "red"})
    assert resp.status_code == 422


def test_non_json_body_is_415(client):
    resp = client.post("/api/v1/products", data="name=x", content_type="text/plain")
    assert resp.status_code == 415


def test_patch_changes_only_sent_fields(client):
    resp = client.patch("/api/v1/products/p001", json={"price": 7.5})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["price"] == 7.5 and body["name"] == "Mug"


def test_delete_twice(client):
    assert client.delete("/api/v1/products/p001").status_code == 204
    assert client.delete("/api/v1/products/p001").status_code == 404


def test_method_not_allowed_has_allow_header(client):
    resp = client.put("/api/v1/products")
    assert resp.status_code == 405
    assert "GET" in resp.headers["Allow"]


def test_events_round_trip_newest_first(client):
    for pid, kind in [("p001", "view"), ("p004", "purchase")]:
        resp = client.post("/api/v1/users/u1/events", json={"productId": pid, "type": kind})
        assert resp.status_code == 201
    items = client.get("/api/v1/users/u1/events").get_json()["items"]
    assert [e["productId"] for e in items] == ["p004", "p001"]
    assert items[0]["userId"] == "u1" and "timestamp" in items[0]


def test_event_for_unknown_product_is_422(client):
    resp = client.post("/api/v1/users/u1/events", json={"productId": "nope", "type": "view"})
    assert resp.status_code == 422


def test_event_bad_type_is_422(client):
    resp = client.post("/api/v1/users/u1/events", json={"productId": "p001", "type": "like"})
    assert resp.status_code == 422


def test_unknown_user_has_no_events(client):
    assert client.get("/api/v1/users/nobody/events").get_json() == {"items": [], "total": 0}
