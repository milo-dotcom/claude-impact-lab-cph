"""Sign in with ChatGPT: a ChatGPT Plus/Pro user runs ParkRefund on their own plan, no API key.

Official flow (developers.openai.com/siwc/token-sharing-open-source): PKCE OAuth in the system
browser, loopback callback on 127.0.0.1, then the public Responses API with the OAuth token.

Tokens live only in memory, one sign-in per browser: under Streamlit each visitor's sign-in sits in
their own st.session_state, so nobody can use another visitor's plan. Outside Streamlit (api.py, evals,
tests) there is one sign-in for the process. Closing the app revokes every sign-in (best effort).
Only the app registration (host id + issued client id, no secrets) is kept in
~/.config/parkrefund/chatgpt.json so ChatGPT does not list a new "ParkRefund" app on every sign-in.
"""
import atexit
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
APP_NAME = "ParkRefund"
REG_PATH = os.path.expanduser("~/.config/parkrefund/chatgpt.json")
LOGIN_TIMEOUT = 300

_shared = {}  # the sign-in outside Streamlit: client_id, access_token, refresh_token, expires_at, models
# shortcut: holds every sign-in until logout or shutdown (closed tabs too), fine for a local app; prune if hosted
_live = []
_endpoints = None


def _box() -> dict:
    """The current browser's sign-in (empty dict = signed out). Under Streamlit, never a shared one."""
    try:
        import streamlit as st
        running = st.runtime.exists()
    except ImportError:
        running = False
    if not running:
        return _shared
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return {}  # a Streamlit thread with no browser behind it must not borrow anyone's sign-in
    return st.session_state.setdefault("chatgpt", {})


def signed_in() -> bool:
    return bool(_box())


def shared() -> bool:
    """True when the current sign-in is the process-wide one (api.py, scripts), not a browser's own."""
    return _box() is _shared


def model() -> str:
    """First model the signed-in account lists; the plan decides what is available."""
    return _box().get("models", [None])[0] or "gpt-6.1-sol"


