"""The HTTP contract of recommendation-service, for v1 and v2, and the
canary-relevant behaviour of v2: fallback, deadline, logging of tokens."""

import json

import pytest

from app import create_app
from app.config import Config
from tests.conftest import EVENTS, FakeCatalog, FakeModel

SUBMIT_GOOD = [("submit_recommendations", {"items": [
    {"product_id": "p004", "reason": "Goes with your kitchen"},
    {"product_id": "p002", "reason": "Kitchen storage"}]})]


def make(version="v2", model=None, catalog=None, **overrides):
    config = type("C", (Config,), {"RECOMMENDER": version, "AGENT_TIMEOUT_SECONDS": 2,
                                   "PRICE_INPUT_PER_M": 1.0, "PRICE_OUTPUT_PER_M": 4.0, **overrides})
    return create_app(config, catalog=catalog or FakeCatalog(EVENTS), model=model).test_client()


def last_log(capsys):
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    return [l for l in lines if l.get("event") == "recommendation"][-1]


def test_v1_answers_with_contract_shape(capsys):
    body = make("v1").get("/api/v1/users/u1/recommendations?limit=3").get_json()
    assert body["userId"] == "u1" and body["total"] == 3
    assert set(body["items"][0]) == {"productId", "name", "category", "reason"}
    log = last_log(capsys)
    assert log["version"] == "v1" and log["source"] == "rules" and log["valid"] is True


def test_v2_agent_uses_tools_then_submits(capsys):
    model = FakeModel([[("get_user_events", {"limit": 10})], [("search_products", {"category": "kitchen"})],
                       SUBMIT_GOOD])
    body = make(model=model).get("/api/v1/users/u1/recommendations?limit=2").get_json()
    assert [i["productId"] for i in body["items"]] == ["p004", "p002"]
    assert body["items"][0]["name"] == "Chef Knife"  # filled in from the catalog, same shape as v1
    # the model saw the real tool results
    assert model.seen[1]["results"][0][1]["events"][1]["name"] == "Mug"
    log = last_log(capsys)
    assert log["source"] == "agent" and log["valid"] is True
    assert log["tool_calls"] == ["get_user_events", "search_products", "submit_recommendations"]
    assert log["input_tokens"] == 300 and log["output_tokens"] == 60
    assert log["cost_usd"] == pytest.approx((300 * 1.0 + 60 * 4.0) / 1e6)


def test_v1_and_v2_responses_have_identical_keys():
    v1 = make("v1").get("/api/v1/users/u1/recommendations?limit=2").get_json()
    v2 = make(model=FakeModel([SUBMIT_GOOD])).get("/api/v1/users/u1/recommendations?limit=2").get_json()
    assert set(v1) == set(v2)
    assert [set(i) for i in v1["items"]] == [set(i) for i in v2["items"]]


def test_invalid_agent_answer_falls_back_and_counts_as_failure(capsys):
    bad = [("submit_recommendations", {"items": [{"product_id": "p001", "reason": "you bought it"},
                                                 {"product_id": "p002", "reason": "ok"}]})]
    resp = make(model=FakeModel([bad])).get("/api/v1/users/u1/recommendations?limit=2")
    assert resp.status_code == 200
    assert "p001" not in [i["productId"] for i in resp.get_json()["items"]]
    log = last_log(capsys)
    assert log["source"] == "fallback" and log["valid"] is False
    assert "already purchased" in log["reason"]


def test_fault_mode_invalid_ids_is_caught(capsys):
    client = make(model=FakeModel([SUBMIT_GOOD]), FAULT_MODE="invalid_ids")
    assert client.get("/api/v1/users/u1/recommendations?limit=2").status_code == 200
    assert "unknown product ids" in last_log(capsys)["reason"]


def test_model_that_never_submits_falls_back(capsys):
    make(model=FakeModel([[]])).get("/api/v1/users/u1/recommendations")
    assert "without calling submit" in last_log(capsys)["reason"]


def test_slow_agent_hits_the_deadline(capsys):
    client = make(model=FakeModel([SUBMIT_GOOD]), FAULT_MODE="slow", AGENT_TIMEOUT_SECONDS=0.3)
    client.application.extensions["recommendations"].agent.slow_seconds = 1
    assert client.get("/api/v1/users/u1/recommendations?limit=2").status_code == 200
    log = last_log(capsys)
    assert log["source"] == "fallback" and "timed out" in log["reason"]
    assert log["latency_ms"] < 1000


def test_error_without_fallback_is_503_problem():
    client = make(model=FakeModel([SUBMIT_GOOD]), FAULT_MODE="error", FALLBACK_ENABLED=False)
    resp = client.get("/api/v1/users/u1/recommendations")
    assert resp.status_code == 503
    assert resp.content_type == "application/problem+json"


def test_catalog_down_is_503_problem():
    resp = make("v1", catalog=FakeCatalog(down=True)).get("/api/v1/users/u1/recommendations")
    assert resp.status_code == 503 and resp.get_json()["title"] == "Service Unavailable"


@pytest.mark.parametrize("limit", ["0", "11", "abc"])
def test_bad_limit_is_400(limit):
    resp = make("v1").get(f"/api/v1/users/u1/recommendations?limit={limit}")
    assert resp.status_code == 400 and resp.content_type == "application/problem+json"


def test_scripted_model_runs_whole_v2_pipeline_offline(capsys):
    body = make(AGENT_MODEL="scripted").get("/api/v1/users/u1/recommendations?limit=3").get_json()
    assert body["total"] == 3
    log = last_log(capsys)
    assert log["source"] == "agent" and log["model"] == "scripted"
    assert log["tool_calls"] == ["get_user_events", "search_products", "submit_recommendations"]


def test_health_reports_version():
    assert make("v1").get("/health").get_json() == {"status": "ok", "recommender": "v1"}
