"""GeminiModel without the network: we hand it a response object built with the
SDK's own types, exactly as Vertex AI would return it, and check that tool calls
and token counts are read correctly and that the conversation is sent back in
the right format."""

from google.genai import types

from app.recommendations.agent import TOOLS
from app.recommendations.model import GeminiModel


class FakeModels:
    def __init__(self, response):
        self.response, self.calls = response, []

    def generate_content(self, model, contents, config):
        self.calls.append((model, contents, config))
        return self.response


def make_model(response):
    gm = GeminiModel.__new__(GeminiModel)  # skip __init__: no credentials, no network
    gm.model, gm.labels = "gemini-test", {"version": "v2"}
    gm.client = type("C", (), {"models": FakeModels(response)})()
    return gm


def response_with_call():
    content = types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(name="get_user_events", args={"limit": 20}))])
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=content)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=410, candidates_token_count=12, thoughts_token_count=30))


def test_reads_tool_calls_and_tokens():
    gm = make_model(response_with_call())
    turn = gm.run_turn([{"role": "user", "text": "LIMIT=5"}], "system text", TOOLS)
    assert [(c.name, c.args) for c in turn.calls] == [("get_user_events", {"limit": 20})]
    assert turn.input_tokens == 410
    assert turn.output_tokens == 42  # answer + thinking tokens
    assert turn.raw.role == "model"


def test_sends_tools_labels_and_history_back():
    response = response_with_call()
    gm = make_model(response)
    history = [
        {"role": "user", "text": "LIMIT=5"},
        {"role": "model", "calls": [], "raw": response.candidates[0].content},
        {"role": "tool", "results": [("get_user_events", {"events": []})]},
    ]
    gm.run_turn(history, "system text", TOOLS)
    model, contents, config = gm.client.models.calls[0]
    assert model == "gemini-test"
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[2].parts[0].function_response.name == "get_user_events"
    names = [f.name for f in config.tools[0].function_declarations]
    assert names == ["get_user_events", "search_products", "get_product", "submit_recommendations"]
    assert config.automatic_function_calling.disable is True
    assert config.labels == {"version": "v2"}
    assert config.temperature == 0
