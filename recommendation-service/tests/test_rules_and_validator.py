from app.recommendations.context import load_context
from app.recommendations.rules import RulesRecommender
from app.recommendations.validator import validate_items


def test_new_user_gets_most_popular(catalog):
    items = RulesRecommender().recommend(load_context(catalog, "new"), 3)
    assert [i["productId"] for i in items] == ["p023", "p001", "p013"]
    assert items[0]["reason"] == "Popular with all shoppers"


def test_interest_ranks_categories_and_bought_items_are_excluded(catalog):
    ctx = load_context(catalog, "u1")
    ids = [i["productId"] for i in RulesRecommender().recommend(ctx, 4)]
    # kitchen (purchase = 3 points) beats accessories (view = 1); the Mug was bought
    assert ids == ["p004", "p002", "p006", "p023"]
    assert "p001" not in ids


def test_rules_are_deterministic(catalog):
    ctx = load_context(catalog, "u1")
    assert RulesRecommender().recommend(ctx, 5) == RulesRecommender().recommend(ctx, 5)


def test_rules_answer_passes_validator(catalog):
    ctx = load_context(catalog, "u1")
    assert validate_items(RulesRecommender().recommend(ctx, 5), ctx, 5).valid


def _items(*ids):
    return [{"productId": i, "reason": "because"} for i in ids]


def test_validator_catches_each_rule(catalog):
    ctx = load_context(catalog, "u1")
    assert not validate_items(_items("p002", "NOPE"), ctx, 2).valid  # unknown
    assert not validate_items(_items("p002", "p001"), ctx, 2).valid  # already bought
    assert not validate_items(_items("p002", "p002"), ctx, 2).valid  # duplicate
    assert not validate_items(_items("p002"), ctx, 2).valid  # too few
    assert not validate_items([{"productId": "p002", "reason": " "}], ctx, 1).valid  # no reason
    assert validate_items(_items("p002", "p004"), ctx, 2).valid


def test_validator_allows_fewer_when_catalog_runs_out(catalog):
    ctx = load_context(catalog, "u1")
    remaining = [p["id"] for p in ctx.available]
    assert len(remaining) == 6
    assert validate_items(_items(*remaining), ctx, 10).valid
