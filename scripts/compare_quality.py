"""Quality comparison: the same shoppers, answered by v1 (rules) and v2 (AI agent).

The canary measures whether v2 is *correct* (valid ids, nothing already bought, ...).
This script looks at whether it is *better*: it creates shoppers with deliberately
different histories, asks both versions for recommendations, and writes a Markdown
report for PEOPLE to judge (relevance, complementarity, price fit, recency, reasons).

Each shopper gets fixed ids for one run (--run-id), so a run is repeatable; v2 uses
temperature 0, so the same history gives (nearly) the same answer.

Cloud (v2 can stay at 0% traffic: its tag URL still answers):
  python scripts/compare_quality.py \\
      --catalog-url https://catalog-service-...run.app \\
      --v1-url https://rules-v1---recommendation-service-...run.app \\
      --v2-url https://agent-v2---recommendation-service-...run.app
Local (docker compose; v2 is the scripted stand-in unless docker-compose.gemini.yml is used):
  python scripts/compare_quality.py --catalog-url http://localhost:8081 \\
      --v1-url http://localhost:8082 --v2-url http://localhost:8083
"""

import argparse
import datetime
import re
import sys
import time

import requests

# Each story: (key, what it tests, events OLDEST FIRST as (productId, type)).
# Product ids come from catalog-service/data/products.json (the seeded catalog).
SHOPPERS = [
    ("new-user", "no history at all: both should fall back to popular products", []),
    ("runner", "bought Running Shoes: complements across categories (socks, bottle, earbuds)?",
     [("p013", "view"), ("p013", "purchase")]),
    ("home-cook", "bought a Chef Knife, carted a Cutting Board: kitchen focus",
     [("p004", "view"), ("p004", "purchase"), ("p005", "cart")]),
    ("bargain-hunter", "carted only cheap items (under $16): price fit?",
     [("p002", "cart"), ("p014", "cart"), ("p021", "cart")]),
    ("luxury", "bought a $110 Watch, viewed a Denim Jacket and Loafers: premium items?",
     [("p010", "view"), ("p012", "view"), ("p007", "purchase")]),
    ("browser", "only views, in 3 different categories: how to weigh weak signals?",
     [("p006", "view"), ("p016", "view"), ("p019", "view")]),
    ("winter", "viewed a Wool Scarf, carted Wool Socks: a seasonal theme across categories?",
     [("p011", "view"), ("p014", "cart")]),
    ("tech", "bought Wireless Earbuds: the obvious complement is the Phone Charger",
     [("p023", "view"), ("p023", "purchase")]),
    ("fitness-done", "already bought Yoga Mat, Dumbbells and Water Bottle: sports almost exhausted",
     [("p020", "purchase"), ("p022", "purchase"), ("p021", "purchase")]),
    ("new-home", "carted a Throw Pillow and a Candle Holder, viewed a Wall Clock: home decor",
     [("p017", "view"), ("p016", "cart"), ("p015", "cart")]),
    ("changed-interest", "old kitchen purchases, but the NEWEST activity is electronics: recency?",
     [("p001", "purchase"), ("p003", "purchase"), ("p024", "view"), ("p023", "view")]),
    ("beauty", "viewed a Hairdryer twice, carted Face Cream: beauty focus",
     [("p018", "view"), ("p018", "view"), ("p019", "cart")]),
    ("traveller", "bought Sunglasses, viewed a Phone Charger and a Water Bottle: a travel bundle?",
     [("p024", "view"), ("p021", "view"), ("p006", "purchase")]),
    ("kitchen-complete", "bought ALL 5 kitchen products: rules still favour kitchen; what next?",
     [("p001", "purchase"), ("p002", "purchase"), ("p003", "purchase"), ("p004", "purchase"),
      ("p005", "purchase")]),
    ("gift-shopper", "carted a Wallet and a Watch, viewed a Scarf: accessories as gifts?",
     [("p011", "view"), ("p008", "cart"), ("p007", "cart")]),
]

# v1's fixed wording; if v2's reasons look like this, v2 probably fell back to the rules
V1_REASON = re.compile(r"^Popular (in |with all shoppers)")


def post_events(catalog, user, events):
    for pid, kind in events:
        r = requests.post(f"{catalog}/api/v1/users/{user}/events",
                          json={"productId": pid, "type": kind}, timeout=15)
        r.raise_for_status()
        time.sleep(0.05)  # distinct timestamps keep the order unambiguous


