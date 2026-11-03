"""The recommendation service layer: no Flask here (REST lecture, slide 16).

For every request:
  1. load the user's context (catalog + events) from catalog-service;
  2. ask the decision-maker: v1 rules, or v2 agent with a deadline;
  3. validate the answer (validator.py);
  4. v2 only: if the agent failed, was too slow, or answered wrongly, answer
     with v1's rules instead (fallback), so the client still gets a correct
     response. The fallback is logged as a FAILURE of v2 (valid=false), so the
     canary still sees the problem;
  5. write one JSON log line with everything the canary and the cost report need.
"""

import time
import uuid
from concurrent import futures

from ..catalog_client import ApiError, CatalogUnavailable
from ..jsonlog import get_logger
from .agent import AgentRecommender
from .context import load_context
from .model import GeminiModel, ScriptedModel
from .rules import RulesRecommender
from .validator import validate_items

logger = get_logger("recommendation-service")


class AgentUnavailable(Exception):
    """v2 failed and fallback is disabled: the client gets a 503."""


class RecommendationService:
    def __init__(self, version, catalog, rules, agent=None, timeout=8.0, fallback_enabled=True,
                 model_name="none", prices=(0.0, 0.0)):
        self.version, self.catalog, self.rules, self.agent = version, catalog, rules, agent
        self.timeout, self.fallback_enabled = timeout, fallback_enabled
        self.model_name, self.prices = model_name, prices
        self.pool = futures.ThreadPoolExecutor(max_workers=8)  # where agent calls run, so we can stop waiting

    def recommend(self, user_id, limit):
        started = time.perf_counter()
        record = {"event": "recommendation", "version": self.version, "request_id": uuid.uuid4().hex,
                  "user_id": user_id, "limit": limit}
        try:
            context = load_context(self.catalog, user_id)
        except (CatalogUnavailable, ApiError) as exc:
            self._log(record, started, status=503, source="none", valid=False, reason=f"catalog: {exc}")
            raise

        if self.version == "v1":
            items = self.rules.recommend(context, limit)
            check = validate_items(items, context, limit)
            self._log(record, started, status=200, source="rules", valid=check.valid,
                      reason="; ".join(check.problems) or None, item_ids=[i["productId"] for i in items])
            return self._response(user_id, items, context)

        items, reason, outcome = None, None, None
        pending = self.pool.submit(self.agent.recommend, context, limit)
        try:
            outcome = pending.result(timeout=self.timeout)
            check = validate_items(outcome.items, context, limit)
            if check.valid:
                items = outcome.items
            else:
                reason = "invalid answer: " + "; ".join(check.problems)
        except futures.TimeoutError:
            reason = f"agent timed out after {self.timeout}s"
        except Exception as exc:  # any agent failure ends in a fallback or a 503, never a crash
            reason = f"agent error: {exc}"

        if outcome is not None:
            cost = (outcome.input_tokens * self.prices[0] + outcome.output_tokens * self.prices[1]) / 1_000_000
            record.update(model=self.model_name, tool_calls=outcome.tool_calls, turns=outcome.turns,
                          input_tokens=outcome.input_tokens, output_tokens=outcome.output_tokens,
                          cost_usd=round(cost, 8))

        if items is not None:
            self._log(record, started, status=200, source="agent", valid=True,
                      item_ids=[i["productId"] for i in items])
            return self._response(user_id, items, context)

        if not self.fallback_enabled:
            self._log(record, started, status=503, source="none", valid=False, reason=reason)
            raise AgentUnavailable(reason)
        items = self.rules.recommend(context, limit)
        self._log(record, started, status=200, source="fallback", valid=False, reason=reason,
                  item_ids=[i["productId"] for i in items])
        return self._response(user_id, items, context)

    @staticmethod
    def _response(user_id, items, context):
        """Same JSON shape whoever answered (the OpenAPI RecommendationList)."""
        out = []
        for item in items:
            product = context.products[item["productId"]]
            out.append({"productId": product["id"], "name": product["name"],
                        "category": product["category"], "reason": item["reason"]})
        return {"userId": user_id, "items": out, "total": len(out)}

    @staticmethod
    def _log(record, started, **fields):
        record.update(fields)
        record["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        logger.info("recommendation", extra={"fields": record})


def build_recommendation_service(config, catalog, model=None):
    version = config["RECOMMENDER"]
    if version not in ("v1", "v2"):
        raise ValueError("RECOMMENDER must be v1 or v2")
    rules = RulesRecommender()
    if version == "v1":
        return RecommendationService("v1", catalog, rules)

    if model is None:
        if config["AGENT_MODEL"] == "scripted":
            model = ScriptedModel()
        else:
            model = GeminiModel(config["GEMINI_MODEL"], config["VERTEX_PROJECT"], config["VERTEX_LOCATION"],
                                labels={"service": "recommendation", "version": "v2"})
    model_name = config["GEMINI_MODEL"] if isinstance(model, GeminiModel) else getattr(model, "name", "custom")
    agent = AgentRecommender(model, catalog, max_turns=config["AGENT_MAX_TURNS"], fault_mode=config["FAULT_MODE"])
    return RecommendationService("v2", catalog, rules, agent, timeout=config["AGENT_TIMEOUT_SECONDS"],
                                 fallback_enabled=config["FALLBACK_ENABLED"], model_name=model_name,
                                 prices=(config["PRICE_INPUT_PER_M"], config["PRICE_OUTPUT_PER_M"]))
