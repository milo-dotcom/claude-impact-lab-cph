"""ParkRefund evidence check: Claude vision over the user's sign / car-position photos.

Live mode needs ANTHROPIC_API_KEY (via .env). Without it check_evidence returns a fixed,
plausible MOCK result so the UI works offline. Contract (issue #4):

    check_evidence(images, claim) -> dict
    images: [(bytes, media_type), ...]
    {"findings": [{"photo_index": int, "observation": str, "supports_claim": bool,
                   "strength": "strong"|"medium"|"weak"}],
     "signage_visible": bool | None, "summary": str, "suggested_additions_to_story": str}
"""
import base64
import json
import os
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

MAX_IMAGES = 5


def is_live() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _model() -> str:
    return os.getenv("PARKREFUND_MODEL", "claude-sonnet-5-5")


# ---------------------------------------------------------------- schema
class Finding(BaseModel):
    photo_index: int
    observation: str
    supports_claim: bool
    strength: Literal["strong", "medium", "weak"]


class EvidenceCheck(BaseModel):
    findings: list[Finding]
    signage_visible: bool | None
    summary: str
    suggested_additions_to_story: str


# ---------------------------------------------------------------- prompt
SYSTEM = """You check photo evidence for an appeal against a Danish parking fine. The photos were taken by the driver, usually of the parking sign(s) and of where the car stood.

Describe only what is visible. For each photo say what it shows. For a sign: whether its text is legible, whether tariff, hours, rules and operator name are stated, and whether anything obstructs it (vegetation, snow, a vehicle, damage, angle, darkness). Say whether each photo supports the driver's claim and how strongly. Do not guess facts that are not in the photo; never invent dates, times, places or plate numbers.

signage_visible: true if a sign relevant to the fine is clearly legible in the photos, false if a sign is present but obstructed or unreadable, null if no sign appears.

suggested_additions_to_story: one to three factual first-person sentences the driver could add to their account, based only on what the photos show. If the photos do not help the claim, say so plainly in summary and leave suggested_additions_to_story empty."""


# ---------------------------------------------------------------- API helpers
def _call(fn, **kwargs):
    try:
        resp = fn(**kwargs)
    except anthropic.APIConnectionError as e:
        raise RuntimeError("Could not reach the Claude API. Check your connection.") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("Claude API rate limit hit. Wait a moment and retry.") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Claude API error ({e.status_code}). Please retry.") from e
    if resp.stop_reason == "refusal":
        raise RuntimeError("Model declined this request")
    return resp


# ---------------------------------------------------------------- check_evidence
def check_evidence(images: list[tuple[bytes, str]], claim: dict) -> dict:
    images = list(images)[:MAX_IMAGES]
    if not images:
        return {"findings": [], "signage_visible": None, "summary": "No photos to check.",
                "suggested_additions_to_story": ""}
    if not is_live():
        return _mock_check(images, claim)

    content = []
    for i, (data, media_type) in enumerate(images):
        content.append({"type": "text", "text": f"Photo {i + 1} (photo_index {i}):"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                      "data": base64.standard_b64encode(data).decode()}})
    context = {k: claim.get(k) for k in ("issuer_type", "issuer_name", "reason_on_ticket", "location", "driver_story")}
    content.append({"type": "text", "text": "Claim context:\n" + json.dumps(context, ensure_ascii=False, indent=2)
                    + "\n\nAssess the photos as evidence for this claim."})
    resp = _call(anthropic.Anthropic().messages.parse, model=_model(), max_tokens=4000, system=SYSTEM,
                 messages=[{"role": "user", "content": content}], output_format=EvidenceCheck)
    out = resp.parsed_output
    if out is None:
        raise RuntimeError("Model returned no structured evidence check")
    d = out.model_dump()
    for f in d["findings"]:
        f["photo_index"] = max(0, min(len(images) - 1, int(f["photo_index"])))
    return d


# ---------------------------------------------------------------- mock
_MOCK_FINDINGS = [
    ("A blue P-sign with a white tariff board under it. A bush covers most of the board; only a fragment of "
     "text is legible, so tariff, hours and operator name cannot be read from this position.", True, "strong"),
    ("The car stands inside a marked bay. No sign is visible in the frame between the car and the entrance.",
     True, "medium"),
    ("Another view of the area. Nothing in it changes the assessment.", False, "weak"),
]


def _mock_check(images, claim):
    findings = []
    for i in range(len(images)):
        obs, supports, strength = _MOCK_FINDINGS[min(i, len(_MOCK_FINDINGS) - 1)]
        findings.append({"photo_index": i, "observation": obs, "supports_claim": supports, "strength": strength})
    return {
        "findings": findings,
        "signage_visible": False,
        "summary": ("The sign nearest the car is obstructed and its tariff board is not legible from the bay. "
                    "That supports a signage ('Skiltning') ground; attach these photos to the appeal."),
        "suggested_additions_to_story": (
            "From where I parked, the tariff board under the P-sign was covered by a bush and could not be read. "
            "I have photos of the sign and of the car's position, taken the same day."),
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    case = json.load(open(os.path.join(here, "data", "sample_cases.json"), encoding="utf-8"))[0]
    photos = []
    for name in ("sign_hidden.png", "sign_clear.png"):
        with open(os.path.join(here, "data", "tickets", "signs", name), "rb") as fh:
            photos.append((fh.read(), "image/png"))
    print(f"MODE: {'LIVE' if is_live() else 'MOCK'}  model={_model()}\n")
    print(json.dumps(check_evidence(photos, case), ensure_ascii=False, indent=2))
