"""Generate synthetic data/pipeline.json for the ops dashboard. Synthetic only."""
import json, random
from datetime import datetime, timedelta
import rules

random.seed(42)
NOW = datetime(2026, 10, 21, 12, 0)
PRIVATE = ["NordPark ApS", "CityParkering A/S", "Havneparkering ApS"]
cats = rules.CATEGORIES
W = {"Skiltning": 8, "Digital registrering": 6, "P-billet": 5, "Standsning og observation": 5}
weights = [W.get(c, 1) for c in cats]

rows = []
for i in range(200):
    private = random.random() < 0.8
    issuer = random.choice(PRIVATE) if private else "Testkøbing Kommune"
    amount = random.randint(650, 900) // 50 * 50 if private else random.choice([510, 1020])
    r = random.random()
    prob = random.randint(65, 95) if r < 0.38 else random.randint(40, 64) if r < 0.72 else random.randint(5, 39)
    verdict = "strong" if prob >= 65 else "medium" if prob >= 40 else "weak"
    rec = "file" if prob >= 50 else "decline"
    dec = rec
    if random.random() < 0.08:
        dec = "decline" if rec == "file" else "file"
        override = True
    else:
        override = False
    if dec == "decline":
        status = random.choice(["withdrawn", "new"]) if random.random() < 0.7 else "new"
    else:
        status = "filed"
        if random.random() < 0.9:
            status = "won" if random.random() < 0.15 + 0.8 * prob / 100 else "lost"
    if random.random() < 0.15 and status == "withdrawn":
        status = "new"
    minutes = random.randint(12, 25) if 40 <= prob <= 60 else random.randint(2, 6)
    rows.append({
        "id": f"PR-{1001+i}",
        "received_at": (NOW - timedelta(minutes=random.randint(0, 30 * 24 * 60))).isoformat(timespec="minutes"),
        "issuer_type": "private" if private else "public",
        "issuer_name": issuer, "amount_dkk": amount,
        "category": random.choices(cats, weights)[0],
        "model_probability": prob, "model_verdict": verdict,
        "human_decision": "override" if override else dec,
        "status": status, "minutes_human_review": minutes,
    })
rows.sort(key=lambda x: x["received_at"], reverse=True)
json.dump(rows, open("data/pipeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rows), "rows")
