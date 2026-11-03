from app import choose_backend

URLS = {"catalog": "C", "v1": "V1", "v2": "V2"}


def test_non_recommendation_paths_go_to_catalog():
    assert choose_backend("/api/v1/products", 100, URLS) == "C"
    assert choose_backend("/api/v1/users/u1/events", 100, URLS) == "C"


def test_split_follows_the_percentage():
    picks = [choose_backend("/api/v1/users/u1/recommendations", 10, URLS, rnd=lambda i=i: i / 1000)
             for i in range(1000)]
    assert picks.count("V2") == 100 and picks.count("V1") == 900


def test_zero_percent_is_a_full_rollback():
    assert all(choose_backend("/api/v1/users/u/recommendations", 0, URLS) == "V1" for _ in range(200))
