"""Two browsers on one ParkRefund server: each gets its own ChatGPT sign-in, signing one out leaves the
other alone, shutdown revokes both, and the sign-in button only shows on a 127.0.0.1-bound app.
Streamlit's AppTest plays the browsers; a fake OpenAI and a fake system browser replace the network.

    .venv/bin/python tests/test_chatgpt_browsers.py
"""
import os
import sys
import tempfile
import threading
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_PROFILE"] = os.environ["OPENAI_API_KEY"] = ""  # only ChatGPT can go live
import chatgpt  # noqa: E402
import claims  # noqa: E402
from streamlit import config  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

chatgpt.REG_PATH = os.path.join(tempfile.mkdtemp(), "chatgpt.json")
revoked = []


def fake_json(url, form=None, token=None):
    if url.endswith("openid-configuration"):
        return {"issuer": chatgpt.ISSUER, "authorization_endpoint": f"{chatgpt.ISSUER}/authorize",
                "token_endpoint": f"{chatgpt.ISSUER}/token", "revocation_endpoint": f"{chatgpt.ISSUER}/revoke"}
    if url.endswith("/token"):  # each sign-in gets its own tokens, named after its code
        return {"access_token": "AT-" + form["code"], "refresh_token": "RT-" + form["code"], "expires_in": 3600,
                "scope": chatgpt.SCOPES}
    if url.endswith("/models"):
        return {"models": [{"slug": "gpt-test", "visibility": "list"}]}
    if url.endswith("/revoke"):
        revoked.append(form["token"])
        return {}
    raise AssertionError(url)


codes = iter(["A", "B"])


def fake_browser(url):  # the user approves in the system browser; ChatGPT calls the loopback back
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    query = urlencode({"code": next(codes), "state": q["state"], "client_id": "oaiapp_1"})
    threading.Thread(target=lambda: urllib.request.urlopen(q["redirect_uri"] + "?" + query), daemon=True).start()


chatgpt._json = fake_json
chatgpt.login.__defaults__ = (fake_browser,)

PAGE = """
import streamlit as st, chatgpt, claims
if st.button("sign in", key="in"):
    chatgpt.login()
if st.button("sign out", key="out"):
    chatgpt.logout()
st.write(f"signed_in={chatgpt.signed_in()} live={claims.is_live()} token={chatgpt.token() if chatgpt.signed_in() else '-'}")
"""


def state(at):
    return at.markdown[-1].value


a, b = AppTest.from_string(PAGE).run(), AppTest.from_string(PAGE).run()
assert state(a) == state(b) == "signed_in=False live=False token=-"

a.button(key="in").click().run(timeout=10)
assert state(a) == "signed_in=True live=True token=AT-A"
assert state(b.run()) == "signed_in=False live=False token=-", "browser B must not see A's sign-in"
assert not chatgpt._shared and not chatgpt.signed_in(), "nothing may leak into the process-wide sign-in"

b.button(key="in").click().run(timeout=10)
assert state(b) == "signed_in=True live=True token=AT-B" and state(a.run()) == "signed_in=True live=True token=AT-A"

a.button(key="out").click().run()
assert revoked == ["RT-A"] and state(a) == "signed_in=False live=False token=-"
assert state(b.run()) == "signed_in=True live=True token=AT-B", "signing A out must leave B signed in"

chatgpt._revoke_all()  # what atexit runs when the app closes
assert revoked == ["RT-A", "RT-B"] and state(b.run()) == "signed_in=False live=False token=-"
print("ok two browsers")

# The sign-in button: hidden when the app listens on the network, shown when it is bound to 127.0.0.1.
app = os.path.join(ROOT, "app.py")
config.set_option("server.address", "")
at = AppTest.from_file(app).run(timeout=30)
assert not [x for x in at.button if x.label == "Continue with ChatGPT"]
assert any("--server.address 127.0.0.1" in c.value for c in at.caption)
config.set_option("server.address", "127.0.0.1")
at = AppTest.from_file(app).run(timeout=30)
assert [x for x in at.button if x.label == "Continue with ChatGPT"]
print("ok local-only button")
