# Hackathon prep: Exception Manager

My working notes for 21 Oct. [BRIEF.md](BRIEF.md) is the version to share with teammates.

**Event reality check** (from the organisers' email): doors open 15:00, start 16:00, end 21:00. There are two build rounds with dinner at 18:00 in between, then demos. Teams of 3–5 form in the room, and you pick one of four paths. **Real build time is about 3 hours, not 5.** API credits go to a Console org, not to Claude.ai.

---

## 1. Challenging the idea

| Assumption in the idea | Challenge | Decision |
|---|---|---|
| "Ingest fragmented data" is step 1 | With synthetic files, ingestion is just `pd.read_csv`. In real life it's the hardest part, but it doesn't win a hackathon. | Load files. Say out loud that connectors are out of scope. |
| AI finds exceptions | Late POs and missing POs are already caught by ERP exception reports and SQL. If the demo only finds those, the judges will ask "why AI?" | AI's job is **reading unstructured text (emails, notes) and linking it to records**. Structural checks are plain Python. |
| AI estimates consequences | LLMs are unreliable at date arithmetic and critical-path logic, and an industrial audience will spot a wrong date. | **Python computes the impact** (CPM forward pass, days, €). Claude only explains it. |
| 7 capabilities | Too many for 3 hours. | Build **one exception type end-to-end** (supplier delay → schedule impact → action → decision). The other types use the same extraction schema and are cheap to add. |
| Recommend actions | The real adoption killer is whether a PM would trust it. | Every exception card shows **the quoted evidence + the source record + the deterministic calculation**. A human decides. |
| "Learns from feedback" | Without real outcomes, any claim of learning is an overclaim. | Past decisions and outcomes go into the prompt (retrieval by supplier or signal type). Call it that, not ML. |
| Fits the theme? | The judges will look for the connection to the theme. | **Organization path:** reading and cross-referencing goes to AI. Trade-offs and supplier relationships stay human. The decision log turns one PM's judgment into shared organisational memory. |

### The most important problem worth solving in 3 hours
> **The signal that a delivery will slip usually exists in an email weeks before the ERP shows it. Nobody connects that sentence to the critical path.**

The smallest genuinely useful version is this. For one project, read supplier emails and internal notes, find statements that contradict the ERP or the schedule, compute whether the customer delivery date or cost moves, rank the results, recommend an action, and log the human's decision. If it does only that, but credibly, it's useful.

---

## 2. Demo (3 minutes)

1. **Hook (15 s).** "The ERP said every PO was green. The project slipped three weeks. The warning was in an email four weeks earlier."
2. **The mess (20 s).** Show the four sources: PO export, schedule, 15 emails, 8 internal notes. Nobody reads all of them.
3. **Run (30 s).** A ranked exception list appears. At the top, the vacuum pump slip is on the critical path, so the customer delivery moves from **18 Dec → ~11 Jan** with **€45k in late-delivery penalties**. The card shows the quoted email line, the PO row and the affected tasks.
4. **It knows what doesn't matter (15 s).** The gas panel part is also 8 days late, but the task has 12 days of float, so it's ranked LOW. A distractor (another project's delay) is ignored.
5. **Recommend → decide (40 s).** Three options with trade-offs: expedite for €X and recover 10 days, move pump integration after mechanical assembly, or qualify the alternative supplier. The human picks one and gives a reason. It's logged.
6. **Close the loop (40 s).** Drop in a new email: "expedite confirmed, ships 10 Nov". Re-run. The exception shrinks, the outcome is recorded, and the next Kessler exception's recommendation cites that history: "expedite worked last time, 2 of 3 weeks recovered."
7. **Score (20 s).** "6/6 planted exceptions found, 0/5 distractors flagged, first signal 28 days before the ERP would show it." The AI did the reading. The human made the call.

**Rehearse it twice before demos. Freeze the code 15 minutes before.**

---

## 3. Synthetic data spec

A fictional company, product, customer and suppliers. **No ATLANT data, names or part numbers.** Generate the files at the event as task #1 (about 15 min with Claude Code from this spec).

**Scenario:** *Nordhavn Process Systems* builds an **NV-400 industrial vacuum process system** for the customer *Baltic Optics*. Contract delivery is **2026-12-18**, with liquidated damages of **€15,000 per week late**. Data is current as of **2026-10-21**.

### Files (`data/`)
| File | Shape | Content |
|---|---|---|
| `project.json` | object | name, customer, contract_delivery, ld_eur_per_week, as_of |
| `purchase_orders.csv` | ~20 rows | `po_id, part_no, description, supplier, qty, unit_price_eur, order_date, confirmed_delivery, status (open/confirmed/received), last_updated` |
| `schedule.csv` | 11 rows | `task_id, task, duration_days, depends_on (;-sep), required_parts (;-sep), planned_start` |
| `emails.jsonl` | ~15 | `id, date, from, to, subject, body`: realistic tone, some vague ("we're seeing some delays on castings, will revert") |
| `notes.jsonl` | ~8 | `id, date, author, channel (teams/meeting), text`: internal chat and meeting notes |
| `ground_truth.json` | list | planted exceptions + distractors, for `eval.py` |

### Schedule (critical path in bold)
**T02 Chamber machining 15d → T03 Leak test 3d → T04 Pump & valve integration 5d → T07 Mechanical assembly 8d → T08 Wiring & integration 6d → T09 Controls commissioning 7d → T10 FAT 4d → T11 Crating & shipping 3d**
The off-path tasks are T01 Frame fabrication 10d → T07, T05 Electrical cabinet 8d → T08, and T06 Gas panel 6d → T08. T05 and T06 should have about 10–12 days of float.

### Planted exceptions (what "good" looks like)
| ID | Source | Signal | Contradicts | Expected |
|---|---|---|---|---|
| E1 | Email 2026-10-02, *Kessler Vakuumtechnik* | Pump rotor lot failed inspection. Revised ship date 2026-11-20 (was 10-30). | PO says confirmed 10-30 | **HIGH**: critical path, delivery slips about 3 weeks, roughly €45k LDs |
| E2 | Email, *Flowtek* | Mass-flow controllers 8 days late | PO date | **LOW**: T06 has float |
| E3 | Email, *Baltic Steel* | 8% alloy surcharge on shipments after 15 Oct | PO unit prices for frame and chamber | **MED**: € cost delta, no schedule impact |
| E4 | Note (QC, Teams) | 4 of 12 flanges rejected, rework 10 days | PO status `received` | **HIGH**: T02 start delayed |
| E5 | Schedule vs POs | T11 needs `P-CRATE`, but there is no PO. A note mentions 15-day lead time. | — (structural, pure Python) | **MED**: must order by a computed date |
| E6 | Email 2026-10-09, *Östra Automation* | Asks to confirm drawing rev C vs D before production. No reply since. | Silence (12 days) | **MED**: T05 float is being consumed, so it becomes critical by a computed date |

### Distractors (must NOT be flagged)
| ID | Content |
|---|---|
| D1 | Kessler holiday closure 24 Dec–2 Jan. Their parts arrive well before. |
| D2 | Flowtek confirms a *different* PO on time |
| D3 | Supplier newsletter / price list for parts we don't buy |
| D4 | Internal note about a delay on *another project* ("Project Fjord") |
| D5 | "Slight delay" email on a PO that has already been received |

---

## 4. Architecture

```
data/*.csv|jsonl ──► engine.py  (pure Python, deterministic)
                      ├─ structural checks: missing PO, PO date > task need date
                      ├─ CPM forward pass → float per task, delivery date
                      └─ apply signals → new dates → Δ delivery, € (LDs + surcharges)
emails, notes ─────► llm.py  extract_signals()  Claude, tool use / JSON schema
                      → {source_id, supplier, po_id|part_no, signal_type, new_date, quote, confidence}
                      → validated: po_id must exist, quote must be a substring of the source
exception + impact + past decisions ─► llm.py  recommend()  → why it matters + 2–3 actions
app.py   (Streamlit)  ranked cards ▸ evidence ▸ impact ▸ actions ▸ Decide button → decisions.jsonl
eval.py  detected vs ground_truth.json → recall, false alarms, lead time
```

- **Models:** `claude-sonnet-5-5` for extraction (many small calls, fast). `claude-opus-5-5` for recommendations (few calls, better reasoning). Switch if credits run low.
- **Cache extraction output** to `signals.json`. The demo then never waits on the API and still works if the wifi dies. Run live once to prove it works, then run from the cache.
- **No frameworks.** No LangChain, vector DB or agent framework. About 4 files and about 400 lines.
- The closed loop is `decisions.jsonl` (`exception_id, supplier, signal_type, action, reason, decided_at, outcome, outcome_at`). `recommend()` gets the last N rows matching the supplier or signal type.

---

## 5. Risks

**Technical**
| Risk | Mitigation |
|---|---|
| Claude links an email to the wrong PO, or invents one | Require `quote` + `po_id`. Reject if the PO doesn't exist or the quote isn't in the source. Show the quote on the card. |
| Wrong dates or € from LLM arithmetic | All math in `engine.py`, with an assert-based check on the CPM |
| API key or credits not working at 16:30 | Console account created *before* the event. One teammate's key works for everyone at first. |
| Slow or flaky API during demo | Cached `signals.json` + demo mode |
| Four people editing one file | Split by file: engine / llm / app / data+eval |
| Streamlit state bugs on buttons | One page, `st.session_state` minimal. Fallback: CLI that prints markdown. |

**Product**
| Risk | Mitigation |
|---|---|
| "It's just a dashboard" | Lead with the cross-source contradiction and the decision, not the list |
| Data looks obviously planted | Vague and realistic wording, noise emails, distractors that are hard to tell apart |
| Alert fatigue (the real-world killer) | Show E2 ranked LOW and D4 ignored, on purpose |
| Overclaiming "learning" | Call it decision memory and be explicit |
| Team wants another idea | Have the backup (§7) ready. Offer the domain and data role on their idea if needed. |

---

## 6. Team plan (3–5 people)

| Role | Owns | Who |
|---|---|---|
| Domain + data + story | Synthetic data, ground truth, demo script, pitch | **Me** |
| Engine | `engine.py`: CPM, checks, impact, asserts | |
| LLM | `llm.py`: extraction schema, prompts, validation, cache | |
| App | `app.py`: cards, decide button, decision log | |
| (5th) Eval + loop | `eval.py`, outcome → next recommendation | |

**Timeline (estimate)**
- **16:00–16:30**: pitch, form the team, agree scope, shared repo, keys working
- **Round 1 → 18:00**: data committed (17:00), engine + extraction run end-to-end in the terminal, ugly is fine
- **Dinner 18:00**: review on paper, cut scope
- **Round 2 → ~20:15**: UI, recommendations, decision log (19:30), closed loop + eval score (20:00), **freeze**, rehearse twice
- **If behind, cut in this order:** eval polish → outcome loop (show as a slide) → Streamlit (CLI fallback). **Never cut** the evidence quote or the deterministic impact.

---

## 7. Backup idea: Closed-loop Industrial Learning Agent

A hidden Python function stands in for a physical process, for example coating thickness and uniformity as a function of temperature, pressure, precursor pulse and cycles, plus noise and a constraint. The agent proposes the next experiment with a rationale, the "process" returns a measurement, and the loop continues until the agent hits a target. **Metric:** experiments needed to reach the target, compared with a random or grid baseline.

- **Pros:** very demoable, clearly closed-loop, close to physical processes.
- **Challenge:** Bayesian optimisation beats an LLM at pure numeric search, and a judge may say so. The honest angle is that the LLM handles **constraints, operator notes and explanations** ("don't exceed 300 °C, the seals degrade"). Or use an LLM plus a simple optimiser and show the hybrid.

---

## 8. What's prepared vs. what waits for the event

**Done now (no prototype code)**
- README, this file, [BRIEF.md](BRIEF.md), [CLAUDE.md](CLAUDE.md) (conventions for Claude Code in the team repo)
- Git repo initialised, `.venv` with `anthropic`, `streamlit`, `pandas`, `python-dotenv`, plus `.env.example`

**You do before 16:00**
- [ ] Create an account at **console.anthropic.com**, add an API key to `.env`, and know which org the credits will go to
- [ ] Push this repo to GitHub (`gh repo create` from this folder) so it can become the team repo
- [ ] Charge the laptop and bring the charger
- [ ] Practise a 30-second pitch for team forming (top of BRIEF.md)

**At the event (deliberately not built yet)**
- Generating the synthetic data files from §3. This is the first task, and teammates may want to shape it.
- All code: `engine.py`, `llm.py`, `app.py`, `eval.py`
