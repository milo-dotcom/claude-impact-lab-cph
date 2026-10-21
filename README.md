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

Test:

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import anthropic; print(anthropic.Anthropic().messages.create(model='claude-sonnet-5-5', max_tokens=20, messages=[{'role':'user','content':'Say ready'}]).content[0].text)"
```

## Run the demo (ParkRefund)

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py                                   # no .env → mock mode, everything still works
PARKREFUND_MODEL=claude-opus-5-5 .venv/bin/streamlit run app.py  # with .env → live
.venv/bin/python api.py                                          # optional: HTTP API + /admin queue for the iOS app
```

What it is: AirHelp for Danish parking fines — upload the ticket, get an honest verdict, a Danish
appeal letter, no win no fee. Concept and plan: `CONCEPT.md`. Demo script: `PITCH.md`.
All data is synthetic. The model drafts and recommends; a human files.

Don't `export ANTHROPIC_API_KEY` in your shell. If you do, Claude Code will bill the event credits instead of your subscription.
