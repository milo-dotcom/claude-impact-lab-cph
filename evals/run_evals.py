"""Calibration check: does claims.assess_claim agree with rules.RULES on labelled cases?

    .venv/bin/python evals/run_evals.py                 # Sonnet (default), or mock mode without a key
    PARKREFUND_MODEL=claude-opus-5-5 .venv/bin/python evals/run_evals.py
    .venv/bin/python evals/run_evals.py --limit 5 --json evals/last_run.json

One assess_claim call per case, no retries, no loops. ~20 cases costs pennies.
Without ANTHROPIC_API_KEY the keyword mock answers, which only proves the plumbing.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import claims  # noqa: E402
from rules import CATEGORIES  # noqa: E402

BANDS = {"strong": 2, "medium": 1, "weak": 0}
CASES_PATH = os.path.join(HERE, "cases.jsonl")


def load_cases(path=CASES_PATH):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run_case(case):
    claim = {k: case.get(k) for k in claims.CLAIM_KEYS}
    t0 = time.time()
    try:
        a = claims.assess_claim(claim)
        err = None
    except Exception as e:  # keep going; one failure should not sink the table
        a, err = {}, f"{type(e).__name__}: {e}"
    grounds = a.get("grounds") or []
    non_weak = [g for g in grounds if g.get("strength") != "weak"] or grounds
    got_cats = [g.get("category") for g in non_weak]
    expected_cat = case.get("expected_category")
    return {
        "id": case["id"], "label": case["label"],
        "expected": case["expected_verdict"], "got": a.get("verdict"), "prob": a.get("success_probability"),
        "recommend": a.get("recommend_filing"),
        "expected_category": expected_cat, "got_categories": got_cats,
        "category_hit": (expected_cat in got_cats) if expected_cat else None,
        "bad_categories": [c for c in got_cats if c not in CATEGORIES],
        "why": case["why"], "error": err, "seconds": round(time.time() - t0, 1),
    }


def summarize(rows):
    scored = [r for r in rows if r["got"] in BANDS]
    exact = sum(r["got"] == r["expected"] for r in scored)
    near = sum(abs(BANDS[r["got"]] - BANDS[r["expected"]]) <= 1 for r in scored)
    # "Honest" check: weak cases must not be recommended, strong ones must be.
    weak = [r for r in scored if r["expected"] == "weak"]
    strong = [r for r in scored if r["expected"] == "strong"]
    declines = sum(r["recommend"] is False for r in weak)
    files = sum(r["recommend"] is True for r in strong)
    cats = [r for r in scored if r["category_hit"] is not None]
    return {
        "cases": len(rows), "errors": sum(1 for r in rows if r["error"]),
        "verdict_exact": (exact, len(scored)), "verdict_within_one_band": (near, len(scored)),
        "weak_declined": (declines, len(weak)), "strong_recommended": (files, len(strong)),
        "category_hit": (sum(r["category_hit"] for r in cats), len(cats)),
        "invalid_categories": sum(len(r["bad_categories"]) for r in rows),
    }


def pct(pair):
    n, d = pair
    return f"{n}/{d}" + (f" ({100 * n / d:.0f}%)" if d else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", default=CASES_PATH)
    ap.add_argument("--limit", type=int, default=0, help="only run the first N cases")
    ap.add_argument("--json", help="write per-case results + summary to this path")
    args = ap.parse_args()

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]
    mode = "LIVE" if claims.is_live() else "MOCK"
    model = os.getenv("PARKREFUND_MODEL", "claude-sonnet-5-5")
    print(f"ParkRefund evals  mode={mode}  model={model if mode == 'LIVE' else '-'}  cases={len(cases)}")
    if mode == "MOCK":
        print("No ANTHROPIC_API_KEY: this scores the keyword mock, not the model. Plumbing check only.")
    print()

    rows = []
    print(f"{'id':<4} {'expected':<8} {'got':<8} {'prob':>4}  {'file?':<5} {'cat':<3}  label")
    for case in cases:
        r = run_case(case)
        rows.append(r)
        ok = "OK " if r["got"] == r["expected"] else "MISS"
        cat = "-" if r["category_hit"] is None else ("y" if r["category_hit"] else "n")
        rec = {True: "yes", False: "no", None: "?"}[r["recommend"]]
        print(f"{r['id']:<4} {r['expected']:<8} {str(r['got']):<8} {str(r['prob']):>4}  {rec:<5} {cat:<3}  "
              f"{ok} {r['label']}" + (f"  [{r['error']}]" if r["error"] else ""))

    s = summarize(rows)
    print()
    print(f"verdict exact          {pct(s['verdict_exact'])}")
    print(f"within one band        {pct(s['verdict_within_one_band'])}")
    print(f"weak -> not recommended {pct(s['weak_declined'])}   (the 'we say no' promise)")
    print(f"strong -> recommended  {pct(s['strong_recommended'])}")
    print(f"expected category hit  {pct(s['category_hit'])}")
    if s["invalid_categories"]:
        print(f"!! {s['invalid_categories']} ground(s) with a category outside rules.CATEGORIES")
    if s["errors"]:
        print(f"!! {s['errors']} case(s) errored")

    misses = [r for r in rows if r["got"] != r["expected"]]
    if misses:
        print("\nMisses:")
        for r in misses:
            print(f"- {r['id']} expected {r['expected']}, got {r['got']} ({r['prob']}%), "
                  f"categories {r['got_categories']}\n    {r['why']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"mode": mode, "model": model, "summary": s, "rows": rows}, fh, ensure_ascii=False, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
