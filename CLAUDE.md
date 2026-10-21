# Exception Manager: hackathon repo

3-hour build. Problem, scope and data spec: README.md and PREP.md.

- **Claude reads, Python computes.** LLM calls only extract signals from text and write explanations and recommendations. All dates, critical path, float and € math live in `engine.py`.
- Validate every extracted signal: `po_id` must exist and `quote` must be a substring of the source text. Drop it otherwise.
- Extraction uses tool use with a JSON schema. Cache results to `signals.json`, and the demo runs from the cache.
- Models: `claude-sonnet-5-5` (extraction), `claude-opus-5-5` (recommendations). Key in `.env` as `ANTHROPIC_API_KEY`.
- Synthetic data only, in `data/`. No real company names or data.
- One owner per file: `engine.py`, `llm.py`, `app.py`, `eval.py`. No frameworks (no LangChain, vector DB or agent libs).
- Prefer working end-to-end and ugly over polished and partial.
