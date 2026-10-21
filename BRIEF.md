# Team brief: Exception Manager

**30-second pitch:** "In hardware projects, the warning that a delivery will slip is usually sitting in a supplier email weeks before the ERP shows it. We'll build an agent that reads emails and notes, connects them to POs and the project schedule, computes whether the customer delivery date or cost moves, and recommends what to do. A human makes the call, and the system remembers how that went next time."

**Path:** The organization. AI does the reading and cross-referencing, and humans keep the trade-off decisions. The decision log turns one manager's judgment into shared practice.

**User story:** As a project / supply chain manager delivering a complex hardware system, I want AI to detect operational risks across fragmented data so I can intervene before costs or schedules slip.

## What we demo
1. Four messy sources (POs, schedule, emails, internal notes) for a fictional vacuum-system project
2. A ranked list of exceptions. The top one: "Pump slip is on the critical path. Delivery 18 Dec → ~11 Jan, €45k penalties." It shows the quoted email and the source PO.
3. It **deprioritises** what doesn't matter (a late part on a task with float) and ignores noise
4. Claude recommends 2–3 actions with trade-offs, and a human picks one, which is logged
5. A new email arrives, the outcome is recorded, and the next recommendation uses that history
6. Score against planted ground truth: exceptions found, false alarms, days of early warning

## Why it's not "another dashboard"
- Claude reads **unstructured text** and links it to records. Plain Python does the date and € math, so the numbers are right.
- Every alert carries **evidence + computed impact + a decision**. Without those, it's just a notification.

## Stack
Python, pandas, Claude API (Sonnet for extraction, Opus for recommendations), Streamlit. Synthetic data only. No connectors, no frameworks.

## Roles (one file each, no merge pain)
Data + story + pitch · `engine.py` (schedule/impact) · `llm.py` (extraction/recommendation) · `app.py` (UI + decision log) · `eval.py` + feedback loop

## Plan
Round 1: data + engine + extraction work end-to-end in the terminal. Round 2: UI, recommendations, decision loop, score. Freeze 15 min before demos and rehearse twice.

Details: [README.md](README.md) · data spec, risks, architecture: [PREP.md](PREP.md)
