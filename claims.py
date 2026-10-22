"""ParkRefund Claude layer: ticket vision extraction, claim assessment, appeal drafting.

Live mode needs ANTHROPIC_API_KEY, ANTHROPIC_PROFILE (a Console login from `ant auth login`) or
OPENAI_API_KEY via .env, or a Sign in with ChatGPT session (chatgpt.py). Without one, every function
runs in deterministic MOCK mode so the app can be built and demoed offline.
"""
import base64
import collections
import io
import json
import os
import threading
import time
from typing import Literal

import anthropic
import openai
from dotenv import load_dotenv
from PIL import Image, ImageOps
from pydantic import BaseModel

import chatgpt
import rules

load_dotenv()

CLAIM_KEYS = ["issuer_type", "issuer_name", "ticket_number", "plate", "date", "time",
              "location", "amount_dkk", "reason_on_ticket", "driver_story", "evidence"]


# Server credentials (.env keys, or one ChatGPT sign-in for a whole api.py) bill the operator for every
# visitor. guard_server_credentials() switches them off when the server is reachable from other machines.
SERVER_KEYS = True
SHARED_CALL_LIMIT = None  # max shared-credential calls per hour for the whole process; None = no cap
LOOPBACK = ("127.0.0.1", "localhost", "::1")
_shared_calls = collections.deque()
_shared_lock = threading.Lock()


def guard_server_credentials(local: bool) -> bool:
    """Call at startup with whether the server only listens on this machine. Off this machine, server
    credentials are used only with PARKREFUND_SHARE_SERVER_KEY=1, and then at most
    PARKREFUND_SHARED_CALLS_PER_HOUR calls an hour (default 30). Returns whether they may be used."""
    global SERVER_KEYS, SHARED_CALL_LIMIT
    SERVER_KEYS = local or os.getenv("PARKREFUND_SHARE_SERVER_KEY") == "1"
    SHARED_CALL_LIMIT = None if local else int(os.getenv("PARKREFUND_SHARED_CALLS_PER_HOUR") or 30)
    return SERVER_KEYS


def server_key_present() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_PROFILE") or os.getenv("OPENAI_API_KEY"))


def _spend_shared_call() -> None:
    """Count one call on a shared credential; refuse once the hourly cap is used up."""
    with _shared_lock:
        now = time.monotonic()
        while _shared_calls and now - _shared_calls[0] > 3600:
            _shared_calls.popleft()
        if len(_shared_calls) >= SHARED_CALL_LIMIT:
            raise RuntimeError(f"This shared ParkRefund has used its {SHARED_CALL_LIMIT} AI requests for this hour. "
                               "Try again later, or run ParkRefund on your own computer with your own plan or key.")
        _shared_calls.append(now)


def _claude() -> bool:
    return SERVER_KEYS and bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_PROFILE"))


def _openai() -> bool:
    return SERVER_KEYS and bool(os.getenv("OPENAI_API_KEY")) and not _claude()  # Claude wins when both are set


def is_live() -> bool:
    return chatgpt.signed_in() or _claude() or _openai()


def _model() -> str:
    default = chatgpt.model() if chatgpt.signed_in() else "gpt-6.1-sol" if _openai() else "claude-sonnet-5-5"
    return os.getenv("PARKREFUND_MODEL", default)


# ---------------------------------------------------------------- schemas
class TicketFields(BaseModel):
    issuer_type: Literal["public", "private"] | None = None
    issuer_name: str | None = None
    ticket_number: str | None = None
    plate: str | None = None
    date: str | None = None
    time: str | None = None
    location: str | None = None
    amount_dkk: int | None = None
    reason_on_ticket: str | None = None


class Ground(BaseModel):
    title: str
    category: str
    strength: Literal["strong", "medium", "weak"]
    explanation: str


class Assessment(BaseModel):
    success_probability: int
    verdict: Literal["strong", "medium", "weak"]
    summary: str
    grounds: list[Ground]
    weaknesses: list[str]
    evidence_to_collect: list[str]
    route: str
    deadline_note: str
    recommend_filing: bool


