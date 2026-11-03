"""v2: the AI agent. The model DECIDES what to do: which tools to call, in which
order, and which products to return. Our code only runs the tools it asks for
and checks the final answer. This is what the project requires of v2: "use a
model to decide how to handle a request, for instance by selecting and calling
tools or backend services".

One request, step by step:
  1. We send the model the task plus the list of tools it may use.
  2. The model answers with tool calls, e.g. get_user_events(limit=20).
  3. Our code runs them against catalog-service and sends the results back.
  4. Repeat until the model calls submit_recommendations(items=[...]).
"""

import time
from dataclasses import dataclass, field

from .model import Tool

SYSTEM = """You recommend products for an online shop.
Use the tools to look at the user's recent activity and at the catalog, then decide.
Rules:
- Only recommend products returned by the tools, using their ids exactly.
- Never recommend a product the user already purchased.
- No duplicates. Return exactly LIMIT items, or all remaining products if fewer exist.
- Give each item one short reason a shopper would understand.
Finish by calling submit_recommendations exactly once."""

TOOLS = [
    Tool(
        "get_user_events",
        "The user's recent activity, newest first: product id, name, category, and type (view, cart, purchase).",
        {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}},
    ),
    Tool(
        "search_products",
        "Products in the catalog, most popular first. Both filters are optional.",
        {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Only this category"},
                "max_price": {"type": "number", "description": "Only products at or below this price"},
            },
        },
    ),
    Tool(
        "get_product",
        "One product by id, or an error if it does not exist.",
        {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]},
    ),
    Tool(
        "submit_recommendations",
        "Your final answer. Call once, with the products in order, best first.",
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"product_id": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["product_id", "reason"],
                    },
                }
            },
            "required": ["items"],
        },
    ),
]

FAULT_MODES = ("none", "invalid_ids", "slow", "error")


class AgentError(Exception):
    pass


@dataclass
class AgentOutcome:
    items: list  # [{"productId", "reason"}]
    tool_calls: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    turns: int = 0


def _short(product):
    return {k: product[k] for k in ("id", "name", "category", "price", "popularity") if k in product}


class AgentRecommender:
    name = "agent"

    def __init__(self, model, catalog, max_turns=6, fault_mode="none", slow_seconds=30.0):
        if fault_mode not in FAULT_MODES:
            raise ValueError(f"FAULT_MODE must be one of {FAULT_MODES}")
        self.model, self.catalog = model, catalog
        self.max_turns, self.fault_mode, self.slow_seconds = max_turns, fault_mode, slow_seconds

    # --- the tools: plain Python functions run by OUR code when the model asks ---
    def _run_tool(self, call, context):
        args = call.args
        if call.name == "get_user_events":
            limit = max(1, min(int(args.get("limit", 20)), 50))
            events = self.catalog.list_events(context.user_id, limit=limit)
            enriched = []
            for e in events:
                p = context.products.get(e["productId"], {})
                enriched.append(
                    {"productId": e["productId"], "name": p.get("name"), "category": p.get("category"), "type": e["type"]}
                )
            return {"events": enriched}
        if call.name == "search_products":
            found = self.catalog.list_products(category=args.get("category"), max_price=args.get("max_price"))
            return {"products": [_short(p) for p in found]}
        if call.name == "get_product":
            product = self.catalog.get_product(str(args.get("product_id", "")))
            return _short(product) if product else {"error": "product not found"}
        return {"error": f"unknown tool {call.name}"}

    def recommend(self, context, limit):
        if self.fault_mode == "error":
            raise AgentError("injected fault: error")
        if self.fault_mode == "slow":
            time.sleep(self.slow_seconds)

        history = [{"role": "user", "text": f"User: {context.user_id}\nLIMIT={limit} (number of products to recommend)"}]
        outcome = AgentOutcome(items=[])
        for _ in range(self.max_turns):
            turn = self.model.run_turn(history, SYSTEM.replace("LIMIT", str(limit)), TOOLS)
            outcome.turns += 1
            outcome.input_tokens += turn.input_tokens
            outcome.output_tokens += turn.output_tokens
            if not turn.calls:
                raise AgentError("model answered without calling submit_recommendations")
            history.append({"role": "model", "calls": turn.calls, "raw": turn.raw})

            results = []
            for call in turn.calls:
                outcome.tool_calls.append(call.name)
                if call.name == "submit_recommendations":
                    outcome.items = [
                        {"productId": str(i.get("product_id", "")), "reason": str(i.get("reason", ""))}
                        for i in call.args.get("items", [])
                    ]
                    if self.fault_mode == "invalid_ids" and outcome.items:
                        outcome.items[-1]["productId"] = "NOT_A_PRODUCT"
                    return outcome
                results.append((call.name, self._run_tool(call, context)))
            history.append({"role": "tool", "results": results})
        raise AgentError(f"no answer after {self.max_turns} model turns")
