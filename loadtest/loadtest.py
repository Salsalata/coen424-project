"""Load generator for the canary: the same load at every step.

Option A has no built-in load generator, so this is ours. It:
  1. creates N synthetic shoppers and records some events for each
     (views, cart adds, purchases) through the catalog API;
  2. sends GET .../recommendations for random shoppers for D seconds,
     from C threads in parallel;
  3. checks every answer from the OUTSIDE (black box): status 200, the
     contract's fields, no duplicate, nothing the shopper bought, `limit` items;
  4. prints errors, p50/p95/p99 latency and the correctness rate.

The client cannot see which version answered (that is the point of the
contract); per-version numbers come from the service logs (scripts/split_report.py).

Usage (python 3.10+, `pip install requests`):
  python loadtest/loadtest.py --catalog-url http://localhost:8080 --reco-url http://localhost:8080
  python loadtest/loadtest.py --catalog-url $CATALOG_URL --reco-url $RECO_URL --duration 300
"""

import argparse
import json
import random
import statistics
import threading
import time

import requests

TYPES = ["view", "view", "view", "cart", "purchase"]


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered) + 0.5) - 1))
    return ordered[index]


def seed_shoppers(catalog, n, events_each, rng, run_id):
    products = requests.get(f"{catalog}/api/v1/products", timeout=10).json()["items"]
    ids = [p["id"] for p in products]
    shoppers = {}
    for i in range(n):
        user = f"load-{run_id}-{i}"
        bought = set()
        for _ in range(events_each):
            pid, kind = rng.choice(ids), rng.choice(TYPES)
            r = requests.post(f"{catalog}/api/v1/users/{user}/events",
                              json={"productId": pid, "type": kind}, timeout=10)
            r.raise_for_status()
            if kind == "purchase":
                bought.add(pid)
        shoppers[user] = bought
    return shoppers, len(ids)


def check(body, user, bought, limit, catalog_size):
    """Correctness as a client can see it."""
    try:
        items = body["items"]
        ids = [i["productId"] for i in items]
        if body["userId"] != user or body["total"] != len(items):
            return False
        if any(not i.get("reason") for i in items):
            return False
        if len(set(ids)) != len(ids) or set(ids) & bought:
            return False
        return len(ids) == min(limit, catalog_size - len(bought))
    except (KeyError, TypeError):
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalog-url", required=True, help="base URL serving /api/v1/products and events")
    ap.add_argument("--reco-url", required=True, help="base URL serving /api/v1/users/{id}/recommendations")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--events", type=int, default=6, help="events recorded per shopper")
    ap.add_argument("--duration", type=int, default=60, help="seconds of load")
    ap.add_argument("--concurrency", type=int, default=4, help="parallel threads")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=15)
    ap.add_argument("--seed", type=int, default=424)
    ap.add_argument("--out", help="write the summary as JSON to this file")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    run_id = int(time.time())
    shoppers, catalog_size = seed_shoppers(args.catalog_url.rstrip("/"), args.users, args.events, rng, run_id)
    users = list(shoppers)
    print(f"Seeded {len(users)} shoppers; sending load for {args.duration}s with {args.concurrency} threads...")

    results, lock = [], threading.Lock()
    deadline = time.time() + args.duration

    def worker(seed):
        local = random.Random(seed)
        session = requests.Session()
        while time.time() < deadline:
            user = local.choice(users)
            url = f"{args.reco_url.rstrip('/')}/api/v1/users/{user}/recommendations"
            start = time.perf_counter()
            try:
                r = session.get(url, params={"limit": args.limit}, timeout=args.timeout)
                ms = (time.perf_counter() - start) * 1000
                ok = r.status_code == 200
                correct = ok and check(r.json(), user, shoppers[user], args.limit, catalog_size)
                outcome = (r.status_code, ms, correct)
            except requests.RequestException:
                outcome = ("timeout/network", (time.perf_counter() - start) * 1000, False)
            with lock:
                results.append(outcome)

    threads = [threading.Thread(target=worker, args=(args.seed + i,)) for i in range(args.concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total = len(results)
    errors = [r for r in results if r[0] != 200]
    server_errors = [r for r in errors if not (isinstance(r[0], int) and r[0] < 500)]
    latencies = [r[1] for r in results]
    summary = {
        "requests": total,
        "requests_per_second": round(total / args.duration, 2),
        "errors_total": len(errors),
        "error_rate_5xx_or_timeout_pct": round(100 * len(server_errors) / total, 2) if total else None,
        "correct_pct": round(100 * sum(1 for r in results if r[2]) / total, 2) if total else None,
        "latency_ms_p50": round(statistics.median(latencies), 1) if latencies else None,
        "latency_ms_p95": round(percentile(latencies, 95), 1) if latencies else None,
        "latency_ms_p99": round(percentile(latencies, 99), 1) if latencies else None,
    }
    print(json.dumps(summary, indent=2))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