# ---------------------------------------------------------------- API helpers
def ask(system: str, content, schema=None):
    """One model call on whichever provider is signed in. content: a str or Anthropic-style blocks
    (see image_block). Returns a parsed `schema` instance (or None), or the reply text when schema is None."""
    own_plan = chatgpt.signed_in() and not chatgpt.shared()  # this visitor's own ChatGPT sign-in: never capped
    if SHARED_CALL_LIMIT is not None and not own_plan:
        _spend_shared_call()
    try:
        if chatgpt.signed_in():  # ChatGPT plan: public Responses API, streamed, nothing stored (OpenAI's rules)
            if isinstance(content, list):
                content = [{"type": "input_image", "image_url": f"data:{b['source']['media_type']};base64,{b['source']['data']}"}
                           if b["type"] == "image" else {"type": "input_text", "text": b["text"]} for b in content]
            client = openai.OpenAI(api_key=chatgpt.token(), base_url=chatgpt.RESOURCE, max_retries=0)
            # Plan models reason before answering, and that counts against max_output_tokens.
            with client.responses.stream(model=_model(), instructions=system, input=[{"role": "user", "content": content}],
                                         max_output_tokens=16000, store=False, **({"text_format": schema} if schema else {})) as s:
                deltas = []  # with store=False the final event can carry an empty output list: keep the streamed text
                for ev in s:
                    if ev.type == "response.output_text.delta":
                        deltas.append(ev.delta)
                    elif ev.type == "response.failed":
                        code = ev.response.error.code if ev.response.error else "unknown"
                        raise RuntimeError(f"ChatGPT could not complete this request ({code}). "
                                           "If it is a usage limit, see chatgpt.com/settings/usage.")
                final = s.get_final_response()
            if final.status == "incomplete":  # the SDK treats this as done, but there is no (full) answer
                reason = final.incomplete_details.reason if final.incomplete_details else "unknown"
                raise RuntimeError(f"ChatGPT stopped before finishing the answer ({reason}).")
            text = final.output_text or "".join(deltas)
            if not schema:
                return text.strip()
            return final.output_parsed or (schema.model_validate_json(text) if text else None)
        if _openai():
            if isinstance(content, list):
                content = [{"type": "image_url", "image_url": {"url": f"data:{b['source']['media_type']};base64,{b['source']['data']}"}}
                           if b["type"] == "image" else b for b in content]
            resp = openai.OpenAI().chat.completions.parse(
                model=_model(), max_completion_tokens=4000,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
                **({"response_format": schema} if schema else {}))
            msg = resp.choices[0].message
            if msg.refusal:
                raise RuntimeError("Model declined this request")
            return msg.parsed if schema else (msg.content or "").strip()
        kw = dict(model=_model(), max_tokens=4000, messages=[{"role": "user", "content": content}],
                  system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}])
        api = anthropic.Anthropic().messages
        resp = api.parse(output_format=schema, **kw) if schema else api.create(**kw)
        if resp.stop_reason == "refusal":
            raise RuntimeError("Model declined this request")
        return resp.parsed_output if schema else "".join(b.text for b in resp.content if b.type == "text").strip()
    except (anthropic.APIConnectionError, openai.APIConnectionError) as e:
        raise RuntimeError("Could not reach the model API. Check your connection.") from e
    except (anthropic.RateLimitError, openai.RateLimitError) as e:
        raise RuntimeError("Model API rate limit hit. Wait a moment and retry.") from e
    except (anthropic.BadRequestError, openai.BadRequestError) as e:  # retrying the same input fails the same way
        raise RuntimeError("The model could not process this request (400). Try a different photo.") from e
    except (anthropic.AuthenticationError, openai.AuthenticationError) as e:
        raise RuntimeError("Not authorised (401): the key is wrong or revoked, or the login expired. Fix .env or log in again.") from e
    except (anthropic.APIStatusError, openai.APIStatusError) as e:
        raise RuntimeError(f"Model API error ({e.status_code}). Please retry.") from e
    except openai.APIError as e:  # an error event inside a 200 stream: what ChatGPT sends when plan sharing is off
        if chatgpt.signed_in():
            raise RuntimeError("ChatGPT stopped this request: plan sharing for ParkRefund is off, or its usage limit "
                               "was reached. Check chatgpt.com/settings/usage.") from e
        raise RuntimeError(f"Model API error: {e.message}") from e