def _json(url, form=None, token=None):
    headers = {"accept": "application/json"}
    if form:
        headers["content-type"] = "application/x-www-form-urlencoded"
    if token:
        headers["authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, data=urlencode(form).encode() if form else None, headers=headers), timeout=30) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        code = (json.loads(e.read() or b"{}") or {}).get("error") if e.headers.get_content_type() == "application/json" else None
        raise RuntimeError(f"ChatGPT sign-in error ({e.code}{': ' + code if isinstance(code, str) else ''}).") from e
    except urllib.error.URLError as e:
        raise RuntimeError("Could not reach ChatGPT sign-in. Check your connection.") from e
    return json.loads(body) if body else {}


def _ep():
    global _endpoints
    if _endpoints is None:
        d = _json(f"{ISSUER}/.well-known/openid-configuration")
        keys = ("authorization_endpoint", "token_endpoint", "revocation_endpoint")
        if d.get("issuer") != ISSUER or not all(str(d.get(k, "")).startswith(ISSUER + "/") for k in keys):
            raise RuntimeError("ChatGPT sign-in configuration could not be verified.")
        _endpoints = d
    return _endpoints


def _registration() -> dict:
    try:
        with open(REG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"host_id": uuid.uuid4().urn}


def login(open_browser=webbrowser.open) -> None:
    """Browser sign-in for the current browser; blocks until the callback arrives or LOGIN_TIMEOUT passes."""
    box = _box()
    ep, reg = _ep(), _registration()
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    got = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items() if len(v) == 1}
            if u.path != "/auth/callback" or not secrets.compare_digest(q.get("state", ""), state):
                self.send_response(400)
                self.end_headers()
                return
            got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"<p style='font:17px system-ui;margin:18vh auto;max-width:32rem'>Return to ParkRefund. You can close this tab.</p>")

    srv = HTTPServer(("127.0.0.1", 0), Callback)
    srv.timeout = 1
    redirect = f"http://127.0.0.1:{srv.server_port}/auth/callback"
    params = {"client_id": reg.get("client_id", "dynamic_agent_client"), "response_type": "code", "redirect_uri": redirect,
              "scope": SCOPES, "resource": RESOURCE, "state": state, "nonce": nonce, "code_challenge_method": "S256",
              "code_challenge": challenge, "ext_agent_host_id": reg["host_id"]}
    if "client_id" not in reg:
        params["agent_name_hint"] = APP_NAME
    try:
        open_browser(f"{ep['authorization_endpoint']}?{urlencode(params)}")
        deadline = time.time() + LOGIN_TIMEOUT
        while not got and time.time() < deadline:
            srv.handle_request()
    finally:
        srv.server_close()
    if not got:
        raise RuntimeError("ChatGPT sign-in timed out. Try again.")
    if got.get("error") == "access_denied":  # the user pressed deny on ChatGPT's consent screen
        raise RuntimeError("You declined access in ChatGPT, so ParkRefund stays in demo mode. "
                           "Sign in again and allow plan usage to run it on your plan.")
    if "error" in got:
        raise RuntimeError(f"ChatGPT sign-in was not completed ({got['error']}).")
    client_id = got.get("client_id") or reg.get("client_id")
    if not client_id or client_id == "dynamic_agent_client":
        raise RuntimeError("ChatGPT did not complete app registration. Try signing in again.")
    if reg.get("client_id") != client_id:
        os.makedirs(os.path.dirname(REG_PATH), exist_ok=True)
        with open(REG_PATH, "w", encoding="utf-8") as f:
            json.dump({"host_id": reg["host_id"], "client_id": client_id}, f)
        os.chmod(REG_PATH, 0o600)
    tok = _json(ep["token_endpoint"], {"grant_type": "authorization_code", "client_id": client_id, "code": got["code"],
                                       "code_verifier": verifier, "redirect_uri": redirect, "resource": RESOURCE})
    if PLAN_SCOPE not in tok.get("scope", "").split():
        raise RuntimeError("Signed in, but ChatGPT plan usage was not allowed for ParkRefund. Sign in again and enable it.")
    listing = _json(f"{RESOURCE}/models", token=tok["access_token"])
    _revoke(box)  # signing in again replaces this browser's old sign-in
    box.update(client_id=client_id, access_token=tok["access_token"], refresh_token=tok["refresh_token"],
               expires_at=time.time() + tok["expires_in"],
               models=[m["slug"] for m in listing.get("models", []) if m.get("visibility") == "list"])
    _live.append(box)


def token() -> str:
    """Access token for the current browser's account, refreshed shortly before it expires."""
    s = _box()
    if not s:
        raise RuntimeError("Not signed in with ChatGPT.")
    if time.time() > s["expires_at"] - 60:
        tok = _json(_ep()["token_endpoint"], {"grant_type": "refresh_token", "client_id": s["client_id"],
                                              "refresh_token": s["refresh_token"], "resource": RESOURCE})
        s.update(access_token=tok["access_token"], refresh_token=tok.get("refresh_token") or s["refresh_token"],
                 expires_at=time.time() + tok["expires_in"])
    return s["access_token"]


def _revoke(box: dict) -> None:
    """Empty one sign-in and revoke it at OpenAI (best effort; the user can also disconnect in ChatGPT settings)."""
    s = dict(box)
    box.clear()
    _live[:] = [b for b in _live if b is not box]
    if not s:
        return
    try:
        _json(_ep()["revocation_endpoint"], {"token": s["refresh_token"], "token_type_hint": "refresh_token", "client_id": s["client_id"]})
    except Exception:
        pass


def logout() -> None:
    """Sign the current browser out."""
    _revoke(_box())


@atexit.register
def _revoke_all() -> None:
    for box in list(_live):
        _revoke(box)
