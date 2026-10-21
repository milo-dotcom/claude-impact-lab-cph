"""ParkRefund customer flow: landing → intake → assessment → letter → payout.

Run: .venv/bin/streamlit run app.py

Talks to claims.py (issue #8) through the contract in CONCEPT.md, and to evidence.py
(issue #4) for the sign / car-position photo check. No .env → both run in mock mode.
Presentation layer is custom HTML/CSS (brand, step tracker, verdict card, letter paper,
receipt); every dynamic value is html-escaped before it goes into a block.
"""

import html
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
VERDICT_STYLE = {  # colour, stamp text
    "strong": ("#1B8A5A", "Strong case"),
    "medium": ("#C77D00", "Borderline"),
    "weak": ("#B3261E", "Weak case"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap');
:root { --navy:#0B2545; --navy2:#163B6E; --ink:#14213D; --muted:#5B6B82; --line:#E5E9F0; --paper:#FFFDF7;
        --ticket:#FFC72C; --green:#1B8A5A; --amber:#C77D00; --red:#B3261E; }
html, body, .stApp, [data-testid="stSidebar"] { font-family: Inter, "Source Sans Pro", system-ui, sans-serif; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none; }
.block-container { padding-top: 1.6rem; max-width: 880px; }
@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes fill { from { width: 0; } }
@keyframes stamp { from { transform: rotate(-6deg) scale(2.2); opacity: 0; }
                   70% { transform: rotate(-6deg) scale(.96); opacity: 1; }
                   to { transform: rotate(-6deg) scale(1); opacity: 1; } }

.pr-hero { position: relative; overflow: hidden; padding: 30px 32px 26px; border-radius: 20px; color: #fff;
           background: linear-gradient(135deg, var(--navy) 0%, var(--navy2) 100%); animation: rise .6s ease-out both; }
.pr-mark { display: inline-flex; align-items: center; gap: 10px; font-weight: 800; letter-spacing: .4px; font-size: 1.05rem; }
.pr-mark .p { width: 32px; height: 32px; border-radius: 8px; background: #fff; color: var(--navy); display: grid;
              place-items: center; font-weight: 900; font-size: 1.1rem; }
.pr-hero h1 { font-size: 2.3rem; line-height: 1.08; margin: 16px 0 8px; font-weight: 800; letter-spacing: -.5px; color: #fff; }
.pr-hero .tag { font-size: 1.08rem; opacity: .92; max-width: 560px; }
.pr-hero .tag b { color: var(--ticket); white-space: nowrap; }
.pr-grid { display: grid; grid-template-columns: 1.15fr .85fr; gap: 28px; align-items: center; }
@media (max-width: 760px) { .pr-grid { grid-template-columns: 1fr; } }
.pr-eyebrow { font-size: .72rem; font-weight: 800; letter-spacing: 1.6px; text-transform: uppercase; color: var(--ticket); margin-bottom: 10px; }
.pr-hero h1 em { font-style: normal; color: var(--ticket); }
.pr-hero .da { opacity: .78; font-size: .95rem; margin-top: 8px; font-style: italic; }
.pr-cta { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }
.pr-cta a { display: inline-block; padding: 12px 18px; border-radius: 12px; font-weight: 800; text-decoration: none !important; background: var(--ticket); color: var(--navy) !important;
            border: 1px solid var(--ticket); transition: transform .12s ease, box-shadow .2s ease; }
.pr-cta a.ghost { background: transparent; color: #fff !important; border-color: rgba(255,255,255,.4); font-weight: 600; }
.pr-cta a:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(0,0,0,.25); }
.pr-trust { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 16px; font-size: .82rem; opacity: .85; }
.pr-trust span::before { content: "✓ "; color: var(--ticket); font-weight: 800; }
.pr-slipwrap { display: grid; place-items: center; min-height: 300px; }
.pr-slip { position: relative; width: min(300px, 100%); background: #FFD54F; color: #1A1A1A; border-radius: 6px; padding: 16px 16px 14px; margin: 0 auto;
           font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: .78rem; box-shadow: 0 20px 50px rgba(0,0,0,.35); transform: rotate(-3deg); overflow: hidden; }
.pr-slip .head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-weight: 800; font-size: .95rem; letter-spacing: 1px;
                 border-bottom: 2px dashed rgba(0,0,0,.28); padding-bottom: 8px; margin-bottom: 8px; font-family: Inter, sans-serif; }
.pr-slip .head span { font-weight: 600; font-size: .72rem; letter-spacing: 0; white-space: nowrap; }
.pr-slip .row { display: flex; justify-content: space-between; gap: 10px; padding: 3px 0; }
.pr-slip .row span { opacity: .7; } .pr-slip .row b { text-align: right; }
.pr-slip .amount { font-family: Inter, sans-serif; font-weight: 800; font-size: 1.5rem; text-align: right; margin-top: 8px; border-top: 2px solid rgba(0,0,0,.6); padding-top: 6px; }
.pr-slip .foot { font-size: .62rem; opacity: .65; margin-top: 8px; }
.pr-slip .scan { position: absolute; left: 0; right: 0; top: 0; height: 3px; background: linear-gradient(90deg, transparent, #0B2545, transparent); box-shadow: 0 0 18px 4px rgba(11,37,69,.35); opacity: 0; }
.pr-slip .big { position: absolute; left: 50%; top: 44%; transform: translate(-50%,-50%) rotate(-14deg) scale(2.4); opacity: 0; border: 4px solid #1B8A5A; color: #1B8A5A;
                font-family: Inter, sans-serif; font-weight: 900; font-size: 1.5rem; letter-spacing: 3px; padding: 6px 14px; border-radius: 8px; mix-blend-mode: multiply; }
.pr-slip .refund { position: absolute; right: 12px; top: 10px; background: #1B8A5A; color: #fff; font-family: Inter, sans-serif; font-weight: 800; padding: 6px 10px; border-radius: 999px;
                   font-size: .85rem; opacity: 0; transform: translateY(8px); box-shadow: 0 8px 20px rgba(0,0,0,.25); }
.pr-slip.loop .scan { animation: prscan 7s ease-in-out infinite; }
.pr-slip.loop .big { animation: prstampin 7s cubic-bezier(.2,1.4,.4,1) infinite; }
.pr-slip.loop .refund { animation: prrefund 7s ease-out infinite; }
@keyframes prscan { 0%,8% { top: 0; opacity: 0; } 10% { opacity: 1; } 32% { top: 100%; opacity: 1; } 34%,100% { opacity: 0; top: 100%; } }
@keyframes prstampin { 0%,38% { opacity: 0; transform: translate(-50%,-50%) rotate(-14deg) scale(2.4); } 46% { opacity: 1; transform: translate(-50%,-50%) rotate(-14deg) scale(.96); }
                       50%,88% { opacity: 1; transform: translate(-50%,-50%) rotate(-14deg) scale(1); } 96%,100% { opacity: 0; transform: translate(-50%,-50%) rotate(-14deg) scale(1); } }
@keyframes prrefund { 0%,52% { opacity: 0; transform: translateY(8px); } 58%,88% { opacity: 1; transform: none; } 96%,100% { opacity: 0; transform: translateY(8px); } }
.pr-slip.small { width: min(250px, 100%); font-size: .7rem; transform: rotate(-2deg); padding: 12px; box-shadow: 0 10px 30px rgba(20,33,61,.15); margin: 6px 0 12px; }
.pr-slip.small .amount { font-size: 1.2rem; }
@keyframes prflash { 0% { background: #FFE89A; box-shadow: 0 0 0 3px rgba(255,199,44,.55); } 100% { box-shadow: none; } }
.pr-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 22px; }
.pr-stat { background: rgba(255,255,255,.09); border: 1px solid rgba(255,255,255,.18); border-radius: 12px; padding: 12px 14px; }
.pr-stat b { display: block; font-size: 1.55rem; letter-spacing: -.5px; }
.pr-stat span { font-size: .8rem; opacity: .82; }

.pr-steps { display: flex; gap: 8px; margin: 18px 0 2px; }
.pr-step { flex: 1; padding: 8px 10px; border-radius: 10px; border: 1px solid var(--line); font-size: .8rem; color: var(--muted);
           background: #fff; display: flex; gap: 8px; align-items: center; white-space: nowrap; transition: all .25s ease; }
.pr-step i { font-style: normal; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
             border: 1.5px solid var(--line); font-size: .72rem; font-weight: 700; flex: none; }
.pr-step.done { border-color: var(--green); color: var(--ink); }
.pr-step.done i { background: var(--green); color: #fff; border-color: var(--green); }
.pr-step.now { border-color: var(--navy); color: var(--ink); box-shadow: 0 0 0 3px rgba(11,37,69,.08); }
.pr-step.now i { background: var(--navy); color: #fff; border-color: var(--navy); }

.pr-h { display: flex; align-items: baseline; gap: 12px; margin: 30px 0 2px; }
.pr-h .n { font-size: .74rem; font-weight: 800; letter-spacing: 1.6px; color: var(--navy); text-transform: uppercase; }
.pr-h h2 { margin: 0; font-size: 1.45rem; font-weight: 800; color: var(--ink); letter-spacing: -.3px; }
.pr-sub { color: var(--muted); margin: 0 0 12px; font-size: .95rem; }

.pr-verdict { border: 1px solid var(--line); border-radius: 18px; padding: 22px 24px 18px; background: #fff;
              box-shadow: 0 10px 30px rgba(20,33,61,.06); animation: rise .5s ease-out both; }
.pr-verdict .lbl { font-size: .74rem; letter-spacing: 1.6px; text-transform: uppercase; color: var(--muted); font-weight: 800; }
.pr-verdict .top { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.pr-verdict .num { font-size: 3.8rem; font-weight: 800; line-height: 1; color: var(--ink); letter-spacing: -2px; animation: rise .6s ease-out both; }
.pr-stamp { display: inline-block; padding: 8px 16px; border: 3px solid var(--c); color: var(--c); border-radius: 8px; font-weight: 900;
            letter-spacing: 2px; text-transform: uppercase; background: #fff; transform: rotate(-6deg);
            animation: stamp .55s cubic-bezier(.2,1.4,.4,1) both; animation-delay: .35s; }
.pr-bar { height: 10px; border-radius: 999px; background: #EEF1F6; overflow: hidden; margin: 16px 0 6px; }
.pr-bar i { display: block; height: 100%; border-radius: 999px; width: var(--p); background: var(--c);
            animation: fill 1.1s cubic-bezier(.2,.8,.2,1) both; }
.pr-take { margin-top: 14px; padding: 12px 14px; border-radius: 12px; font-weight: 600; }
.pr-take.yes { background: #E8F5EE; color: #145C3B; }
.pr-take.no { background: #FBEAE8; color: #7A1C14; }
.pr-take small { display: block; font-weight: 500; opacity: .85; margin-top: 4px; }
.pr-summary { margin: 14px 0 0; color: #2B3A55; font-size: 1.02rem; }

.pr-card { border: 1px solid var(--line); border-left: 4px solid var(--c, var(--navy)); border-radius: 12px; padding: 12px 14px;
           margin: 8px 0; background: #fff; animation: rise .45s ease-out both; }
.pr-card b { font-size: 1rem; color: var(--ink); }
.pr-card .meta { font-size: .74rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-left: 8px; }
.pr-card p { margin: 6px 0 0; color: #2B3A55; }
.pr-list { margin: 4px 0 0; padding-left: 18px; color: #2B3A55; }
.pr-list li { margin: 4px 0; }
.pr-h3 { font-size: .74rem; letter-spacing: 1.6px; text-transform: uppercase; color: var(--muted); font-weight: 800; margin: 18px 0 6px; }

.pr-paper { background: var(--paper); border: 1px solid #EADFBF; border-radius: 6px; padding: 34px 38px; font-family: "Source Serif 4", Georgia, serif;
            font-size: 1rem; line-height: 1.55; white-space: pre-wrap; color: #1F2937; max-height: 520px; overflow: auto;
            box-shadow: 0 12px 32px rgba(20,33,61,.10); animation: rise .6s ease-out both; }
.pr-receipt { border: 1px dashed #C9D1DE; border-radius: 14px; padding: 18px 20px; background: #fff; max-width: 480px; animation: rise .5s ease-out both; }
.pr-receipt .row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--line); color: #2B3A55; }
.pr-receipt .row.total { border: 0; font-weight: 800; font-size: 1.35rem; color: var(--ink); margin-top: 4px; }
.pr-receipt .note { color: var(--muted); font-size: .85rem; margin-top: 8px; }

[data-testid="stSidebarNavLink"] span[label="app"] p { font-size: 0; }
[data-testid="stSidebarNavLink"] span[label="app"] p::after { content: "Your case"; font-size: .95rem; }
.pr-side .pr-mark { color: var(--ink); }
.pr-side .pr-mark .p { background: var(--navy); color: #fff; }
.pr-side .tag { color: var(--muted); font-size: .9rem; margin: 6px 0 14px; }
.pr-side .status { font-size: .85rem; color: var(--ink); padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.pr-side .status small { color: var(--muted); }

button[data-testid="stBaseButton-primary"] { background: var(--navy); border: 0; border-radius: 12px; padding: .72rem 1rem; font-weight: 700;
    transition: transform .12s ease, box-shadow .2s ease, background .2s ease; }
button[data-testid="stBaseButton-primary"]:hover { background: var(--navy2); transform: translateY(-1px); box-shadow: 0 8px 20px rgba(11,37,69,.25); }
button[data-testid="stBaseButton-secondary"] { border-radius: 12px; font-weight: 600; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea { border-radius: 10px; }
[data-testid="stExpander"] details { border-radius: 12px; }
</style>
"""

SAMPLE_TICKET_PATH = Path(__file__).parent / "data" / "tickets" / "0_NP-2026-004117.png"
SLIP_HTML = ("<div class='head'>KONTROLAFGIFT<span>NordPark ApS</span></div>"
             "<div class='row'><span>Afgiftsnr.</span><b>NP-2026-004117</b></div><div class='row'><span>Reg.nr.</span><b>AB 12 345</b></div>"
             "<div class='row'><span>Dato / kl.</span><b>03.10.2026 · 14:12</b></div><div class='row'><span>Sted</span><b>Testgade 14, Testkøbing</b></div>"
             "<div class='row'><span>Overtrædelse</span><b>Uden gyldig p-billet</b></div><div class='amount'>850,00 DKK</div>"
             "<div class='foot'>Betales inden 10 dage · Indsigelse sendes skriftligt til NordPark ApS</div>"
             "<div class='scan'></div><div class='big'>ANNULLERET</div><div class='refund'>+850 DKK back</div>")


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def section(n: int, title: str, sub: str, anchor: str = "") -> None:
    st.markdown(f"<div class='pr-h' id='{anchor or f'step-{n}'}'><span class='n'>Step {n}</span><h2>{esc(title)}</h2></div>"
                f"<p class='pr-sub'>{esc(sub)}</p>", unsafe_allow_html=True)


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
        # Streamlit drops widget keys while another page (Ops dashboard) is shown: restore the form.
        saved = st.session_state.get("saved_claim", {})
        for k in claims.CLAIM_KEYS:
            st.session_state.setdefault(field(k), saved.get(k, [] if k == "evidence" else 0 if k == "amount_dkk" else ""))
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
    st.session_state.last_upload_id = None
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
    st.session_state.saved_claim = {k: st.session_state[field(k)] for k in claims.CLAIM_KEYS}


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


def ingest_image(data: bytes, media_type: str, label: str) -> None:
    """Read a ticket image (an upload or the sample slip) into the form. Runs in the main
    flow (not a callback) so the spinner is visible while the model reads the image; it
    must run before the form widgets render, since it writes their session-state keys."""
    try:
        extracted = claims.extract_ticket(data, media_type)
    except Exception as e:  # claims.py raises RuntimeError on API trouble
        st.session_state.notice = ("error", f"Could not read the {label}: {e}")
        return
    put_claim(extracted)
    clear_results()
    st.session_state.sample_pick = None
    st.session_state.just_filled = True  # one-shot highlight on the fields this run
    filled = [k for k in claims.CLAIM_KEYS if extracted.get(k) not in (None, "", [])]
    note = f"Read {len(filled)} fields from the {label} — check them below."
    if not claims.is_live():
        note += " (Demo mode: the values are the sample ticket's, not read from your image.)"
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

st.set_page_config(page_title="ParkRefund — your personal ticket lawyer", page_icon="🅿️", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)
init_state()
normalize_fields()

with st.sidebar:
    live = claims.is_live()
    st.markdown(
        "<div class='pr-side'><div class='pr-mark'><span class='p'>P</span>ParkRefund</div>"
        "<div class='tag'>Your personal ticket lawyer</div></div>", unsafe_allow_html=True)
    st.markdown(f"**Mode:** {'🟢 LIVE' if live else '🟠 MOCK (demo)'}  \n**Engine:** `{MODEL_NAME}`")
    if not live:
        st.caption("No ANTHROPIC_API_KEY — deterministic demo output from claims.py / evidence.py.")
    st.divider()
    st.caption("The model drafts and recommends; a human files.")
    st.caption("Synthetic demo data. ParkRefund is not a law firm — not legal advice.")

# Hero: lead with the outcome, then the proof (a slip getting scanned, cancelled, refunded)
st.markdown(
    "<div class='pr-hero'><div class='pr-grid'><div>"
    "<div class='pr-eyebrow'>Parkeringsbøde · Kontrolafgift · Indsigelse</div>"
    "<h1>Got a parking fine? <em>Get your money back.</em></h1>"
    "<div class='tag'>Upload the ticket. Your personal ticket lawyer tells you honestly whether an appeal will win, "
    "writes the <i>indsigelse</i> for you, and only gets paid when the money comes back. <b>No win, no fee.</b></div>"
    "<div class='da'>Parkeringsbøde? Vi henter dine penge hjem.</div>"
    "<div class='pr-cta'><a href='#step-1'>Check my odds — it's free</a><a class='ghost' href='#step-1'>Try the sample ticket</a></div>"
    "<div class='pr-trust'><span>No win, no fee</span><span>30 % only on refunds</span><span>Verdict in under a minute</span></div>"
    "</div><div class='pr-slipwrap'><div class='pr-slip loop'>" + SLIP_HTML + "</div></div></div>"
    "<div class='pr-stats'><div class='pr-stat'><b>12,480</b><span>fines fought</span></div>"
    "<div class='pr-stat'><b>71 %</b><span>won on appeal</span></div>"
    "<div class='pr-stat'><b>6,214,350 DKK</b><span>back in drivers' pockets</span></div></div></div>",
    unsafe_allow_html=True)
st.caption("Demo numbers — synthetic data.")

# Step tracker
a = st.session_state.assessment
done_upto = 4 if st.session_state.letter else 3 if a else 1
labels = ["Your ticket", "What happened", "Your odds", "Appeal letter", "Payout"]
steps = ""
for i, lbl in enumerate(labels, start=1):
    cls = "done" if i <= done_upto else "now" if i == done_upto + 1 else ""
    mark = "✓" if cls == "done" else str(i)
    steps += f"<div class='pr-step {cls}'><i>{mark}</i>{lbl}</div>"
st.markdown(f"<div class='pr-steps'>{steps}</div>", unsafe_allow_html=True)

# 1 · Intake
section(1, "Your ticket", "Photograph the fine — we read it for you. Try our sample ticket, upload your own, or pick a sample case.")
left, right = st.columns(2)
with left:
    st.markdown("<div class='pr-h3' style='margin-top:0'>Sample ticket</div><div class='pr-slip small'>" + SLIP_HTML + "</div>",
                unsafe_allow_html=True)
    scan = st.button("Scan this ticket", disabled=not SAMPLE_TICKET_PATH.exists())
with right:
    upload = st.file_uploader("Upload a photo of the fine (jpeg / png / webp)", type=PHOTO_TYPES,
                              key="ticket_upload")
if scan:
    with st.spinner("Scanning the ticket… (about 10 s)"):
        ingest_image(SAMPLE_TICKET_PATH.read_bytes(), "image/png", "sample ticket")
elif upload is not None and upload.file_id != st.session_state.last_upload_id:
    st.session_state.last_upload_id = upload.file_id
    with st.spinner("Reading your ticket… (about 10 s)"):
        ingest_image(upload.getvalue(), upload.type or "image/jpeg", "ticket photo")
with right:
    st.selectbox("…or pick a sample case", SAMPLE_LABELS, key="sample_pick", index=None,
                 placeholder="Choose a case…", on_change=on_pick_sample)
if st.session_state.notice:
    kind, text = st.session_state.notice
    getattr(st, kind)(text)
if st.session_state.pop("just_filled", False):  # style element exists for this run only, so the flash plays once
    st.markdown("<style>[data-testid='stTextInput'] input, [data-testid='stNumberInput'] input "
                "{ animation: prflash 1.2s ease-out both; }</style>", unsafe_allow_html=True)

# 2 · Story
section(2, "What happened", "Your own words. Tick the evidence you have — it moves the odds.")
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
            with st.spinner("Inspecting your photos… (about 15 s)"):
                st.session_state.evidence_check = evidence.check_evidence(
                    [(p.getvalue(), p.type or "image/jpeg") for p in photos], read_claim())
        except Exception as e:  # evidence.py raises RuntimeError on API trouble
            st.error(f"Photo check failed: {e}")
    ec = st.session_state.evidence_check
    if ec:
        if not evidence.is_live():
            st.caption("Demo mode: illustrative result, not read from your photos.")
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

# 3 · Verdict
section(3, "Your odds", "The honest verdict: what carries your case, what sinks it, and what to go photograph.")
if st.button("Check my case", type="primary", use_container_width=True):
    if st.session_state.assessment and read_claim() == st.session_state.assessed_claim:
        st.toast("Already checked — edit the form to check again.")  # a second click must not cost another call
    else:
        with st.spinner("Reviewing your fine against the rulebook… (usually 5–20 s)"):
            err = run_assessment()
        if err:
            st.error(err)
        else:
            st.session_state.notice = None

a = st.session_state.assessment
if a:
    prob = max(0, min(100, int(a.get("success_probability", 0))))
    verdict = str(a.get("verdict", "weak")).lower()
    colour, stamp = VERDICT_STYLE.get(verdict, ("#666", verdict))
    take = ("<div class='pr-take yes'>We'd take this case. Below is what carries it, and what would make it stronger.</div>"
            if a.get("recommend_filing") else
            "<div class='pr-take no'>We wouldn't take this case — here's why.<small>No fee, no filing from us. "
            "You can still draft a letter below and send it yourself.</small></div>")
    st.markdown(
        f"<div class='pr-verdict' style='--c:{colour}'><div class='lbl'>Chance of winning</div>"
        f"<div class='top'><div class='num'>{prob} %</div><div class='pr-stamp' data-verdict='{esc(verdict)}'>{esc(stamp)}</div></div>"
        f"<div class='pr-bar'><i style='--p:{prob}%'></i></div>{take}"
        f"<p class='pr-summary'>{esc(a.get('summary', ''))}</p></div>", unsafe_allow_html=True)

    if a.get("grounds"):
        st.markdown("<div class='pr-h3'>What helps you</div>", unsafe_allow_html=True)
        for g in a["grounds"]:
            gc = VERDICT_STYLE.get(str(g.get("strength", "")).lower(), ("#0B2545", ""))[0]
            tags = " · ".join(esc(t) for t in (g.get("category"), str(g.get("strength", "")).lower()) if t)
            st.markdown(f"<div class='pr-card' style='--c:{gc}'><b>{esc(g.get('title', ''))}</b>"
                        f"<span class='meta'>{tags}</span><p>{esc(g.get('explanation', ''))}</p></div>",
                        unsafe_allow_html=True)
    lists = [(t, items) for t, items in (("What works against you", a.get("weaknesses")),
                                         ("Evidence that would raise the odds", a.get("evidence_to_collect"))) if items]
    for col, (title, items) in zip(st.columns(len(lists)) if len(lists) > 1 else [st], lists):
        col.markdown(f"<div class='pr-h3'>{title}</div><ul class='pr-list'>"
                     + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>", unsafe_allow_html=True)
    st.markdown(f"<div class='pr-card'><b>Where to appeal</b><p>{esc(a.get('route', ''))}</p>"
                f"<b style='display:block;margin-top:10px'>Deadline</b><p>{esc(a.get('deadline_note', ''))}</p></div>",
                unsafe_allow_html=True)

    # 4 · Letter
    section(4, "Your appeal letter", "A ready-to-send indsigelse, citing the ticket, the ground and your evidence.")
    lang = st.radio("Language", ["da", "en"], horizontal=True, key="letter_lang",
                    format_func=lambda v: {"da": "Dansk", "en": "English"}[v])
    if st.button("Draft my appeal", use_container_width=True):
        if st.session_state.letter and st.session_state.get("letter_lang_done") == lang:
            st.toast("Already drafted in this language — switch language to draft again.")
        else:
            try:
                with st.spinner("Writing your indsigelse… (usually 5–20 s)"):
                    st.session_state.letter = claims.draft_appeal(st.session_state.assessed_claim, a, language=lang)
                st.session_state.letter_rev += 1
                st.session_state.letter_lang_done = lang
            except Exception as e:  # claims.py raises RuntimeError on API trouble
                st.error(f"Drafting failed: {e}")
    if st.session_state.letter:
        key = f"letter_text_{st.session_state.letter_rev}"
        with st.expander("Edit before sending"):
            st.text_area("Letter", st.session_state.letter, height=360, key=key, label_visibility="collapsed")
        text = st.session_state.get(key, st.session_state.letter)
        st.markdown(f"<div class='pr-paper'>{esc(text)}</div>", unsafe_allow_html=True)
        ticket_no = (st.session_state.assessed_claim or {}).get("ticket_number") or "appeal"
        st.download_button("Download as .txt", text, file_name=f"indsigelse_{ticket_no}.txt", mime="text/plain")
        st.caption("The model drafts and recommends; a human files. Read it, sign it, send it.")

    # 5 · Payout
    section(5, "If we win", "The whole deal on one receipt.")
    amount = int((st.session_state.assessed_claim or {}).get("amount_dkk") or 0)
    pay = claims.payout(amount)
    fee_pct = round(100 * pay["fee"] / pay["refund"]) if pay.get("refund") else round(100 * SUCCESS_FEE)
    st.markdown(
        f"<div class='pr-receipt'><div class='row'><span>Refund</span><b>{pay['refund']:,} DKK</b></div>"
        f"<div class='row'><span>Our fee ({fee_pct} %)</span><b>−{pay['fee']:,} DKK</b></div>"
        f"<div class='row total'><span>You get</span><span>{pay['you_get']:,} DKK</span></div>"
        f"<div class='note'>Paid out when the refund lands. Nothing to pay up front.</div></div>",
        unsafe_allow_html=True)
    st.caption("You pay nothing if we lose.")
