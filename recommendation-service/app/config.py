"""Settings from environment variables (REST lecture, slide 14). The v1 and
v2 revisions run the same image with different values."""

import os


def _flag(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


class Config:
    # Which decision-maker answers: "v1" (rules) or "v2" (AI agent)
    RECOMMENDER = os.getenv("RECOMMENDER", "v1")
    # Base URL of catalog-service, including /api/v1
    CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8081/api/v1")
    CATALOG_TIMEOUT = float(os.getenv("CATALOG_TIMEOUT", "5"))

    # v2 only
    AGENT_MODEL = os.getenv("AGENT_MODEL", "gemini")  # "gemini" or "scripted" (offline stand-in, not AI)
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # pinned model version
    VERTEX_PROJECT = os.getenv("VERTEX_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
    AGENT_TIMEOUT_SECONDS = float(os.getenv("AGENT_TIMEOUT_SECONDS", "8"))
    AGENT_MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "6"))
    FALLBACK_ENABLED = _flag("FALLBACK_ENABLED", True)
    FAULT_MODE = os.getenv("FAULT_MODE", "none")  # none | invalid_ids | slow | error

    # Model prices in USD per 1 million tokens, copied from the Vertex AI pricing
    # page for GEMINI_MODEL. Used only to compute cost_usd in the logs.
    PRICE_INPUT_PER_M = float(os.getenv("PRICE_INPUT_PER_M", "0"))
    PRICE_OUTPUT_PER_M = float(os.getenv("PRICE_OUTPUT_PER_M", "0"))
