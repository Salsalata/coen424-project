"""The model behind v2, hidden behind one small interface so the agent does not
care which model runs:

    run_turn(history, system, tools) -> ModelTurn

- GeminiModel: Gemini on Vertex AI, through the google-genai SDK. The model
  version is a parameter (lecture "Inference as a Utility", slide 7), pinned by
  GEMINI_MODEL. Authentication uses the Cloud Run service account: no API key.
- ScriptedModel: an offline stand-in for local runs without a cloud account.
  It follows a fixed script; it is NOT AI and never counts as v2's model.

History entries (our own neutral format):
    {"role": "user", "text": "..."}                       the request
    {"role": "model", "calls": [ToolCall], "raw": ...}    what the model asked for
    {"role": "tool", "results": [(name, dict)]}           what our code answered
"""

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str = None  # Gemini 3.x requires each tool result to carry its call's id


@dataclass
class ModelTurn:
    calls: list = field(default_factory=list)  # ToolCall
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    raw: object = None  # the model's own message, sent back unchanged next turn


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON schema of the arguments


class ModelTimeout(Exception):
    """One model call was too slow or failed transiently (timeout, 500/503/504,
    lost connection). Safe to retry: nothing was decided yet in this turn."""


RETRYABLE_STATUS = (500, 503, 504)


class GeminiModel:
    def __init__(self, model, project, location, labels=None, thinking_level=None, call_timeout_seconds=None):
        from google import genai  # imported here so v1 and tests never need it
        from google.genai import types

        self.model = model
        self.labels = labels or {}
        # LOW thinking = fewer (billed) thinking tokens and faster turns; None = the model's default
        self.thinking_level = thinking_level
        # Limit for ONE Gemini call (SDK unit: ms). The SDK also sends it to Google as
        # X-Server-Timeout, so a call that would take longer ends with 504 DEADLINE_EXCEEDED.
        # A normal call takes about 1 s; measured in the cloud canary, a few hang for 8-9 s.
        # A short limit cuts those off early, leaving time to retry within the request deadline.
        http_options = types.HttpOptions(timeout=int(call_timeout_seconds * 1000)) if call_timeout_seconds else None
        self.client = genai.Client(vertexai=True, project=project, location=location, http_options=http_options)

    def _generate(self, **kwargs):
        """generate_content, with slow/transient failures turned into ModelTimeout."""
        import httpx
        from google.genai import errors

        try:
            return self.client.models.generate_content(**kwargs)
        except errors.APIError as exc:
            if exc.code in RETRYABLE_STATUS:
                raise ModelTimeout(f"{exc.code} {exc.status or ''}".strip()) from exc
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ModelTimeout(f"{type(exc).__name__}") from exc

    def run_turn(self, history, system, tools):
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level) if self.thinking_level else None,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name, description=t.description, parameters_json_schema=t.parameters
                        )
                        for t in tools
                    ]
                )
            ],
            # We run the tool loop ourselves, so we can count tokens and log every call
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            # Vertex AI billing labels: lets the cost report separate v2's model spend
            labels=self.labels,
        )
        response = self._generate(
            model=self.model, contents=[self._content(h, types) for h in history], config=config
        )
        usage = response.usage_metadata
        calls = [ToolCall(fc.name, dict(fc.args or {}), fc.id) for fc in (response.function_calls or [])]
        text = ""
        if not calls and response.candidates and response.candidates[0].content:
            text = "".join(p.text or "" for p in response.candidates[0].content.parts or [])
        return ModelTurn(
            calls=calls,
            text=text,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            # thinking tokens are billed as output tokens
            output_tokens=((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0,
            raw=response.candidates[0].content if response.candidates else None,
        )

    @staticmethod
    def _content(entry, types):
        if entry["role"] == "user":
            return types.Content(role="user", parts=[types.Part.from_text(text=entry["text"])])
        if entry["role"] == "model":
            return entry["raw"]  # unchanged, so Gemini keeps its own context (thought signatures)
        ids = entry.get("ids") or [None] * len(entry["results"])
        return types.Content(  # tool results go back with role "user", as the SDK itself does
            role="user",
            parts=[
                types.Part(function_response=types.FunctionResponse(id=i, name=n, response=r))
                for (n, r), i in zip(entry["results"], ids)
            ],
        )


class ScriptedModel:
    """Offline stand-in: look at events, search the favourite category, submit.
    Lets the whole v2 pipeline (tool loop, validator, logs) run with no cloud."""

    name = "scripted"

    def run_turn(self, history, system, tools):
        results = [(n, r) for h in history if h["role"] == "tool" for n, r in h["results"]]
        limit = int(history[0]["text"].split("LIMIT=")[1].split()[0])

        # Step 1: look at the user's activity
        events_result = [r for n, r in results if n == "get_user_events"]
        if not events_result:
            return ModelTurn(calls=[ToolCall("get_user_events", {"limit": 20})])
        events = events_result[0]["events"]

        # Step 2: get every product (one search with no filter)
        searches = [r for n, r in results if n == "search_products"]
        if not searches:
            return ModelTurn(calls=[ToolCall("search_products", {})])

        # Step 3: favourite category first, then the rest by popularity; skip what was bought
        bought = {e["productId"] for e in events if e["type"] == "purchase"}
        favourite = events[0]["category"] if events else None
        products = [p for p in searches[0]["products"] if p["id"] not in bought]
        products.sort(key=lambda p: (p["category"] != favourite, -p["popularity"], p["id"]))
        items = [
            {"product_id": p["id"], "reason": f"Picked for your interest in {p['category']}"}
            for p in products[:limit]
        ]
        return ModelTurn(calls=[ToolCall("submit_recommendations", {"items": items})])
