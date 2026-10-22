"""chatgpt.login/token/logout without network or browser: a fake OpenAI answers discovery, token and
model calls; a fake browser hits the loopback callback. Checks state validation, PKCE, scope check,
registration persistence, refresh and revocation.

    .venv/bin/python tests/test_chatgpt_login.py
"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import threading
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chatgpt  # noqa: E402

chatgpt.REG_PATH = os.path.join(tempfile.mkdtemp(), "chatgpt.json")
calls = []


def fake_json(url, form=None, token=None):
    calls.append((url, form, token))
    if url.endswith("openid-configuration"):
        return {"issuer": chatgpt.ISSUER, "authorization_endpoint": f"{chatgpt.ISSUER}/api/accounts/authorize",
                "token_endpoint": f"{chatgpt.ISSUER}/api/accounts/oauth/token", "revocation_endpoint": f"{chatgpt.ISSUER}/revoke"}
    if url.endswith("/token"):
        assert form["resource"] == chatgpt.RESOURCE
        return {"access_token": "AT-" + form["grant_type"], "refresh_token": "RT2", "expires_in": 3600, "token_type": "Bearer",
                "scope": chatgpt.SCOPES}
    if url.endswith("/models"):
        assert token == "AT-authorization_code"
        return {"models": [{"slug": "hidden", "visibility": "hide"}, {"slug": "gpt-test", "display_name": "Test", "visibility": "list"}]}
    if url.endswith("/revoke"):
        return {}
    raise AssertionError(url)


chatgpt._json = fake_json
auth_urls = []


def fake_browser(url):
    auth_urls.append(url)
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    cb = q["redirect_uri"]

    def go():
        try:  # wrong state must be rejected and must not end the wait
            urllib.request.urlopen(cb + "?" + urlencode({"code": "x", "state": "wrong"}))
        except urllib.error.HTTPError as e:
            assert e.code == 400
        urllib.request.urlopen(cb + "?" + urlencode({"code": "CODE", "state": q["state"], "client_id": "oaiapp_123"}))
    threading.Thread(target=go, daemon=True).start()


# first sign-in: dynamic registration
chatgpt.login(open_browser=fake_browser)
q = {k: v[0] for k, v in parse_qs(urlparse(auth_urls[0]).query).items()}
assert q["client_id"] == "dynamic_agent_client" and q["agent_name_hint"] == "ParkRefund" and q["ext_agent_host_id"].startswith("urn:uuid:")
assert q["code_challenge_method"] == "S256" and q["scope"] == chatgpt.SCOPES
exchange = next(f for u, f, _ in calls if u.endswith("/token"))
assert exchange["client_id"] == "oaiapp_123" and exchange["code"] == "CODE" and exchange["redirect_uri"] == q["redirect_uri"]
expected = base64.urlsafe_b64encode(hashlib.sha256(exchange["code_verifier"].encode()).digest()).rstrip(b"=").decode()
assert q["code_challenge"] == expected
assert chatgpt.signed_in() and chatgpt.model() == "gpt-test" and chatgpt.token() == "AT-authorization_code"
assert json.load(open(chatgpt.REG_PATH)) == {"host_id": q["ext_agent_host_id"], "client_id": "oaiapp_123"}
assert oct(os.stat(chatgpt.REG_PATH).st_mode & 0o777) == "0o600"

# expiry triggers a refresh grant with the rotated token kept
chatgpt._shared["expires_at"] = 0
assert chatgpt.token() == "AT-refresh_token" and chatgpt._shared["refresh_token"] == "RT2"

# logout revokes and clears; a second call is a no-op
chatgpt.logout()
assert not chatgpt.signed_in() and calls[-1][1]["token_type_hint"] == "refresh_token"
n = len(calls)
chatgpt.logout()
assert len(calls) == n

# second sign-in reuses the issued client id and sends no name hint
calls.clear()
chatgpt.login(open_browser=fake_browser)
q2 = {k: v[0] for k, v in parse_qs(urlparse(auth_urls[1]).query).items()}
assert q2["client_id"] == "oaiapp_123" and "agent_name_hint" not in q2 and q2["ext_agent_host_id"] == q["ext_agent_host_id"]

# plan usage not granted -> clear error, no session
chatgpt.logout()
real = chatgpt._json
chatgpt._json = lambda url, form=None, token=None: {**real(url, form, token), "scope": "openid email"} if url.endswith("/token") else real(url, form, token)
try:
    chatgpt.login(open_browser=fake_browser)
    raise AssertionError("should fail without plan scope")
except RuntimeError as e:
    assert "plan usage" in str(e) and not chatgpt.signed_in()


def deny_browser(url):  # the user presses deny: ChatGPT redirects back with error=access_denied
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    threading.Thread(target=lambda: urllib.request.urlopen(
        q["redirect_uri"] + "?" + urlencode({"error": "access_denied", "state": q["state"]})), daemon=True).start()


try:
    chatgpt.login(open_browser=deny_browser)
    raise AssertionError("a denied consent must fail")
except RuntimeError as e:
    assert "declined access" in str(e) and not chatgpt.signed_in()
print("ok")
