"""Language binding for catalog-service: the only class that knows its URLs,
status codes and JSON (REST lecture, slides 25-29).

- A Session reuses connections; only idempotent GETs are retried (slide 27).
- Every call has a timeout: requests has none by default (slide 25).
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ApiError(Exception):
    def __init__(self, status, detail):
        super().__init__(f"{status}: {detail}")
        self.status, self.detail = status, detail


class CatalogUnavailable(Exception):
    pass


class CatalogClient:
    def __init__(self, base_url, session=None, timeout=5):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        if session is None:
            retry = Retry(total=2, backoff_factor=0.2, status_forcelist=[502, 503, 504], allowed_methods=["GET"])
            session = requests.Session()
            session.mount("http://", HTTPAdapter(max_retries=retry))
            session.mount("https://", HTTPAdapter(max_retries=retry))
            session.headers.update({"Accept": "application/json"})
        self.session = session

    def _call(self, method, path, **kwargs):
        try:
            r = self.session.request(method, self.base + path, timeout=self.timeout, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise CatalogUnavailable(str(exc)) from exc
        if r.status_code >= 400:
            is_json = r.headers.get("Content-Type", "").endswith("json")
            body = r.json() if is_json else {}
            raise ApiError(r.status_code, body.get("detail", r.reason))
        return r.json() if r.content else None

    # one method per API operation
    def list_products(self, category=None, max_price=None, limit=100):
        params = {"category": category, "max_price": max_price, "limit": limit}
        params = {k: v for k, v in params.items() if v is not None}
        return self._call("GET", "/products", params=params)["items"]

    def get_product(self, product_id):
        try:
            return self._call("GET", f"/products/{product_id}")
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise

    def list_events(self, user_id, limit=50):
        return self._call("GET", f"/users/{user_id}/events", params={"limit": limit})["items"]
