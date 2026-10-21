# ParkRefund — 2-minute pitch + demo script

*Claude Impact Lab Copenhagen, 21 Oct 2026. Theme: "What does AI mean for my job?"*

## Before you walk up (5 min)

```bash
git checkout main && git pull
.venv/bin/pip install -r requirements.txt
PARKREFUND_MODEL=claude-opus-5-5 .venv/bin/streamlit run app.py     # with .env → LIVE
.venv/bin/streamlit run app.py                                       # no .env → MOCK (fallback)
```

- Sidebar must say **LIVE** for the real demo. If the API is down or slow, delete `.env`, restart:
  everything still works in **MOCK** mode with the same screens — say "running on cached results"
  and carry on. Nobody will know the difference.
- Have `data/tickets/0_NP-2026-004117.png` open in a Finder/Explorer window for the upload.
- Pre-load the page once so Streamlit is warm. Browser zoom 125%.

## The pitch (2:00)

**Hook (0:00–0:15)**
> A parking fine in Denmark is 650 to 900 kroner. Plenty of them would fall on appeal — bad signage,
> a plate typo in the app, a two-minute unloading stop — but almost nobody appeals, because it's
> tedious and you don't know the rules. AirHelp built a company
> on exactly this gap for flights. We built it for parking. ParkRefund: no win, no fee.

**Demo — the customer (0:15–1:25)**

| Step | Click | Say |
|---|---|---|
| 1 | Upload `0_NP-2026-004117.png` under **1 · Your ticket** | "Photo of the fine. Claude reads it — operator, ticket number, plate, amount — and fills the form." |
| 2 | Scroll **2 · What happened** — the story is prefilled (no entrance sign, photos taken) | "You tell us what happened in your own words. Tick the evidence you have." |
| 3 | **Check my case** | "Here's the honest part. 78%, strong. The ground is *Skiltning* — that's the regulator's own category. It tells you what helps, what hurts, and exactly which photo to go take." |
| 4 | **Draft my appeal** (Danish) → **Download** | "A ready-to-send *indsigelse* to the operator, in Danish, citing the ticket, the ground, the attached evidence. You send it." |
| 5 | **5 · If we win** | "850 back, we keep 30%, you get 595. If we lose, you pay nothing." |
| 6 | Tab **Pick a sample case** → **"Private - forgot p-skive"** → **Check my case** | "And this is why people trust it: 5%, weak, *we wouldn't take this case.* We say no when the rulebook says no." |

**The job angle (1:25–1:50)** — sidebar → **Ops dashboard**
> This is the back office. Every claim is triaged and drafted by the model. The paralegal's job used
> to be reading all of them. Now it's *this* queue — only the 40–60% cases, the ones where judgement
> matters — plus the final say on every filing. Model drafts and recommends; a human files.

(If the iOS build is running: "and it's a product — same flow on a phone, submissions land in this queue.")

**Close (1:50–2:00)**
> Built in three hours on synthetic data. What it needs next: a lawyer on the rulebook, the real
> Parkeringsklagenævnet decisions for calibration, and operator APIs for filing. Thank you.

## If something breaks

| Symptom | Do |
|---|---|
| Spinner > 15 s on "Check my case" | Say "let me switch to cached" → delete `.env`, restart, continue in MOCK. |
| Upload doesn't prefill | Pick sample case 1 from the dropdown instead; same data. |
| Ops dashboard missing from sidebar | `pages/` not on your checkout — `git pull`. Worst case: skip it, say the line anyway. |
| Letter is in English | Radio under **4 · Your appeal letter** → `da`. |

## What's true and what's synthetic (if asked)

- Rulebook (`rules.py`) is a simplified approximation written today — not legal advice.
- Categories are Parkeringsklagenævnet's real 11 decision categories (`docs/data-sources.md`).
- All operators, kommuner, plates, tickets, pipeline stats: invented. No real data was used.
- The model drafts and recommends. A human files. That line is the product.
