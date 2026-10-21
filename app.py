"""ParkRefund customer flow: landing → intake → assessment → letter → payout.

Run: .venv/bin/streamlit run app.py

Talks to claims.py (issue #8) through the contract in CONCEPT.md, and to evidence.py
(issue #4) for the sign / car-position photo check. No .env → both run in mock mode.
"""

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import claims
import evidence
from rules import SUCCESS_FEE

load_dotenv()

EVIDENCE_OPTIONS = ["sign photos", "payment receipt", "breakdown receipt", "witness", "permit"]
PHOTO_TYPES = ["jpg", "jpeg", "png", "webp"]
MAX_EVIDENCE_PHOTOS = 5
MODEL_NAME = os.environ.get("PARKREFUND_MODEL", "claude-sonnet-5-5")
SAMPLE_CASES_PATH = Path(__file__).parent / "data" / "sample_cases.json"


def load_samples() -> list[dict]:
    try:
        data = json.loads(SAMPLE_CASES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def sample_label(case: dict) -> str:
    return case.get("label") or f"{case.get('issuer_name', '?')} — {case.get('reason_on_ticket', '?')}"


SAMPLES = load_samples()
SAMPLE_LABELS = [sample_label(s) for s in SAMPLES]

# ---------------------------------------------------------------------------
# Session state. Form widgets are keyed "claim_<field>" so a sample case, an
# extracted ticket or the evidence check can write straight into them from a
# callback (widget state can only be set before the widget renders).
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
    st.session_state.evidence_check = None


def init_state() -> None:
    if st.session_state.get("booted"):
        return
    st.session_state.booted = True
    for k in claims.CLAIM_KEYS:
        st.session_state[field(k)] = [] if k == "evidence" else 0 if k == "amount_dkk" else ""
    st.session_state[field("issuer_type")] = "private"
    st.session_state.sample_pick = None
    if SAMPLES:
        put_claim(SAMPLES[0])
        st.session_state.sample_pick = SAMPLE_LABELS[0]
    st.session_state.notice = None
    st.session_state.letter_rev = 0
    clear_results()


def normalize_fields() -> None:
    """Coerce whatever the sample file or extract_ticket wrote into what the widgets accept."""
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


def run_assessment() -> str | None:
    """Assess the current form; returns an error message or None."""
    claim = read_claim()
    try:
        assessment = claims.assess_claim(claim)
    except Exception as e:  # claims.py raises RuntimeError on API trouble
        return f"Assessment failed: {e}"
    st.session_state.assessment = assessment
    st.session_state.assessed_claim = claim
    st.session_state.letter = None
    return None


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


def on_apply_evidence() -> None:
    """Fold the photo check into the story + evidence list, then re-assess."""
    ec = st.session_state.evidence_check or {}
    addition = (ec.get("suggested_additions_to_story") or "").strip()
    story = st.session_state[field("driver_story")].strip()
    if addition and addition not in story:
        st.session_state[field("driver_story")] = f"{story}\n\n{addition}".strip()
    ev = list(st.session_state[field("evidence")])
    if "sign photos" not in ev:
        ev.append("sign photos")
    st.session_state[field("evidence")] = ev
    err = run_assessment()
    st.session_state.notice = ("error", err) if err else ("success", "Photo findings added to your story — odds re-checked below.")


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
    if not live:
        st.caption("No ANTHROPIC_API_KEY — deterministic mock output from claims.py / evidence.py.")
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
    st.file_uploader("Photo of the fine (jpeg / png / webp)", type=PHOTO_TYPES,
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

with st.expander("Upload evidence photos — the sign, where the car stood"):
    photos = (st.file_uploader(f"Photos (jpeg / png / webp, up to {MAX_EVIDENCE_PHOTOS})", type=PHOTO_TYPES,
                               accept_multiple_files=True, key="evidence_upload") or [])[:MAX_EVIDENCE_PHOTOS]
    if photos:
        st.image([p.getvalue() for p in photos], width=140)
    if st.button("Check my photos", disabled=not photos):
        try:
            with st.spinner("Looking at your photos…"):
                st.session_state.evidence_check = evidence.check_evidence(
                    [(p.getvalue(), p.type or "image/jpeg") for p in photos], read_claim())
        except Exception as e:  # evidence.py raises RuntimeError on API trouble
            st.error(f"Photo check failed: {e}")
    ec = st.session_state.evidence_check
    if ec:
        if not evidence.is_live():
            st.caption("Mock mode: illustrative result, not read from your photos.")
        visible = ec.get("signage_visible")
        if visible is not None:
            st.markdown(f"**Sign visible from where the car stood:** {'yes' if visible else 'no'}")
        st.write(ec.get("summary", ""))
        for f in ec.get("findings", []):
            icon = "✅" if f.get("supports_claim") else "⚠️"
            st.markdown(f"{icon} **Photo {int(f.get('photo_index', 0)) + 1}** · {f.get('strength', '')} — "
                        f"{f.get('observation', '')}")
        if ec.get("suggested_additions_to_story"):
            st.markdown("**Suggested addition to your story:**")
            st.info(ec["suggested_additions_to_story"])
            st.button("Add to my story and re-check my case", type="primary", on_click=on_apply_evidence)

# 3 · Assessment
st.header("3 · Your odds")
if st.button("Check my case", type="primary", use_container_width=True):
    with st.spinner("Reading the rulebook…"):
        err = run_assessment()
    if err:
        st.error(err)
    else:
        st.session_state.notice = None

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
                tags = " · ".join(t for t in (g.get("category"), str(g.get("strength", "")).lower()) if t)
                st.markdown(f"**{g.get('title', '')}** · {tags}")
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
