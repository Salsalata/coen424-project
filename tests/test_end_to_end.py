"""End to end over real HTTP: catalog-service and recommendation-service (v1,
then v2) run as real servers on random ports; recommendation-service reaches
the catalog through its HTTP client binding. Every response is checked
against openapi.yaml, so the code cannot drift from the contract.

Run from the repository root:  python -m pytest -q tests
"""

import importlib
import sys
import threading
from pathlib import Path

import pytest
import requests
import yaml
from jsonschema import Draft4Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load((ROOT / "openapi.yaml").read_text())
REGISTRY = Registry().with_resource("urn:spec", Resource.from_contents(SPEC, default_specification=DRAFT4))


def load_app_module(service_dir):
    """Both services have a package named `app`; load each one cleanly."""
    for name in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[name]
    sys.path.insert(0, str(ROOT / service_dir))
    try:
        return importlib.import_module("app")
    finally:
        sys.path.pop(0)


def serve(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def check_schema(body, schema_name):
    schema = {"$ref": f"urn:spec#/components/schemas/{schema_name}"}
    Draft4Validator(schema, registry=REGISTRY).validate(body)


@pytest.fixture(scope="module")
def catalog_url():
    catalog_app = load_app_module("catalog-service")
    from app.config import TestConfig  # noqa: E402  (the catalog's config)

    server, url = serve(catalog_app.create_app(TestConfig))
    yield url
    server.shutdown()


def reco_server(catalog_url, version):
    reco_app = load_app_module("recommendation-service")
    from app.config import Config  # noqa: E402  (the recommendation config)

    config = type("C", (Config,), {"RECOMMENDER": version, "CATALOG_URL": catalog_url + "/api/v1",
                                   "AGENT_MODEL": "scripted"})
    return serve(reco_app.create_app(config))


def test_catalog_responses_match_contract(catalog_url):
    products = requests.get(f"{catalog_url}/api/v1/products", timeout=5).json()
    check_schema(products, "ProductList")
    event = requests.post(f"{catalog_url}/api/v1/users/e2e/events",
                          json={"productId": "p001", "type": "purchase"}, timeout=5)
    assert event.status_code == 201
    check_schema(event.json(), "Event")
    problem = requests.get(f"{catalog_url}/api/v1/products/nope", timeout=5)
    assert problem.status_code == 404
    check_schema(problem.json(), "Problem")


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_recommendations_match_contract_for_both_versions(catalog_url, version):
    requests.post(f"{catalog_url}/api/v1/users/shopper/events",
                  json={"productId": "p004", "type": "purchase"}, timeout=5)
    server, url = reco_server(catalog_url, version)
    try:
        resp = requests.get(f"{url}/api/v1/users/shopper/recommendations?limit=5", timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        check_schema(body, "RecommendationList")
        ids = [i["productId"] for i in body["items"]]
        assert len(ids) == 5 and "p004" not in ids and len(set(ids)) == 5
        bad = requests.get(f"{url}/api/v1/users/shopper/recommendations?limit=99", timeout=5)
        assert bad.status_code == 400
        check_schema(bad.json(), "Problem")
    finally:
        server.shutdown()
