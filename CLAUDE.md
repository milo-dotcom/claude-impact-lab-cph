# Hackathon repo

About 3 hours of build time. Prefer working end-to-end and ugly over polished and partial.

- Python in `.venv`, with dependencies in `requirements.txt`. The API key lives in `.env` as `ANTHROPIC_API_KEY`, loaded with `python-dotenv`. Never commit it.
- Models: `claude-sonnet-5-5` (fast, cheap) and `claude-opus-5-5` (hardest reasoning).
- Synthetic data only. No real company names or data.
- One owner per file to avoid merge conflicts. No frameworks unless the team agrees.
