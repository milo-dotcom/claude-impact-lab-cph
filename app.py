"""ParkRefund — customer flow: landing -> intake -> verdict -> letter -> payout.

Issue #2. Talks to the Claude layer only through the claims.py contract in CONCEPT.md.
Until claims.py (issue #8) lands, falls back to an inline mock so the flow can be built
and demoed now; the fallback is dropped automatically once claims.py is importable.
"""

import json
from pathlib import Path

import streamlit as st

try:
    from claims import CLAIM_KEYS, is_live, extract_ticket, assess_claim, draft_appeal, payout
except ImportError:
    CLAIM_KEYS = [
        "issuer_type", "issuer_name", "ticket_number", "plate", "date", "time", "location",
        "amount_dkk", "reason_on_ticket", "driver_story", "evidence",
    ]

    def is_live() -> bool:
        return False

    def extract_ticket(image_bytes: bytes, media_type: str) -> dict:
        return {
            "issuer_type": "private",
            "issuer_name": "NordPark ApS",
            "ticket_number": "NP-204817",
            "plate": "AB 12 345",
            "date": "2026-10-14",
            "time": "14:32",
            "location": "Testkøbing Storcenter, P-plads 3",
            "amount_dkk": 750,
            "reason_on_ticket": "Manglende synlig p-billet",
        }

    def assess_claim(claim: dict) -> dict:
        return {
            "success_probability": 72,
            "verdict": "strong",
            "summary": (
                "The entrance signage at this private lot is poorly documented, and the "
                "5-minute observation period looks like it wasn't respected."
            ),
            "grounds": [
                {
                    "title": "Observation period not respected",
                    "strength": "strong",
                    "explanation": "Ticket time is 2 minutes after the stated arrival time.",
                },
                {
                    "title": "Entrance signage unclear",
                    "strength": "medium",
                    "explanation": "No photo of entrance signage was provided; operators must prove it.",
                },
            ],
            "weaknesses": ["No photo of the parking disc or dashboard at the time of the ticket."],
            "evidence_to_collect": [
                "A photo of the entrance sign, taken today, for context.",
                "Any payment app receipt or timestamp, if one exists.",
            ],
            "route": "Complain to NordPark ApS in writing, then Parkeringsklagenævnet if rejected.",
            "deadline_note": "File within 10 days of the ticket to pause collection.",
            "recommend_filing": True,
        }

    def draft_appeal(claim: dict, assessment: dict, language: str = "da") -> str:
        if language == "da":
            return (
                f"Indsigelse mod kontrolafgift {claim.get('ticket_number', '')}\n\n"
                f"Til {claim.get('issuer_name', 'udsteder')},\n\n"
                f"Jeg gør hermed indsigelse mod kontrolafgiften udstedt {claim.get('date', '')} "
                f"kl. {claim.get('time', '')} ved {claim.get('location', '')} for køretøj med "
                f"nummerplade {claim.get('plate', '')}.\n\n"
                f"{assessment.get('summary', '')}\n\n"
                "Jeg anmoder om annullering af afgiften.\n\nMed venlig hilsen"
            )
        return (
            f"Appeal against control charge {claim.get('ticket_number', '')}\n\n"
            f"To {claim.get('issuer_name', 'the issuer')},\n\n"
            f"I am appealing the charge issued on {claim.get('date', '')} at "
            f"{claim.get('time', '')} at {claim.get('location', '')} for the vehicle with "
            f"plate {claim.get('plate', '')}.\n\n"
            f"{assessment.get('summary', '')}\n\n"
            "I request that the charge be annulled.\n\nKind regards"
        )

    def payout(amount_dkk: int) -> dict:
        fee = round(amount_dkk * 0.30)
        return {"refund": amount_dkk, "fee": fee, "you_get": amount_dkk - fee}


SAMPLE_CASES_PATH = Path(__file__).parent / "data" / "sample_cases.json"
FALLBACK_SAMPLE_CASES = [
    {
        "issuer_type": "private",
        "issuer_name": "NordPark ApS",
        "ticket_number": "NP-204817",
        "plate": "AB 12 345",
        "date": "2026-10-14",
        "time": "14:32",
        "location": "Testkøbing Storcenter, P-plads 3",
        "amount_dkk": 750,
        "reason_on_ticket": "Manglende synlig p-billet",
        "driver_story": "Parked, walked to the machine, and was back within two minutes with a ticket already on the windscreen.",
        "evidence": ["payment_receipt"],
    },
    {
        "issuer_type": "public",
        "issuer_name": "Testkøbing Kommune",
        "ticket_number": "TK-558120",
        "plate": "CD 67 890",
        "date": "2026-10-09",
        "time": "09:15",
        "location": "Rådhuspladsen, Testkøbing",
        "amount_dkk": 510,
        "reason_on_ticket": "P-skive ikke indstillet korrekt",
        "driver_story": "The disc was set, but to the wrong hour; I was unloading groceries for about 3 minutes.",
        "evidence": [],
    },
    {
        "issuer_type": "private",
        "issuer_name": "CityParkering A/S",
        "ticket_number": "CP-991102",
        "plate": "EF 24 680",
        "date": "2026-10-11",
        "time": "18:47",
        "location": "Havnefronten, Testkøbing",
        "amount_dkk": 900,
        "reason_on_ticket": "Parkering udenfor afmærket bås",
        "driver_story": "I parked inside the lines as far as I could tell; the lot was unlit and the markings were faded.",
        "evidence": ["signage_photo", "car_position_photo"],
    },
]

