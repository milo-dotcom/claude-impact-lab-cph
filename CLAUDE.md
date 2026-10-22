# Hackathon repo

About 3 hours of build time. Prefer working end-to-end and ugly over polished and partial.

- Python in `.venv`, with dependencies in `requirements.txt`. The API key lives in `.env` as `ANTHROPIC_API_KEY` (or `ANTHROPIC_PROFILE` for a Claude login, or `OPENAI_API_KEY` to run on OpenAI), loaded with `python-dotenv`; or no key and Sign in with ChatGPT (`chatgpt.py`). Never commit it.
- Models: `claude-sonnet-5-5` (fast, cheap) and `claude-opus-5-5` (hardest reasoning). On OpenAI: `gpt-6.1-sol` by default.
- Synthetic data only. No real company names or data.
- One owner per file to avoid merge conflicts. No frameworks unless the team agrees.
