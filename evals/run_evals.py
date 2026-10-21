"""Calibration check: does claims.assess_claim agree with rules.py on evals/cases.jsonl?

    .venv/bin/python evals/run_evals.py           # live (Sonnet) if a key is set
    .venv/bin/python evals/run_evals.py --mock    # force mock mode
    PARKREFUND_MODEL=claude-opus-5-5 .venv/bin/python evals/run_evals.py
"""
import json
import os
import sys

if "--mock" in sys.argv:
    os.environ["ANTHROPIC_API_KEY"] = ""  # set-but-empty wins over .env, so claims.is_live() is False
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import claims  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
META = {"label", "expected_verdict", "expected_category", "why"}


def main():
    cases = [json.loads(l) for l in open(os.path.join(HERE, "cases.jsonl"), encoding="utf-8") if l.strip()]
    print(f"mode={'LIVE ' + claims._model() if claims.is_live() else 'MOCK'}  cases={len(cases)}\n")
    print(f"{'case':42} {'exp':7} {'got':7} {'p%':>3}  {'top category':34} ok")
    hits = cat_hits = 0
    misses = []
    for c in cases:
        claim = {k: v for k, v in c.items() if k not in META}
        a = claims.assess_claim(claim)
        top = next((g for g in a["grounds"] if g["strength"] != "weak"), a["grounds"][0] if a["grounds"] else None)
        cat = top["category"] if top else "-"
        ok = a["verdict"] == c["expected_verdict"]
        hits += ok
        cat_hits += cat == c["expected_category"]
        print(f"{c['label'][:42]:42} {c['expected_verdict']:7} {a['verdict']:7} {a['success_probability']:3}  {cat[:34]:34} {'✓' if ok else '✗'}")
        if not ok:
            misses.append((c, a))
    print(f"\nverdict accuracy {hits}/{len(cases)}   category match {cat_hits}/{len(cases)}")
    for c, a in misses:
        print(f"\nMISS {c['label']}: expected {c['expected_verdict']} ({c['why']}), got {a['verdict']} {a['success_probability']}%")
        print("  ", a["summary"])
    return 0 if hits == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
