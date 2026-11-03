"""Local strangler facade, for rehearsing the canary on a laptop.

This is the lecture's Router class (Monolithic vs Microservices, slides 8-9)
with a percentage dial instead of an on/off switch:

    recommendations  ->  v2 with probability V2_PERCENT, otherwise v1
    everything else  ->  catalog-service

In the cloud this file is NOT used: Cloud Run's traffic split between the v1
and v2 revisions does the same job.
"""

import os
import random
import re

import requests
from flask import Flask, Response, request

RECO_PATH = re.compile(r"^/api/v1/users/[^/]+/recommendations$")
HOP_BY_HOP = {"connection", "content-length", "transfer-encoding", "content-encoding", "keep-alive"}


def choose_backend(path, v2_percent, urls, rnd=random.random):
    """Pure function: which upstream serves this path? (easy to test)"""
    if RECO_PATH.match(path):
        return urls["v2"] if rnd() * 100 < v2_percent else urls["v1"]
    return urls["catalog"]


def create_app():
    app = Flask(__name__)
    urls = {
        "catalog": os.getenv("CATALOG_UPSTREAM", "http://catalog:8080"),
        "v1": os.getenv("V1_UPSTREAM", "http://reco-v1:8080"),
        "v2": os.getenv("V2_UPSTREAM", "http://reco-v2:8080"),
    }
    v2_percent = float(os.getenv("V2_PERCENT", "0"))
    session = requests.Session()

    @app.get("/facade/healthz")
    def health():
        return {"status": "ok", "v2_percent": v2_percent}

    @app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
    @app.route("/<path:path>", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
    def forward(path):
        upstream = choose_backend("/" + path, v2_percent, urls)
        resp = session.request(
            request.method, upstream + "/" + path, params=request.args, data=request.get_data(),
            headers={k: v for k, v in request.headers if k.lower() != "host"}, timeout=30,
        )
        headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP]
        return Response(resp.content, resp.status_code, headers)

    return app