EVIDENCE_OPTIONS = {
    "signage_photo": "Photo of the sign",
    "payment_receipt": "Payment receipt (app or machine)",
    "car_position_photo": "Photo of the car's position",
    "permit": "Handicap / resident permit",
    "medical_note": "Medical or breakdown documentation",
}

STEPS = ["landing", "intake", "verdict", "letter", "payout"]
VERDICT_COLOR = {"strong": "🟢", "medium": "🟡", "weak": "🔴"}


def load_sample_cases() -> list[dict]:
    if SAMPLE_CASES_PATH.exists():
        return json.loads(SAMPLE_CASES_PATH.read_text(encoding="utf-8"))
    return FALLBACK_SAMPLE_CASES


def init_state():
    st.session_state.setdefault("step", "landing")
    st.session_state.setdefault("claim", {})
    st.session_state.setdefault("assessment", None)
    st.session_state.setdefault("letter", None)
    st.session_state.setdefault("language", "da")


def goto(step: str):
    st.session_state.step = step


def restart():
    for key in ("step", "claim", "assessment", "letter", "language"):
        st.session_state.pop(key, None)
    init_state()


def render_progress():
    if st.session_state.step == "landing":
        return
    labels = ["Intake", "Verdict", "Letter", "Payout"]
    current = STEPS.index(st.session_state.step)
    st.progress(current / (len(STEPS) - 1), text=" → ".join(
        f"**{l}**" if STEPS[i + 1] == st.session_state.step else l for i, l in enumerate(labels)
    ))


