"""Simplified rulebook for Danish parking fines, used as grounding for the assessor.

This is a hackathon approximation, not legal advice. Amounts and deadlines are
rounded/illustrative. Operator and municipality names in the demo are synthetic.
"""

RULES = """
# Parking fines in Denmark – simplified rulebook (prototype)

## Two kinds of fine
1. PUBLIC ("parkeringsafgift", issued by a kommune or the police)
   - Standard amount ~510 DKK; ~1,020 DKK for serious cases (handicap bay, fire lane, pavement).
   - Appeal ("indsigelse") goes in writing to the kommune's parkeringskontor. No fee.
   - If the kommune rejects, the only further route is Fogedretten (bailiff's court).
   - The kommune must document the offence (photos, time of observation).
2. PRIVATE ("kontrolafgift", issued by a private operator on private land)
   - Typically 650–900 DKK. It is a contractual claim, not a public fine.
   - Step 1: complain to the operator. Step 2: if rejected, complain to Parkeringsklagenævnet
     (complaint fee ~175 DKK, refunded if you win). Deadlines are usually stated on the ticket.
   - The operator must prove clear signage at the ENTRANCE of the area with price, rules, and
     operator name. Unclear or missing entrance signage is the single strongest ground.
   - Operators are expected to apply an observation period (usually 5 minutes) before ticketing a
     car without a visible ticket/disc, to allow the driver to walk to a payment machine.

## Grounds that usually WIN
- No sign, or sign not visible from where the car was parked (hidden by snow, vegetation, a van, graffiti).
- Entrance signage missing or incomplete (private areas).
- Observation period not respected (ticket issued within 1–2 minutes of arrival).
- Fine issued while the driver was loading/unloading ("af- og pålæsning"): stopping up to ~3 minutes
  for loading is "standsning", not "parkering", and is allowed where only parking is prohibited.
- Payment was made (app or machine) but with a typo in the plate; most operators and kommuner
  refund on goodwill ("kulance") when a receipt is shown with a near-identical plate.
- Payment confirmed for the time of the ticket (receipt timestamp covers the ticket timestamp).
- Valid handicap permit / resident permit was displayed and visible.
- Breakdown or medical emergency, documented (roadside-assistance receipt, hospital note).
- Fine is formally defective: wrong plate, wrong date, wrong location, no photo documentation.
- Parking disc ("p-skive") set correctly within the normal rounding rule (set to the next quarter hour
  after arrival).

## Grounds that usually LOSE
- "I didn't see the sign" when the sign was clear and standard.
- "I was only a few minutes over" (no grace period beyond the observation period).
- "I didn't know the rules" / "everyone else parks there".
- P-skive forgotten, not set, or set to a later time than permitted.
- Parked in a handicap bay, fire lane, pavement, or in front of a driveway without exemption.
- Paid via app but for the wrong zone/area code.
- The fine was placed on the car but blew away / was lost (the issuer's photo proves placement).

## Scope note
Parkeringsklagenævnet only hears PRIVATE operators' kontrolafgifter, and that is where published
decisions exist, so private cases are the primary target. Public (kommune) fines are still
supported but there is no public corpus of outcomes for them.

## Procedure
- Always appeal in writing, within the deadline printed on the ticket (commonly 10 days to pay, but
  appeals are accepted later; the fine is paused while a complaint is being handled).
- Attach: photos of the signage and the car's position taken the same day, payment receipt,
  the fine itself, and any permit.
- Tone: factual, polite, specific. State the ticket number, plate, date/time, location,
  the ground(s), the attached evidence, and what you request (annulment / "annullering").
- Deadline to complain to Parkeringsklagenævnet: within ~4 weeks of the operator's rejection.
"""

# Parkeringsklagenævnet's own decision categories (see docs/data-sources.md). The assessor labels
# every ground with one of these so our output speaks the regulator's language.
CATEGORIES = [
    "Skiltning",
    "P-skive",
    "P-billet",
    "Digital registrering",
    "Standsning og observation",
    "Handicapparkering",
    "P-tilladelse",
    "Gæste-/periodekort",
    "Opmærkning og områdets indretning",
    "Motorcykel/knallert",
    "Formalitet og gyldighedsbetingelser",
]

# Rough mapping from the rulebook's grounds to those categories, for prompts and evals.
CATEGORY_HINTS = {
    "Skiltning": "missing, hidden, unclear or incomplete signage; entrance sign lacks price/rules/operator",
    "P-skive": "parking disc set wrongly, missing, or disputed rounding",
    "P-billet": "paper ticket not visible, fell down, expired, or was valid",
    "Digital registrering": "app/ANPR payment with plate typo, wrong zone, or registration lag",
    "Standsning og observation": "loading/unloading, stopping vs parking, observation period not respected",
    "Handicapparkering": "handicap bay with or without a visible permit",
    "P-tilladelse": "resident/business permit displayed or registered",
    "Gæste-/periodekort": "guest or period card validity",
    "Opmærkning og områdets indretning": "bay markings, layout, where the car actually stood",
    "Motorcykel/knallert": "two-wheeler specific rules",
    "Formalitet og gyldighedsbetingelser": "wrong plate/date/location on the fine, no photo, deadlines",
}

# Success fee charged on a won case, AirHelp-style "no win, no fee".
SUCCESS_FEE = 0.30