def recommend(base, user, limit):
    started = time.perf_counter()
    r = requests.get(f"{base}/api/v1/users/{user}/recommendations", params={"limit": limit}, timeout=30)
    secs = time.perf_counter() - started
    r.raise_for_status()
    return r.json()["items"], secs


def fmt_items(items, products):
    lines = []
    for i, item in enumerate(items, 1):
        p = products.get(item["productId"], {})
        lines.append(f"{i}. **{p.get('name', item['productId'])}** ({item['productId']}, "
                     f"{p.get('category', '?')}, ${p.get('price', '?')}): {item['reason']}")
    return "<br>".join(lines) or "(none)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog-url", required=True, help="catalog-service base URL (without /api/v1)")
    ap.add_argument("--v1-url", required=True, help="v1 base URL (cloud: the rules-v1 tag URL)")
    ap.add_argument("--v2-url", required=True, help="v2 base URL (cloud: the agent-v2 tag URL)")
    ap.add_argument("--limit", type=int, default=4)
    ap.add_argument("--run-id", default=datetime.datetime.now().strftime("%Y%m%d-%H%M"),
                    help="part of every shopper id; reuse it to re-ask the same shoppers without new events")
    ap.add_argument("--no-seed", action="store_true", help="do not record events (shoppers already exist)")
    ap.add_argument("--out", default="docs/quality-comparison.md")
    a = ap.parse_args()
    catalog, v1, v2 = (u.rstrip("/") for u in (a.catalog_url, a.v1_url, a.v2_url))

    products = {p["id"]: p for p in requests.get(f"{catalog}/api/v1/products", params={"limit": 100},
                                                 timeout=15).json()["items"]}
    rows, sections = [], []
    for key, story, events in SHOPPERS:
        user = f"qc-{a.run_id}-{key}"
        if not a.no_seed:
            post_events(catalog, user, events)
        try:
            v1_items, v1_secs = recommend(v1, user, a.limit)
            v2_items, v2_secs = recommend(v2, user, a.limit)
        except requests.RequestException as exc:
            print(f"{key}: FAILED: {exc}", file=sys.stderr)
            rows.append(f"| {key} | n/a | n/a | n/a | request failed | | |")
            continue
        v1_ids = [i["productId"] for i in v1_items]
        v2_ids = [i["productId"] for i in v2_items]
        overlap = len(set(v1_ids) & set(v2_ids))
        fallback = v2_items and all(V1_REASON.match(i["reason"]) for i in v2_items)
        flag = "probable fallback (v1 wording)" if fallback else ""
        history = ", ".join(f"{kind} {products.get(pid, {}).get('name', pid)}" for pid, kind in events) or "none"

        print(f"{key:18} overlap {overlap}/{a.limit}  v1 {v1_secs:4.1f}s  v2 {v2_secs:4.1f}s  {flag}")
        rows.append(f"| {key} | {overlap}/{a.limit} | {v1_secs:.1f} s | {v2_secs:.1f} s | {flag} | | |")
        sections.append(f"### {key}\n\n*Tests:* {story}  \n*History (oldest first):* {history}\n\n"
                        f"| v1 (rules) | v2 (AI agent) |\n| --- | --- |\n"
                        f"| {fmt_items(v1_items, products)} | {fmt_items(v2_items, products)} |\n")

    with open(a.out, "w") as f:
        f.write(f"""# Quality comparison: v1 (rules) vs v2 (AI agent)

Generated by `scripts/compare_quality.py` on {datetime.datetime.now():%Y-%m-%d %H:%M}
(run id `{a.run_id}`, {a.limit} recommendations per shopper, {len(SHOPPERS)} shoppers).
v1: `{v1}`
v2: `{v2}`

The canary checks that v2 is **correct**; this page is for judging whether it is **better**.
The verdicts are filled in by the team, not by a script or an AI.

**Criteria for the judges:** (1) relevance to the shopper's history; (2) complementarity
(goes *with* what they have, not just more of the same); (3) price fit; (4) recency
(newest activity weighs more); (5) reason quality (specific, true, useful to a shopper).

## Summary

| Shopper | Overlap v1/v2 | v1 time | v2 time | Note | Better (v1 / v2 / tie) | Why |
| --- | --- | --- | --- | --- | --- | --- |
""")
        f.write("\n".join(rows) + "\n\n## Per shopper\n\n" + "\n".join(sections))
    print(f"\nWrote {a.out}")


if __name__ == "__main__":
    main()