MAX_IMAGE_SIDE = 1568  # Claude scales larger images down anyway; this keeps phone photos under the 5 MB API limit


def image_block(image_bytes: bytes) -> dict:
    """Any uploaded photo → upright, downscaled JPEG content block the API accepts."""
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    except OSError as e:
        raise ValueError("Could not open this image. Use a JPEG, PNG or WebP photo.") from e
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.standard_b64encode(out.getvalue()).decode()}}


# ---------------------------------------------------------------- extract_ticket
MOCK_TICKET = {
    "issuer_type": "private",
    "issuer_name": "NordPark ApS",
    "ticket_number": "NP-2026-004117",
    "plate": "AB 12 345",
    "date": "2026-10-03",
    "time": "14:12",
    "location": "Testgade 14, 2100 Testkøbing",
    "amount_dkk": 850,
    "reason_on_ticket": "Parkering uden gyldig p-billet",
}


def extract_ticket(image_bytes: bytes, media_type: str) -> dict:
    if not is_live():
        return dict(MOCK_TICKET)
    system = ("You read photos of Danish parking tickets (afgift / kontrolafgift). Extract only what is "
              "clearly legible; leave a field null if unsure. issuer_type is 'public' for a kommune/police "
              "parkeringsafgift and 'private' for a private operator's kontrolafgift. date is YYYY-MM-DD, "
              "time is HH:MM (24h), amount_dkk is an integer. Never guess or invent values.")
    content = [image_block(image_bytes), {"type": "text", "text": "Extract the ticket fields."}]
    parsed = ask(system, content, TicketFields)
    if parsed is None:
        return {}
    return {k: v for k, v in parsed.model_dump().items() if v not in (None, "")}


# ---------------------------------------------------------------- assess_claim
def _assess_system() -> str:
    hints = "\n".join(f"- {c}: {rules.CATEGORY_HINTS.get(c, '')}" for c in rules.CATEGORIES)
    return f"""You are a Danish parking-fine appeals specialist at a free, open-source public-interest service (no fee, no cut of the refund). You triage claims honestly: people trust it because it tells them when a case is weak.

RULEBOOK (ground truth for this prototype):
{rules.RULES}

Every ground you list MUST carry exactly one category from this list (Parkeringsklagenævnet's categories):
{hints}

Instructions:
- Be calibrated. success_probability (0-100) must follow the rulebook's WIN and LOSE lists: clear winning grounds with evidence -> high; only losing grounds -> low (under 25).
- verdict: "strong" for >= 65, "medium" for 40-64, "weak" below 40.
- Be honest when weak. recommend_filing is false below about 35.
- Never invent facts the user did not give. If something decisive is unknown, say so in weaknesses and ask for it in evidence_to_collect.
- evidence_to_collect must be concrete (e.g. "Photo of the entrance to the car park showing the absence of a sign, taken today").
- Public (kommune) vs private (operator) changes the route: follow the rulebook.
- summary: 2-3 plain-English sentences for a layperson. route: who to appeal to and the steps. deadline_note: deadlines from the ticket and rulebook."""


def assess_claim(claim: dict) -> dict:
    if not is_live():
        return _mock_assess(claim)
    user = "Assess this claim:\n" + json.dumps(claim, ensure_ascii=False, indent=2)
    out = ask(_assess_system(), user, Assessment)
    if out is None:
        raise RuntimeError("Model returned no structured assessment")
    d = out.model_dump()
    d["success_probability"] = max(0, min(100, int(d["success_probability"])))
    for g in d["grounds"]:
        if g["category"] not in rules.CATEGORIES:
            g["category"] = "Formalitet og gyldighedsbetingelser"
    return d


# ---------------------------------------------------------------- mock assessor
def _any(text, words):
    return any(w in text for w in words)


