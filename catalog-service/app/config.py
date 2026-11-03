"""Settings come from environment variables, so the same image runs locally
and on Cloud Run (REST lecture, slides 13-14 and 31)."""

import os
from pathlib import Path


def _flag(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


class Config:
    # "memory" (local, tests) or "firestore" (cloud)
    STORAGE = os.getenv("STORAGE", "memory")
    # Load data/products.json at startup (memory storage only; Firestore is seeded once by a script)
    SEED = _flag("SEED", True)
    SEED_FILE = os.getenv("SEED_FILE", str(Path(__file__).resolve().parent.parent / "data" / "products.json"))
    # Firestore project; empty = the project the service runs in
    GCP_PROJECT = os.getenv("GCP_PROJECT") or None


class TestConfig(Config):
    STORAGE = "memory"
    SEED = True
