# Exception Manager: the ERP is the last to know

*Copenhagen Claude Impact Lab, 21 Oct 2026. Theme: "What does AI mean for my job?" Path: **The organization**, deciding which work stays human.*

## Problem

A complex hardware project slips for reasons that were already written down somewhere. A supplier email says "castings delayed ~3 weeks". A QC note says "flanges rejected, rework 10 days". A quote carries an 8% surcharge. The ERP still shows every PO as *confirmed, on time* because nobody has updated it yet.

The project manager has no shortage of dashboards. What they lack is someone who reads every source, connects a sentence in an email to a PO line and a task on the critical path, and asks: **does this move our delivery date or our cost, and what should we do about it?**

## User

> As a **project / supply chain manager delivering a complex hardware system**, I want **AI to detect operational risks across fragmented data** so I can **intervene before costs or schedules slip**.

## What it does (hackathon scope)

```
emails + internal notes ──► Claude extracts signals ──┐  (supplier, PO, new date, quote)
ERP PO export ────────────────────────────────────────┼─► Python reconciles + computes impact
project schedule ─────────────────────────────────────┘     (critical path, days late, € at risk)
                                                              │
                     Claude explains + recommends 2–3 actions ◄┘  (uses past decisions)
                                                              │
                     Human decides ──► decision log ──► outcome recorded ──► fed into next run
```

1. **Detect.** Find where unstructured signals contradict structured plans, plus gaps in the structured data itself (a needed part with no PO).
2. **Quantify.** Deterministic code propagates the change through the schedule. It reports which tasks move, the new customer delivery date, and the € exposure (penalties and surcharges). The LLM never does date math.
3. **Prioritise.** Rank by impact. A slip on a task with float is marked as low priority, so the user isn't flooded with alerts.
4. **Recommend.** Claude explains why the exception matters, quotes the evidence, and proposes concrete actions with trade-offs.
5. **Decide and learn.** The human picks an action, which is logged. When the outcome arrives, it is recorded, and later recommendations for the same supplier or failure type see that history.

## Value

| Metric | How we show it in the demo |
|---|---|
| **Detection lead time** | Days between the first signal and the ERP update (planted: ~4 weeks) |
| **Recall / false alarms** | Planted exceptions found / distractors wrongly flagged, scored against `ground_truth.json` |
| **€ and days at risk surfaced** | Sum of computed impact for the top exceptions |

## Not in scope (deliberately)

- Live ERP or email connectors. The data is synthetic CSV and JSONL files, and in a real deployment integration is the hard part.
- Automatically executing actions. The AI recommends and a human decides, which is the part of the job that stays human.
- Real learning or fine-tuning. The hackathon version of the loop is that past decisions and outcomes are put into the prompt.
- Chat interface and dashboards.

## Data

All data is **synthetic**: a fictional company, a fictional product and fictional suppliers. No real company data. See [PREP.md](PREP.md#3-synthetic-data-spec).

## Run (filled in at the event)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
```
