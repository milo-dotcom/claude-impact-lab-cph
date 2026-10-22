"""Nobody else can spend the operator's credentials: off 127.0.0.1 the .env key is ignored unless sharing
is opted in, opted-in sharing is capped per hour, a visitor's own ChatGPT sign-in is never capped,
api.py refuses --chatgpt on the network, and app.py tells the operator why. No network.

    .venv/bin/python tests/test_server_credentials.py
"""
import os
import subprocess
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for k in ("ANTHROPIC_PROFILE", "OPENAI_API_KEY", "PARKREFUND_SHARE_SERVER_KEY", "PARKREFUND_SHARED_CALLS_PER_HOUR"):
    os.environ[k] = ""
os.environ["ANTHROPIC_API_KEY"] = "sk-test"  # the operator's key, as if read from .env
import chatgpt  # noqa: E402
import claims  # noqa: E402

calls = []
reply = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="hi")])
claims.anthropic.Anthropic = lambda: SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: calls.append(kw) or reply))

# On this machine only: the key is the user's own, no cap.
assert claims.guard_server_credentials(local=True) and claims.is_live() and claims.SHARED_CALL_LIMIT is None
assert [claims.ask("s", "x") for _ in range(5)] == ["hi"] * 5

# Reachable from the network, no opt-in: the key is not used at all, the app stays in mock mode.
assert not claims.guard_server_credentials(local=False)
assert claims.server_key_present() and not claims._claude() and not claims.is_live()

# Opted in: shared, but capped for the whole process.
os.environ["PARKREFUND_SHARE_SERVER_KEY"], os.environ["PARKREFUND_SHARED_CALLS_PER_HOUR"] = "1", "2"
assert claims.guard_server_credentials(local=False) and claims.is_live() and claims.SHARED_CALL_LIMIT == 2
calls.clear()
claims._shared_calls.clear()
assert claims.ask("s", "x") == claims.ask("s", "x") == "hi"
try:
    claims.ask("s", "x")
    raise AssertionError("the third shared call in an hour must be refused")
except RuntimeError as e:
    assert "used its 2 AI requests" in str(e) and len(calls) == 2  # refused before anything was sent
os.environ["PARKREFUND_SHARED_CALLS_PER_HOUR"] = ""
assert claims.guard_server_credentials(local=False) and claims.SHARED_CALL_LIMIT == 30  # default cap

# A visitor's own ChatGPT sign-in (a browser's, not the process-wide one) is theirs: never capped.
claims.SHARED_CALL_LIMIT = 0


class Stream:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def __iter__(self):
        return iter([])

    def get_final_response(self):
        return SimpleNamespace(status="completed", output_text="own", output_parsed=None)


real = chatgpt.signed_in, chatgpt.shared, chatgpt.token
chatgpt.signed_in, chatgpt.shared, chatgpt.token = (lambda: True), (lambda: False), (lambda: "AT")
claims.openai.OpenAI = lambda **kw: SimpleNamespace(responses=SimpleNamespace(stream=lambda **kw: Stream()))
assert claims.ask("s", "x") == "own"
chatgpt.shared = lambda: True  # api.py's one sign-in for everyone counts as shared
try:
    claims.ask("s", "x")
    raise AssertionError("a shared ChatGPT sign-in must be capped")
except RuntimeError as e:
    assert "used its 0 AI requests" in str(e)
chatgpt.signed_in, chatgpt.shared, chatgpt.token = real
print("ok credentials guard")

# api.py: --chatgpt on a network address is refused before any sign-in or server starts.
env = {**os.environ, "HOST": "0.0.0.0", "PARKREFUND_SHARE_SERVER_KEY": "", "ANTHROPIC_API_KEY": ""}
r = subprocess.run([sys.executable, os.path.join(ROOT, "api.py"), "--chatgpt"], env=env, capture_output=True, text=True, timeout=30)
assert r.returncode == 1 and "Refusing --chatgpt on HOST=0.0.0.0" in r.stderr, (r.returncode, r.stderr[-300:])
print("ok api.py refuses --chatgpt on the network")

# app.py: on a network-reachable server the key is ignored and the operator is told why; on 127.0.0.1 it is used.
from streamlit import config  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

os.environ["PARKREFUND_SHARE_SERVER_KEY"] = ""
config.set_option("server.address", "")
at = AppTest.from_file(os.path.join(ROOT, "app.py")).run(timeout=30)
assert any("won't spend the API key" in w.value for w in at.warning)
assert not any("Using Claude" in s.value for s in at.success)
config.set_option("server.address", "127.0.0.1")
at = AppTest.from_file(os.path.join(ROOT, "app.py")).run(timeout=30)
assert any("Using Claude" in s.value for s in at.success) and not any("won't spend" in w.value for w in at.warning)
print("ok app.py")
