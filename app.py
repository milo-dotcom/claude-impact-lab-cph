"""ParkRefund customer flow: landing → intake → assessment → letter → payout.

Run: .venv/bin/streamlit run app.py

Talks to claims.py through the contract in CONCEPT.md. Until claims.py and
data/sample_cases.json land (issue #8), an inline stand-in with the same contract
keeps the page running in mock mode; it is picked automatically only when
`import claims` fails, and can be deleted once #8 is on main.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

try:
    from rules import SUCCESS_FEE
except ImportError:
    SUCCESS_FEE = 0.30

CLAIM_KEYS = ["issuer_type", "issuer_name", "ticket_number", "plate", "date", "time", "location",
              "amount_dkk", "reason_on_ticket", "driver_story", "evidence"]
EVIDENCE_OPTIONS = ["sign photos", "payment receipt", "breakdown receipt", "witness", "permit"]
MODEL_NAME = os.environ.get("PARKREFUND_MODEL", "claude-sonnet-5-5")
SAMPLE_CASES_PATH = Path(__file__).parent / "data" / "sample_cases.json"

# ---------------------------------------------------------------------------
# Stand-in for claims.py (issue #8). Same contract, deterministic, no API calls.
# ---------------------------------------------------------------------------

_WIN = [  # (keywords in the story, points, ground title, explanation)
    (("hidden", "not visible", "no sign", "obscured", "covered by", "covered in", "behind a"), 25,
     "Signage not visible from the car",
     "A restriction only binds if its sign can be seen from where the car was parked."),
    (("receipt", "paid", "payment", "betalt"), 20,
     "Payment was made",
     "A receipt whose timestamp covers the ticket time is the strongest paper evidence."),
    (("typo", "wrong digit", "instead of", "mistyped"), 10,
     "Plate typo on a valid payment",
     "Issuers routinely refund on goodwill when the receipt shows a near-identical plate."),
    (("unload", "loading", "boxes", "carry"), 15,
     "Loading / unloading, not parking",
     "Stopping up to ~3 minutes to load is 'standsning', allowed where only parking is prohibited."),
    (("just arrived", "walking to the machine", "within two minutes", "within 2 minutes"), 15,
     "Observation period not respected",
     "Operators should wait ~5 minutes before ticketing a car without a visible ticket."),
    (("breakdown", "towed", "hospital", "ambulance", "medical"), 15,
     "Breakdown or medical emergency",
     "Documented emergencies are accepted when the paperwork matches the time."),
    (("permit was", "my permit", "resident permit", "tilladelse"), 15,
     "Valid permit displayed",
     "A visible, valid permit defeats the fine outright."),
    (("wrong plate", "wrong date", "no photo", "wrong location"), 15,
     "Formally defective fine",
     "A fine with wrong details or no photo documentation is routinely annulled."),
]
_LOSE = [  # (keywords, points, weakness)
    (("handicap", "disabled bay"), -35, "Parked in a handicap bay — annulled only with a valid permit."),
    (("fire lane", "brandvej"), -30, "Parked in a fire lane — serious offence, rarely overturned."),
    (("pavement", "sidewalk", "fortov", "driveway"), -20, "Parked on a pavement or across a driveway."),
    (("didn't see", "did not see", "didn't notice"), -10, "'Didn't see the sign' rarely succeeds when the sign is standard."),
    (("few minutes over", "forgot", "running late", "late for"), -10, "Being late or a few minutes over is not a ground."),
    (("wrong zone", "wrong area"), -15, "Paid for the wrong zone — treated as not paid."),
    (("everyone", "didn't know"), -10, "'Didn't know the rules' is not a ground."),
]
_EVIDENCE_POINTS = {"sign photos": 10, "payment receipt": 10, "breakdown receipt": 10, "permit": 10, "witness": 5}


def _fb_is_live() -> bool:
    return False


def _fb_extract_ticket(image_bytes: bytes, media_type: str) -> dict:
    return {"issuer_type": "private", "issuer_name": "NordPark ApS", "ticket_number": "NP-2026-004512",
            "plate": "AB 12 345", "date": "2026-10-03", "time": "14:22",
            "location": "Havnegade 12, Testkøbing", "amount_dkk": 790,
            "reason_on_ticket": "Parkeret uden gyldig billet"}


def _fb_assess_claim(claim: dict) -> dict:
    story = (claim.get("driver_story") or "").lower()
    evidence = set(claim.get("evidence") or [])
    private = claim.get("issuer_type") == "private"
    issuer = claim.get("issuer_name") or ("the operator" if private else "the kommune")

    score, grounds, weaknesses, collect = 30, [], [], []
    for kws, pts, title, why in _WIN:
        if any(k in story for k in kws):
            score += pts
            grounds.append({"title": title, "strength": "strong" if pts >= 20 else "medium", "explanation": why})
    for kws, pts, weak in _LOSE:
        if any(k in story for k in kws):
            score += pts
            weaknesses.append(weak)
    score += sum(_EVIDENCE_POINTS.get(e, 0) for e in evidence)

    titles = {g["title"] for g in grounds}
    if "Signage not visible from the car" in titles and "sign photos" not in evidence:
        weaknesses.append("No photos of the signage — the issuer's photos will be the only record.")
        collect.append("Photos of the sign and of the car's position, taken the same day")
    if "Payment was made" in titles and "payment receipt" not in evidence:
        weaknesses.append("No receipt attached — the payment claim can't be verified.")
        collect.append("Payment receipt or app screenshot showing the timestamp")
    if not evidence:
        weaknesses.append("No evidence ticked — a story alone rarely wins.")
    if not grounds:
        weaknesses.append("The story doesn't match any ground in the rulebook.")
    collect += ["The fine itself, both sides", "Any permit, receipt or correspondence you already have"]

    prob = max(5, min(95, score))
    verdict = "strong" if prob >= 65 else "medium" if prob >= 40 else "weak"
    lead = grounds[0]["title"].lower() if grounds else "no recognised ground"
    summary = {
        "strong": f"Strong case: {lead}. Issuers usually annul on this ground when the evidence is attached.",
        "medium": f"Borderline: {lead} helps, but the outcome will turn on the evidence and on the issuer's photos.",
        "weak": f"Weak case: {lead}. On the rulebook this fine would most likely stand.",
    }[verdict]
    if private:
        route = (f"Written complaint to {issuer} first. If rejected: Parkeringsklagenævnet "
                 f"(fee ~175 DKK, refunded if you win).")
        deadline = ("Appeal within the deadline printed on the ticket; the fine is paused while it is handled. "
                    "Parkeringsklagenævnet: within ~4 weeks of the operator's rejection.")
    else:
        route = f"Written objection ('indsigelse') to {issuer}'s parkeringskontor. No fee. If rejected: Fogedretten."
        deadline = "Appeal in writing within the deadline on the ticket (commonly 10 days); the fine is paused meanwhile."
    return {"success_probability": prob, "verdict": verdict, "summary": summary, "grounds": grounds,
            "weaknesses": weaknesses, "evidence_to_collect": collect, "route": route,
            "deadline_note": deadline, "recommend_filing": prob >= 40}


def _fb_draft_appeal(claim: dict, assessment: dict, language: str = "da") -> str:
    c = {k: claim.get(k) or "—" for k in CLAIM_KEYS}
    private = claim.get("issuer_type") == "private"
    attached = ", ".join(claim.get("evidence") or []) or "—"
    grounds = assessment.get("grounds") or []
    if language == "da":
        kind = "kontrolafgift" if private else "parkeringsafgift"
        lines = [f"Til {c['issuer_name']}", "", f"Indsigelse mod {kind} nr. {c['ticket_number']}", "",
                 f"Registreringsnummer: {c['plate']}", f"Dato og tidspunkt: {c['date']} kl. {c['time']}",
                 f"Sted: {c['location']}", f"Begrundelse på afgiften: {c['reason_on_ticket']}", "",
                 "Jeg gør hermed indsigelse mod ovennævnte afgift.", "", str(c["driver_story"]), "",
                 "Jeg henviser til følgende forhold:"]
        lines += [f"- {g['title']}: {g['explanation']}" for g in grounds] or ["- Se beskrivelsen ovenfor."]
        lines += ["", f"Vedlagt: {attached}", "",
                  "På den baggrund anmoder jeg om, at afgiften annulleres."]
        if private:
            lines.append("Såfremt indsigelsen afvises, forbeholder jeg mig at indbringe sagen for Parkeringsklagenævnet.")
        lines += ["", "Med venlig hilsen", "[Navn]", "[Adresse]", "[E-mail / telefon]"]
    else:
        kind = "control fee" if private else "parking fine"
        lines = [f"To {c['issuer_name']}", "", f"Objection to {kind} no. {c['ticket_number']}", "",
                 f"Registration: {c['plate']}", f"Date and time: {c['date']} at {c['time']}",
                 f"Location: {c['location']}", f"Reason stated on the ticket: {c['reason_on_ticket']}", "",
                 "I hereby object to the above fee.", "", str(c["driver_story"]), "", "I rely on the following:"]
        lines += [f"- {g['title']}: {g['explanation']}" for g in grounds] or ["- See the account above."]
        lines += ["", f"Attached: {attached}", "", "On this basis I request that the fee be annulled."]
        if private:
            lines.append("Should the objection be rejected, I reserve the right to bring the case before Parkeringsklagenævnet.")
        lines += ["", "Kind regards", "[Name]", "[Address]", "[E-mail / phone]"]
    return "\n".join(lines)


def _fb_payout(amount_dkk: int) -> dict:
    fee = round(amount_dkk * SUCCESS_FEE)
    return {"refund": amount_dkk, "fee": fee, "you_get": amount_dkk - fee}


try:
    import claims
    USING_FALLBACK = False
except ImportError:
    claims = SimpleNamespace(CLAIM_KEYS=CLAIM_KEYS, is_live=_fb_is_live, extract_ticket=_fb_extract_ticket,
                             assess_claim=_fb_assess_claim, draft_appeal=_fb_draft_appeal, payout=_fb_payout)
    USING_FALLBACK = True

# ---------------------------------------------------------------------------
# Sample cases: data/sample_cases.json from #8 when present, else these.
# ---------------------------------------------------------------------------

BUILTIN_SAMPLES = [
    {"label": "Paid in the app, typo in the plate (private)",
     "issuer_type": "private", "issuer_name": "NordPark ApS", "ticket_number": "NP-2026-004512",
     "plate": "AB 12 345", "date": "2026-10-03", "time": "14:22", "location": "Havnegade 12, Testkøbing",
     "amount_dkk": 790, "reason_on_ticket": "Parkeret uden gyldig billet",
     "driver_story": "I paid for two hours in the NordPark app at 14:05 but typed AB 12 435 instead of "
                     "AB 12 345. The receipt shows the payment covered 14:05–16:05 in the same car park. "
                     "I have the receipt and a screenshot from the app.",
     "evidence": ["payment receipt"]},
    {"label": "Sign hidden behind a parked van (kommune)",
     "issuer_type": "public", "issuer_name": "Testkøbing Kommune", "ticket_number": "TK-7781920",
     "plate": "CD 34 567", "date": "2026-09-28", "time": "09:40", "location": "Søndergade 4, Testkøbing",
     "amount_dkk": 510, "reason_on_ticket": "Parkering i strid med skiltning",
     "driver_story": "The only sign for the time restriction was completely hidden behind a delivery van "
                     "when I parked. I took photos of the van and the sign right after I found the ticket. "
                     "No other sign was visible from where I parked.",
     "evidence": ["sign photos", "witness"]},
    {"label": "Unloading for three minutes in a no-parking street (kommune)",
     "issuer_type": "public", "issuer_name": "Testkøbing Kommune", "ticket_number": "TK-7790331",
     "plate": "EF 56 789", "date": "2026-10-10", "time": "17:05", "location": "Nørregade 22, Testkøbing",
     "amount_dkk": 510, "reason_on_ticket": "Parkering forbudt",
     "driver_story": "I stopped for about three minutes to carry two boxes into the shop. The sign says "
                     "parking forbidden, not stopping. The shop owner saw me unloading.",
     "evidence": ["witness"]},
    {"label": "Handicap bay, running late (private) — the honest 'no'",
     "issuer_type": "private", "issuer_name": "CityParkering A/S", "ticket_number": "CP-33-118877",
     "plate": "GH 78 901", "date": "2026-10-14", "time": "08:12", "location": "Centerparkering, Testkøbing",
     "amount_dkk": 900, "reason_on_ticket": "Parkeret på handicapplads uden tilladelse",
     "driver_story": "I was late for a job interview and the handicap bay was the only free spot. I was "
                     "gone for 15 minutes at most and nobody needed the space. 900 DKK is a lot of money for me.",
     "evidence": []},
]


def load_samples() -> list[dict]:
    if SAMPLE_CASES_PATH.exists():
        try:
            data = json.loads(SAMPLE_CASES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except (OSError, ValueError):
            pass
    return BUILTIN_SAMPLES


def sample_label(case: dict) -> str:
    return case.get("label") or f"{case.get('issuer_name', '?')} — {case.get('reason_on_ticket', '?')}"


SAMPLES = load_samples()
SAMPLE_LABELS = [sample_label(s) for s in SAMPLES]

# ---------------------------------------------------------------------------
# Session state. Form widgets are keyed "claim_<field>" so a sample case or an
# extracted ticket can be written straight into them from a callback.
# ---------------------------------------------------------------------------


def field(key: str) -> str:
    return "claim_" + key


def put_claim(claim: dict) -> None:
    for k in claims.CLAIM_KEYS:
        if claim.get(k) not in (None, ""):
            st.session_state[field(k)] = claim[k]


def read_claim() -> dict:
    claim = {k: st.session_state.get(field(k)) for k in claims.CLAIM_KEYS}
    claim["amount_dkk"] = int(claim["amount_dkk"] or 0)
    claim["evidence"] = list(claim["evidence"] or [])
    return claim


def clear_results() -> None:
    st.session_state.assessment = None
    st.session_state.assessed_claim = None
    st.session_state.letter = None


def init_state() -> None:
    if st.session_state.get("booted"):
        return
    st.session_state.booted = True
    for k in claims.CLAIM_KEYS:
        st.session_state[field(k)] = [] if k == "evidence" else 0 if k == "amount_dkk" else ""
    st.session_state[field("issuer_type")] = "private"
    put_claim(SAMPLES[0])
    st.session_state.sample_pick = SAMPLE_LABELS[0]
    st.session_state.notice = None
    st.session_state.letter_rev = 0
    clear_results()


def normalize_fields() -> None:
    """Coerce whatever a sample file or extract_ticket wrote into what the widgets accept."""
    if st.session_state[field("issuer_type")] not in ("public", "private"):
        st.session_state[field("issuer_type")] = "private"
    try:
        st.session_state[field("amount_dkk")] = int(st.session_state[field("amount_dkk")] or 0)
    except (TypeError, ValueError):
        st.session_state[field("amount_dkk")] = 0
    ev = st.session_state[field("evidence")]
    st.session_state[field("evidence")] = [str(e) for e in (ev if isinstance(ev, list) else [ev] if ev else [])]
    for k in ("issuer_name", "ticket_number", "plate", "date", "time", "location", "reason_on_ticket",
              "driver_story"):
        v = st.session_state[field(k)]
        st.session_state[field(k)] = "" if v is None else str(v)


def on_pick_sample() -> None:
    label = st.session_state.sample_pick
    for case in SAMPLES:
        if sample_label(case) == label:
            put_claim(case)
            clear_results()
            st.session_state.notice = ("info", f"Loaded sample case: {label}")
            return


def on_upload() -> None:
    up = st.session_state.ticket_upload
    if up is None:
        return
    try:
        extracted = claims.extract_ticket(up.getvalue(), up.type or "image/jpeg")
    except Exception as e:  # claims.py raises RuntimeError on API trouble
        st.session_state.notice = ("error", f"Could not read the ticket photo: {e}")
        return
    put_claim(extracted)
    clear_results()
    st.session_state.sample_pick = None
    filled = [k for k in claims.CLAIM_KEYS if extracted.get(k) not in (None, "", [])]
    note = f"Read {len(filled)} fields from the ticket photo — check them below."
    if not claims.is_live():
        note += " (Mock mode: the values are illustrative, not read from your image.)"
    st.session_state.notice = ("success", note)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.set_page_config(page_title="ParkRefund", page_icon="🅿️", layout="centered")
init_state()
normalize_fields()

with st.sidebar:
    st.header("ParkRefund")
    live = claims.is_live()
    st.markdown(f"**Mode:** {'🟢 LIVE' if live else '🟠 MOCK'}")
    st.markdown(f"**Model:** `{MODEL_NAME}`")
    if USING_FALLBACK:
        st.caption("claims.py not found — running the inline stand-in (issue #8).")
    elif not live:
        st.caption("No ANTHROPIC_API_KEY — claims.py is returning deterministic mock output.")
    st.divider()
    st.caption("The model drafts and recommends; a human files.")
    st.caption("Synthetic demo data. Not legal advice.")

# 1 · Hero
st.title("Parkeringsbøde? Vi henter dine penge hjem.")
st.subheader("No win, no fee.")
c1, c2, c3 = st.columns(3)
c1.metric("Cases handled", "12,480")
c2.metric("Win rate", "71 %")
c3.metric("DKK refunded", "6.2 M")
st.caption("Demo numbers — synthetic data.")

# 2 · Intake
st.header("1 · Your ticket")
tab_upload, tab_sample = st.tabs(["Upload ticket photo", "Pick a sample case"])
with tab_upload:
    st.file_uploader("Photo of the fine (jpeg / png / webp)", type=["jpg", "jpeg", "png", "webp"],
                     key="ticket_upload", on_change=on_upload)
with tab_sample:
    st.selectbox("Sample case", SAMPLE_LABELS, key="sample_pick", index=None,
                 placeholder="Choose a case…", on_change=on_pick_sample)
if st.session_state.notice:
    kind, text = st.session_state.notice
    getattr(st, kind)(text)

st.header("2 · What happened")
col = st.columns(2)
col[0].radio("Who issued it?", ["public", "private"], key=field("issuer_type"), horizontal=True,
             format_func=lambda v: {"public": "Kommune (public)", "private": "Private operator"}[v])
col[1].number_input("Amount (DKK)", min_value=0, max_value=5000, step=10, key=field("amount_dkk"))
col = st.columns(2)
col[0].text_input("Issuer name", key=field("issuer_name"))
col[1].text_input("Ticket number", key=field("ticket_number"))
col = st.columns(3)
col[0].text_input("Plate", key=field("plate"))
col[1].text_input("Date (YYYY-MM-DD)", key=field("date"))
col[2].text_input("Time (HH:MM)", key=field("time"))
st.text_input("Location", key=field("location"))
st.text_input("Reason on the ticket", key=field("reason_on_ticket"))
st.text_area("What happened? Be specific: times, what you saw, what you did.", key=field("driver_story"),
             height=140)
evidence_options = EVIDENCE_OPTIONS + [e for e in st.session_state[field("evidence")] if e not in EVIDENCE_OPTIONS]
st.multiselect("Evidence you have", evidence_options, key=field("evidence"))

# 3 · Assessment
st.header("3 · Your odds")
if st.button("Check my case", type="primary", use_container_width=True):
    claim = read_claim()
    try:
        with st.spinner("Reading the rulebook…"):
            assessment = claims.assess_claim(claim)
        st.session_state.assessment = assessment
        st.session_state.assessed_claim = claim
        st.session_state.letter = None
        st.session_state.notice = None
    except Exception as e:  # claims.py raises RuntimeError on API trouble
        st.error(f"Assessment failed: {e}")

a = st.session_state.assessment
if a:
    prob = int(a.get("success_probability", 0))
    verdict = str(a.get("verdict", "weak")).lower()
    colour = {"strong": "#1b8a5a", "medium": "#c77d00", "weak": "#b3261e"}.get(verdict, "#666")
    c1, c2 = st.columns([1, 2])
    c1.metric("Chance of winning", f"{prob} %")
    c2.markdown(
        f"<div style='margin-top:14px;display:inline-block;padding:8px 18px;border-radius:999px;"
        f"background:{colour};color:white;font-weight:700;font-size:1.1rem'>{verdict.upper()}</div>",
        unsafe_allow_html=True)
    if a.get("recommend_filing"):
        st.success("We'd take this case. Below is what carries it, and what would make it stronger.")
    else:
        st.error("We wouldn't take this case — here's why.")
    st.write(a.get("summary", ""))

    if a.get("grounds"):
        st.subheader("What helps you")
        for g in a["grounds"]:
            with st.container(border=True):
                st.markdown(f"**{g.get('title', '')}** · {str(g.get('strength', '')).lower()}")
                st.write(g.get("explanation", ""))
    if a.get("weaknesses"):
        st.subheader("What works against you")
        for w in a["weaknesses"]:
            st.markdown(f"- {w}")
    if a.get("evidence_to_collect"):
        st.subheader("Evidence that would raise the odds")
        for e in a["evidence_to_collect"]:
            st.markdown(f"- {e}")
    with st.container(border=True):
        st.markdown(f"**Where to appeal:** {a.get('route', '')}")
        st.markdown(f"**Deadline:** {a.get('deadline_note', '')}")

    # 4 · Letter
    st.header("4 · Your appeal letter")
    lang = st.radio("Language", ["da", "en"], horizontal=True, key="letter_lang",
                    format_func=lambda v: {"da": "Dansk", "en": "English"}[v])
    if st.button("Draft my appeal", use_container_width=True):
        try:
            with st.spinner("Drafting…"):
                st.session_state.letter = claims.draft_appeal(st.session_state.assessed_claim, a, language=lang)
            st.session_state.letter_rev += 1
        except Exception as e:  # claims.py raises RuntimeError on API trouble
            st.error(f"Drafting failed: {e}")
    if st.session_state.letter:
        text = st.text_area("Read it, edit it, sign it", st.session_state.letter, height=420,
                            key=f"letter_text_{st.session_state.letter_rev}")
        ticket_no = (st.session_state.assessed_claim or {}).get("ticket_number") or "appeal"
        st.download_button("Download as .txt", text, file_name=f"indsigelse_{ticket_no}.txt", mime="text/plain")
        st.caption("The model drafts and recommends; a human files.")

    # 5 · Payout
    st.header("5 · If we win")
    amount = int((st.session_state.assessed_claim or {}).get("amount_dkk") or 0)
    pay = claims.payout(amount)
    fee_pct = round(100 * pay["fee"] / pay["refund"]) if pay.get("refund") else round(100 * SUCCESS_FEE)
    c1, c2, c3 = st.columns(3)
    c1.metric("Refund", f"{pay['refund']:,} DKK")
    c2.metric(f"Our fee ({fee_pct} %)", f"{pay['fee']:,} DKK")
    c3.metric("You get", f"{pay['you_get']:,} DKK")
    st.caption("You pay nothing if we lose.")
