"""claims.ask on the OpenAI branch: image blocks become data URLs, the schema reaches response_format,
and a refusal raises. No network: openai.OpenAI is replaced by a fake.

    .venv/bin/python tests/test_ask_openai.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_PROFILE"] = ""
os.environ["OPENAI_API_KEY"] = "test"
import claims  # noqa: E402

seen = {}


class FakeOpenAI:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self.parse))

    def parse(self, **kw):
        seen.update(kw)
        msg = SimpleNamespace(parsed=claims.TicketFields(plate="AB 12 345"), content=" hi ", refusal=kw.get("refuse"))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


claims.openai.OpenAI = FakeOpenAI
assert claims.is_live() and claims._openai() and claims._model() == "gpt-6.1-sol"

block = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}
out = claims.ask("sys", [block, {"type": "text", "text": "go"}], claims.TicketFields)
assert out.plate == "AB 12 345"
assert seen["response_format"] is claims.TicketFields and seen["model"] == "gpt-6.1-sol"
assert seen["messages"][0] == {"role": "system", "content": "sys"}
assert seen["messages"][1]["content"][0] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}
assert seen["messages"][1]["content"][1] == {"type": "text", "text": "go"}

seen.clear()
assert claims.ask("sys", "plain") == "hi" and "response_format" not in seen

# every schema must survive OpenAI's strict-mode conversion (done client-side by the SDK)
import evidence  # noqa: E402
from openai.lib._pydantic import to_strict_json_schema  # noqa: E402
for s in (claims.TicketFields, claims.Assessment, evidence.EvidenceCheck):
    to_strict_json_schema(s)
print("ok")

# ChatGPT-plan branch: Responses API, streamed, store=False, Responses-style content, account's model.
import chatgpt  # noqa: E402
import httpx2  # noqa: E402  (the HTTP client this openai version uses)

chatgpt._shared.update({"client_id": "c", "access_token": "AT", "refresh_token": "RT", "expires_at": 9e12, "models": ["gpt-test"]})
chatgpt._json = lambda *a, **k: {}  # atexit logout must not touch the network
seen.clear()


class FakeStream:
    def __init__(self, **kw):
        seen.update(kw)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def __iter__(self):
        if seen.get("instructions") == "sharing off":  # what ChatGPT really sent after ParkRefund's access was switched off
            raise claims.openai.APIError("The ChatGPT user has reached their Subscription Sharing usage limit.",
                                         httpx2.Request("POST", chatgpt.RESOURCE + "/responses"), body={})
        if seen.get("instructions") == "empty final":  # store=False: the text only arrives as deltas
            return iter([SimpleNamespace(type="response.output_text.delta", delta=d) for d in ('{"plate": ', '"D"}')])
        return iter([])

    def get_final_response(self):
        if seen.get("instructions") == "cut off":  # reasoning used the whole output budget
            return SimpleNamespace(status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                                   output_parsed=None, output_text="")
        if seen.get("instructions") == "empty final":  # what the plan endpoint really sent: completed, output []
            return SimpleNamespace(status="completed", output=[], output_parsed=None, output_text="")
        return SimpleNamespace(status="completed", output=["message"], output_parsed=claims.TicketFields(plate="X"), output_text=" t ")


class FakeChatGPTClient:
    def __init__(self, **kw):
        seen["client"] = kw
        self.responses = self

    def stream(self, **kw):
        return FakeStream(**kw)


claims.openai.OpenAI = FakeChatGPTClient
assert claims.is_live() and claims._model() == "gpt-test"
out = claims.ask("sys", [block, {"type": "text", "text": "go"}], claims.TicketFields)
assert out.plate == "X" and seen["text_format"] is claims.TicketFields and seen["store"] is False and seen["instructions"] == "sys"
assert seen["client"] == {"api_key": "AT", "base_url": chatgpt.RESOURCE, "max_retries": 0}
assert seen["input"] == [{"role": "user", "content": [{"type": "input_image", "image_url": "data:image/jpeg;base64,QUJD"},
                                                      {"type": "input_text", "text": "go"}]}]
assert claims.ask("sys", "plain") == "t"
assert seen["max_output_tokens"] >= 16000
try:
    claims.ask("cut off", "plain", claims.TicketFields)
    raise AssertionError("an incomplete response must raise")
except RuntimeError as e:
    assert "max_output_tokens" in str(e)
assert claims.ask("empty final", "plain", claims.TicketFields).plate == "D"
assert claims.ask("empty final", "plain") == '{"plate": "D"}'
try:
    claims.ask("sharing off", "plain", claims.TicketFields)
    raise AssertionError("a stream error must raise")
except RuntimeError as e:
    assert "plan sharing for ParkRefund is off" in str(e) and "chatgpt.com/settings/usage" in str(e)
chatgpt._shared.clear()
print("ok chatgpt branch")
