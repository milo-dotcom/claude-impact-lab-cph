# Claude Impact Lab Copenhagen

*21 Oct 2026. Theme: "What does AI mean for my job?"*

## Setup

```bash
git clone https://github.com/milo-dotcom/claude-impact-lab-cph.git && cd claude-impact-lab-cph
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Save your API key from console.anthropic.com to `.env` (it isn't echoed or saved in shell history):

```bash
read -s "k?Paste API key: " && printf 'ANTHROPIC_API_KEY=%s\n' "$k" > .env && unset k && echo saved
```

Two other ways to go live, each one line in `.env`:

- `ANTHROPIC_PROFILE=default` — use a Claude login instead of a key: run `ant auth login` (browser sign-in to your Console account; `--profile <name>` picks the name). Bills that Console organization pay-as-you-go. A Claude Pro/Max plan has no API access, so it cannot power the app.
- `OPENAI_API_KEY=sk-...` — run on OpenAI (default model `gpt-6.1-sol`; override with `PARKREFUND_MODEL`). Needs a pay-as-you-go platform key; a ChatGPT Plus subscription has no API access.

- **Sign in with ChatGPT** — no `.env` at all: click **Continue with ChatGPT** in the app's sidebar (or start the API with `.venv/bin/python api.py --chatgpt`). A ChatGPT Plus/Pro user signs in in the browser and the app runs on their plan, via OpenAI's official [Sign in with ChatGPT](https://developers.openai.com/siwc) flow for open-source, locally run tools. Tokens stay in memory: closing the app signs out and revokes the session. Only the app registration (no secrets) is kept in `~/.config/parkrefund/chatgpt.json`, so ChatGPT lists one "ParkRefund" connection, not one per run. Users manage or disconnect it at chatgpt.com/settings/usage.

Precedence: a ChatGPT sign-in wins while it lasts, then Claude, then an OpenAI key.

**Credentials and safety.** The app never asks a visitor for a key: credentials come only from `.env` on the machine running it, are read for presence only, and are never logged, stored, or sent to the browser or the API's clients (errors are rewritten to fixed messages). Nothing runs live unless `.env` opts in, so a Claude login on the machine is never used silently, and the app never logs in, logs out, or switches profiles. Running it leaves no credential behind beyond what you put in `.env`. To end access: delete the line from `.env`, revoke the key in the provider console, or log out with the tool that created the profile (`ant auth logout` or `/logout` in Claude Code). For anything beyond your own laptop, use a dedicated API key with a spend limit and revoke it afterwards, and keep `api.py` on localhost: it has no auth, so anyone who can reach it spends your credits.

Test:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import anthropic; print(anthropic.Anthropic().messages.create(model='claude-sonnet-5-5', max_tokens=20, messages=[{'role':'user','content':'Say ready'}]).content[0].text)"
```

## Run the demo (ParkRefund)

**Shareable 2-minute demo (no install):** https://claude.ai/artifact/XQufJwdkuqk9pL2cQx9kQ4 — eight screens, → to advance, N for speaker notes.

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py --server.address 127.0.0.1                                   # no .env → mock mode, everything still works
PARKREFUND_MODEL=claude-opus-5-5 .venv/bin/streamlit run app.py --server.address 127.0.0.1  # with .env → live
.venv/bin/python api.py                                          # optional: HTTP API + /admin queue for the iOS app
```

What it is: a free, open-source tool for better living in Denmark — upload a parking fine, get an honest verdict
and a Danish appeal letter. No company in the middle, no cut of your refund. Concept and plan: `CONCEPT.md`. Demo script: `PITCH.md`. **Screenshots of every step + one-command
end-to-end test: `DEMO.md`.** First 30 days after launch: `GTM.md`.
All data is synthetic. The model drafts and recommends; a human files.

## Whose tokens get spent

ParkRefund only spends AI credit that belongs to the person using it:

- **Run it on your own computer** with `--server.address 127.0.0.1` (as above). Only your machine can reach it,
  so the key in your `.env` and the "Continue with ChatGPT" sign-in are yours alone.
- **ChatGPT sign-in is per browser.** Each browser keeps its own sign-in in memory; another tab or visitor
  starts signed out. Closing the app revokes every sign-in. The button only appears on a `127.0.0.1` app,
  because the sign-in page opens on the machine running the app. OpenAI only allows plan usage in locally
  hosted apps for now.
- **Reachable from other computers** (plain `streamlit run app.py`, Streamlit Cloud, `api.py` with
  `HOST=0.0.0.0`): the `.env` key is **not used** and the app runs in demo mode, so nobody can spend it.
  To share it on purpose, set `PARKREFUND_SHARE_SERVER_KEY=1`. It is then capped at
  `PARKREFUND_SHARED_CALLS_PER_HOUR` requests an hour for the whole server (default 30). Also set a spend
  limit on the key in the provider's console. `api.py --chatgpt` refuses to start off `127.0.0.1` without it.

Don't `export ANTHROPIC_API_KEY` in your shell. If you do, Claude Code will bill the event credits instead of your subscription.