def _mock_assess(claim: dict) -> dict:
    story = str(claim.get("driver_story", ""))
    ev = claim.get("evidence") or []
    ev = [ev] if isinstance(ev, str) else ev
    text = (story + " " + " ".join(map(str, ev))).lower()
    private = claim.get("issuer_type") != "public"
    has_ev = bool(ev) and _any(text, ["photo", "foto", "receipt", "kvittering", "statement", "witness", "vidne", "note"])

    grounds, weaknesses = [], []
    pts = {"strong": 70, "medium": 48, "weak": 15}
    best = 0

    def add(title, cat, strength, expl):
        nonlocal best
        grounds.append({"title": title, "category": cat, "strength": strength, "explanation": expl})
        best = max(best, pts[strength]) if strength != "weak" else best

    # winning grounds
    if _any(text, ["sign", "skilt"]) and _any(text, ["hidden", "missing", "no sign", "not visible", "could not see",
                                                   "skjult", "manglede", "covered", "snow", "faded", "entrance", "indgang"]):
        add("Entrance signage missing or not visible", "Skiltning", "strong",
            "The operator must prove clear signage at the entrance with price, rules and operator name. "
            "The driver reports missing or unreadable signs, which the rulebook names as the strongest ground.")
    if _any(text, ["receipt", "kvittering", "paid", "betalt"]) and _any(text, ["typo", "mistyp", "one character", "wrong letter", "tastefejl", "slip"]):
        add("Paid in app; plate mistyped by one character", "Digital registrering", "strong",
            "Payment covering the ticket time exists and the plate is near-identical. Operators usually refund on goodwill (kulance) when a receipt is shown.")
    obs = _any(text, ["1 minute", "one minute", "minute after", "walking to", "on my way to the machine", "payment machine", "automat"])
    if obs:
        later = _any(text, ["receipt", "kvittering", "paid in the app", "paid at"])
        add("Observation period not respected", "Standsning og observation", "strong" if later else "medium",
            "The ticket was issued within 1-2 minutes of arrival, before the usual 5-minute observation period for walking to a payment machine"
            + (", and a later payment receipt supports this." if later else "."))
    if _any(text, ["unload", "loading", "pålæsning", "afløsning", "afl"]):
        add("Loading/unloading is stopping, not parking", "Standsning og observation", "medium",
            "Stopping up to about 3 minutes to load or unload counts as 'standsning', which is allowed where only parking is prohibited. "
            "Strength depends on proving the short duration.")
    if _any(text, ["wrong plate on the ticket", "wrong date on the ticket", "no photo", "wrong location on the ticket", "forkert dato"]):
        add("Formal defect on the fine", "Formalitet og gyldighedsbetingelser", "strong",
            "A fine with wrong plate, date or location, or without photo documentation, is formally defective.")
    if _any(text, ["handicap"]):
        if _any(text, ["permit", "card displayed", "badge", "tilladelse", "kort"]) and _any(text, ["displayed", "visible", "synlig"]):
            add("Valid handicap permit was displayed", "Handicapparkering", "strong", "A valid, visible permit is a winning ground under the rulebook.")
        else:
            grounds.append({"title": "Handicap bay without proven permit", "category": "Handicapparkering", "strength": "weak",
                            "explanation": "Parking in a handicap bay without an exemption is a losing ground."})
            weaknesses.append("Handicap bays are strictly enforced without a visible permit.")

    # losing grounds
    penalty = 0
    if _any(text, ["p-skive", "parking disc", "disc"]) and _any(text, ["forgot", "forgotten", "not set", "glemt", "didn't put", "did not put"]):
        grounds.append({"title": "Parking disc forgotten", "category": "P-skive", "strength": "weak",
                        "explanation": "A forgotten or unset p-skive is a losing ground under the rulebook."})
        weaknesses.append("A forgotten p-skive is not excused by the rulebook.")
        penalty += 15
    if _any(text, ["few minutes", "only 10", "min over", "minutes over", "just a few"]):
        weaknesses.append("There is no grace period beyond the observation period; 'only a few minutes over' does not win.")
        penalty += 10
    if _any(text, ["everyone else", "didn't know the rules", "did not know the rules"]):
        weaknesses.append("'Everyone else parks there' and not knowing the rules are not accepted grounds.")
        penalty += 5
    if _any(text, ["did see the sign", "did see the signs", "didn't see the sign", "did not see the sign"]) and not best:
        weaknesses.append("Saying you did not see a clear, standard sign does not win.")
        penalty += 5

    winning = [g for g in grounds if g["strength"] != "weak"]
    if winning:
        prob = best + (8 if has_ev else 0) + 5 * (len(winning) - 1) - penalty
        if not has_ev:
            weaknesses.append("No supporting evidence listed yet; the claim rests on the driver's account alone.")
    else:
        prob = 12 - (penalty // 2) + (4 if has_ev else 0)
        if not grounds:
            grounds.append({"title": "No clear ground identified", "category": "Formalitet og gyldighedsbetingelser", "strength": "weak",
                            "explanation": "Nothing in the account matches a winning ground in the rulebook."})
            weaknesses.append("The account does not identify a ground that usually wins.")
    prob = max(5, min(95, prob))
    verdict = "strong" if prob >= 65 else "medium" if prob >= 40 else "weak"
    recommend = prob >= 35

    cats = {g["category"] for g in winning}
    evid = []
    if "Skiltning" in cats:
        evid += ["Photos of the car park entrance showing the absence (or poor visibility) of signs, taken as soon as possible",
                 "Photo of the car's position and the nearest sign, with date visible"]
    if "Digital registrering" in cats:
        evid += ["App payment receipt showing the time span and the plate as typed", "Photo of the vehicle registration certificate"]
    if "Standsning og observation" in cats:
        evid += ["Receipt or delivery note with timestamps", "Written statement from a witness with name and phone number"]
    if not evid:
        evid = ["Photos of the signage and the car's position taken the same day", "Any payment receipt or permit", "A copy of the ticket"]

    amount = claim.get("amount_dkk")
    if private:
        route = ("Complain in writing to the operator (" + str(claim.get("issuer_name") or "the operator") +
                 ") first. If rejected, complain to Parkeringsklagenævnet within about 4 weeks (fee ~175 DKK, refunded if you win).")
    else:
        route = ("Send a written indsigelse to " + str(claim.get("issuer_name") or "the kommune") +
                 "'s parkeringskontor. If rejected, the only further route is Fogedretten.")
    deadline = ("Appeal within the deadline printed on the ticket (commonly 10 days to pay); later appeals are accepted and the fine is paused while a complaint is handled."
                + (f" Ticket date: {claim.get('date')}." if claim.get("date") else ""))
    label = {"strong": "a strong", "medium": "a borderline", "weak": "a weak"}[verdict]
    top = winning[0]["title"].lower() if winning else "no ground that usually wins"
    summary = (f"This looks like {label} case with about {prob}% chance of success"
               + (f" for a {amount} DKK fine" if amount else "") + f". The main point is: {top}. "
               + ("We recommend appealing." if recommend else "We would not recommend appealing, as the rulebook does not support it."))
    return {"success_probability": prob, "verdict": verdict, "summary": summary, "grounds": grounds,
            "weaknesses": weaknesses, "evidence_to_collect": evid, "route": route,
            "deadline_note": deadline, "recommend_filing": recommend}


# ---------------------------------------------------------------- draft_appeal
def draft_appeal(claim: dict, assessment: dict, language: str = "da") -> str:
    if not is_live():
        return _mock_letter(claim, assessment, language)
    lang = "Danish" if language == "da" else "English"
    private = claim.get("issuer_type") != "public"
    system = (f"You write appeal letters (indsigelse) against Danish parking fines, in {lang}. Plain text only, no markdown. "
              "Factual, polite, specific. Cite ticket number, plate, date, time and location. State each ground from the assessment "
              "using its category name. List the attached evidence (only evidence the claim actually lists). Request annulment "
              "(annullering). " +
              ("Address it to the private operator; mention that if rejected the case will be brought to Parkeringsklagenævnet. "
               if private else "Address it to the kommune's parkeringskontor. ") +
              "Use placeholders like [Dit navn] / [Your name], [Adresse], [Dato] where personal info is missing. "
              "Never invent facts the driver did not give. Output only the letter.")
    user = ("Claim:\n" + json.dumps(claim, ensure_ascii=False, indent=2) +
            "\n\nAssessment:\n" + json.dumps(assessment, ensure_ascii=False, indent=2))
    return ask(system, user)


def _mock_letter(claim, assessment, language):
    c = {k: claim.get(k) or "[ukendt]" for k in CLAIM_KEYS}
    private = claim.get("issuer_type") != "public"
    grounds = [g for g in assessment.get("grounds", []) if g.get("strength") != "weak"] or assessment.get("grounds", [])
    ev = claim.get("evidence") or []
    ev = [ev] if isinstance(ev, str) else ev
    if language == "en":
        to = f"{c['issuer_name']}" if private else f"{c['issuer_name']}, Parking Office (parkeringskontor)"
        g = "\n".join(f"{i}. {x['title']} (category: {x['category']}): {x['explanation']}" for i, x in enumerate(grounds, 1))
        e = "\n".join(f"- {x}" for x in ev) or "- The ticket"
        esc = ("If my objection is rejected I will bring the matter before Parkeringsklagenævnet.\n\n" if private else "")
        return (f"[Your name]\n[Address]\n[Date]\n\nTo: {to}\n\n"
                f"Re: Objection to ticket no. {c['ticket_number']} - plate {c['plate']}\n\n"
                f"Dear Sir or Madam,\n\nI object to the ticket of {c['amount_dkk']} DKK issued on {c['date']} at {c['time']} "
                f"at {c['location']} for vehicle {c['plate']}.\n\nMy account: {c['driver_story']}\n\n"
                f"Grounds:\n{g}\n\nAttached evidence:\n{e}\n\n"
                f"I request that the ticket be annulled (annullering) and that any payment be refunded.\n\n{esc}"
                f"Kind regards,\n[Your name]")
    to = f"{c['issuer_name']}" if private else f"{c['issuer_name']}, Parkeringskontoret"
    g = "\n".join(f"{i}. {x['title']} (kategori: {x['category']}): {x['explanation']}" for i, x in enumerate(grounds, 1))
    e = "\n".join(f"- {x}" for x in ev) or "- Afgiften"
    esc = ("Hvis min indsigelse afvises, vil jeg indbringe sagen for Parkeringsklagenævnet.\n\n" if private else "")
    return (f"[Dit navn]\n[Adresse]\n[Dato]\n\nTil: {to}\n\n"
            f"Vedr.: Indsigelse mod afgift nr. {c['ticket_number']} - nummerplade {c['plate']}\n\n"
            f"Til rette vedkommende,\n\nJeg gør hermed indsigelse mod afgiften på {c['amount_dkk']} kr., udstedt den {c['date']} "
            f"kl. {c['time']} på {c['location']} til køretøj {c['plate']}.\n\nMin forklaring: {c['driver_story']}\n\n"
            f"Grundlag for indsigelsen:\n{g}\n\nVedlagt dokumentation:\n{e}\n\n"
            f"Jeg anmoder om, at afgiften annulleres (annullering), og at et eventuelt indbetalt beløb tilbagebetales.\n\n{esc}"
            f"Med venlig hilsen\n[Dit navn]")


# ---------------------------------------------------------------- payout
def payout(amount_dkk: int) -> dict:
    fee = round(amount_dkk * rules.SUCCESS_FEE)
    return {"refund": amount_dkk, "fee": fee, "you_get": amount_dkk - fee}


if __name__ == "__main__":
    case = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample_cases.json"), encoding="utf-8"))[0]
    print(f"MODE: {'LIVE' if is_live() else 'MOCK'}  model={_model()}\n")
    a = assess_claim(case)
    print(json.dumps(a, ensure_ascii=False, indent=2))
    print("\n----- APPEAL (da) -----\n")
    print(draft_appeal(case, a))
    print("\n----- PAYOUT -----")
    print(payout(case["amount_dkk"]))