def render_landing():
    st.title("🅿️ ParkRefund")
    st.subheader("AirHelp for parking fines in Denmark")
    st.markdown(
        "Got a parking fine? Upload it, tell us what happened, and we'll give you an "
        "**honest** verdict on your odds of winning an appeal — a ready-to-send Danish "
        "letter if it's worth it, and we only take a cut **if the money comes back**."
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Typical fine", "510–1,020 kr")
    col2.metric("Success fee", "30%", help="Only charged if your appeal succeeds.")
    col3.metric("Cases reviewed (demo)", "248")
    st.caption("Demo statistics — illustrative, not a real win-rate claim.")
    if not is_live():
        st.info("Demo mode — no API key loaded, responses are scripted.", icon="🧪")
    st.divider()
    if st.button("Check my fine →", type="primary"):
        goto("intake")


def render_intake():
    st.header("Tell us about your fine")
    mode = st.radio("Start from", ["Upload a ticket photo", "Pick a sample case"], horizontal=True)

    prefill = dict(st.session_state.claim)

    if mode == "Upload a ticket photo":
        uploaded = st.file_uploader("Ticket photo", type=["png", "jpg", "jpeg"])
        if uploaded is not None:
            media_type = uploaded.type or "image/png"
            image_bytes = uploaded.getvalue()
            st.image(image_bytes, caption="Uploaded ticket", width=300)
            if st.button("Read ticket with Claude"):
                with st.spinner("Reading the ticket…"):
                    extracted = extract_ticket(image_bytes, media_type)
                prefill.update(extracted)
                st.session_state.claim = prefill
                st.success("Ticket read — check the fields below.")
    else:
        samples = load_sample_cases()
        labels = [f"{c['ticket_number']} — {c['issuer_name']} ({c['amount_dkk']} kr)" for c in samples]
        idx = st.selectbox("Sample case", range(len(samples)), format_func=lambda i: labels[i])
        if st.button("Use this case"):
            prefill.update(samples[idx])
            st.session_state.claim = prefill

    st.subheader("The details")
    with st.form("intake_form"):
        c = st.session_state.claim
        col1, col2 = st.columns(2)
        with col1:
            issuer_type = st.radio(
                "Who issued the fine?", ["private", "public"],
                index=0 if c.get("issuer_type", "private") == "private" else 1,
                format_func=lambda v: "Private operator" if v == "private" else "Kommune / police",
            )
            issuer_name = st.text_input("Issuer name", value=c.get("issuer_name", ""))
            ticket_number = st.text_input("Ticket number", value=c.get("ticket_number", ""))
            plate = st.text_input("Number plate", value=c.get("plate", ""))
            amount_dkk = st.number_input("Amount (DKK)", value=int(c.get("amount_dkk", 750)), step=10)
        with col2:
            date = st.text_input("Date (YYYY-MM-DD)", value=c.get("date", ""))
            time = st.text_input("Time (HH:MM)", value=c.get("time", ""))
            location = st.text_input("Location", value=c.get("location", ""))
            reason_on_ticket = st.text_input("Reason stated on the ticket", value=c.get("reason_on_ticket", ""))
        driver_story = st.text_area("What happened, in your own words?", value=c.get("driver_story", ""), height=120)
        evidence = st.multiselect(
            "Evidence you have",
            options=list(EVIDENCE_OPTIONS.keys()),
            default=c.get("evidence", []),
            format_func=lambda k: EVIDENCE_OPTIONS[k],
        )
        submitted = st.form_submit_button("Get my verdict →", type="primary")

    if submitted:
        claim = {
            "issuer_type": issuer_type, "issuer_name": issuer_name, "ticket_number": ticket_number,
            "plate": plate, "date": date, "time": time, "location": location,
            "amount_dkk": int(amount_dkk), "reason_on_ticket": reason_on_ticket,
            "driver_story": driver_story, "evidence": evidence,
        }
        st.session_state.claim = claim
        with st.spinner("Assessing your odds…"):
            st.session_state.assessment = assess_claim(claim)
        st.session_state.letter = None
        goto("verdict")

    st.button("← Back", on_click=goto, args=("landing",))


def render_verdict():
    st.header("Your verdict")
    a = st.session_state.assessment
    if a is None:
        st.warning("No assessment yet.")
        st.button("← Back to intake", on_click=goto, args=("intake",))
        return

    badge = VERDICT_COLOR.get(a["verdict"], "⚪")
    st.markdown(f"## {badge} {a['success_probability']}% chance of winning — **{a['verdict']}** case")
    st.write(a["summary"])

    if a["verdict"] == "weak" or not a.get("recommend_filing", True):
        st.error(
            "**We wouldn't take this case.** Based on what you've told us, the odds don't "
            "favour an appeal, and we don't want to charge you a fee for a case we don't believe in.",
            icon="🤝",
        )

    if a.get("grounds"):
        st.subheader("Grounds")
        for g in a["grounds"]:
            st.markdown(f"- {VERDICT_COLOR.get(g.get('strength'), '⚪')} **{g['title']}** — {g['explanation']}")

    if a.get("weaknesses"):
        st.subheader("Weaknesses")
        for w in a["weaknesses"]:
            st.markdown(f"- {w}")

    if a.get("evidence_to_collect"):
        st.subheader("Evidence that would raise your odds")
        for e in a["evidence_to_collect"]:
            st.markdown(f"- {e}")

    col1, col2 = st.columns(2)
    col1.markdown(f"**Route:** {a.get('route', '—')}")
    col2.markdown(f"**Deadline:** {a.get('deadline_note', '—')}")

    st.divider()
    col1, col2 = st.columns(2)
    col1.button("← Back to intake", on_click=goto, args=("intake",))
    if a.get("recommend_filing", True):
        col2.button("See my appeal letter →", type="primary", on_click=goto, args=("letter",))
    else:
        col2.button("Draft it anyway →", on_click=goto, args=("letter",))


def render_letter():
    st.header("Your appeal letter")
    language = st.radio(
        "Language", ["da", "en"], horizontal=True,
        index=0 if st.session_state.language == "da" else 1,
        format_func=lambda v: "Dansk" if v == "da" else "English",
    )
    if language != st.session_state.language or st.session_state.letter is None:
        st.session_state.language = language
        st.session_state.letter = draft_appeal(st.session_state.claim, st.session_state.assessment, language)

    st.text_area("Indsigelse / Appeal", value=st.session_state.letter, height=320)
    st.download_button(
        "Download letter (.txt)", data=st.session_state.letter,
        file_name=f"appeal_{st.session_state.claim.get('ticket_number', 'draft')}.txt",
    )

    st.divider()
    col1, col2 = st.columns(2)
    col1.button("← Back to verdict", on_click=goto, args=("verdict",))
    col2.button("See the payout →", type="primary", on_click=goto, args=("payout",))


def render_payout():
    st.header("If you win")
    claim = st.session_state.claim
    p = payout(int(claim.get("amount_dkk", 0)))
    col1, col2, col3 = st.columns(3)
    col1.metric("Refund", f"{p['refund']} kr")
    col2.metric("Our fee (30%)", f"{p['fee']} kr")
    col3.metric("You get", f"{p['you_get']} kr")
    st.caption("No win, no fee — you only pay this if the appeal succeeds.")

    st.divider()
    col1, col2 = st.columns(2)
    col1.button("← Back to letter", on_click=goto, args=("letter",))
    col2.button("Start a new case", on_click=restart)


RENDERERS = {
    "landing": render_landing,
    "intake": render_intake,
    "verdict": render_verdict,
    "letter": render_letter,
    "payout": render_payout,
}


def main():
    st.set_page_config(page_title="ParkRefund", page_icon="🅿️")
    init_state()
    render_progress()
    RENDERERS[st.session_state.step]()
    st.sidebar.caption("The model drafts and recommends; a human files.")
    st.sidebar.caption("Prototype — synthetic data, not legal advice.")


if __name__ == "__main__":
    main()
