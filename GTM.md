# ParkRefund — Go-to-market, first 30 days after launch

*Hackathon plan, 21 Oct 2026. Numbers are targets and assumptions, not data.*

## The 30-day impact plan — three answers

**01 · A named owner.** JC (@spontain112) takes it forward after tonight: owns the repo, the
live URL, and the first ten cases. milo-dotcom stays on data (nævn decisions, WFS signage).

**02 · The first real-world test.** Ten people in Copenhagen who got a private kontrolafgift in the
last 30 days — friends, colleagues, one Facebook parking group. They upload the real ticket, get
the verdict and the letter, and send it themselves. We handle nothing yet; we watch. What we want
to learn, in order: (1) does a human handler agree with the model's verdict on each case, (2) do
people actually send the letter when we say "strong" and *not* send it when we say "weak",
(3) what the operators answer within three weeks. Success = 10 verdicts reviewed, 5 letters sent,
and at least one refund we can show.

**03 · The support we need.** Two hours of a Danish lawyer on `rules.py` (the rulebook is a
hackathon approximation). One private operator or kommune parkeringskontor willing to be a
pilot counterpart instead of an adversary. Introductions to Parkeringsklagenævnet for the
decision corpus beyond the 100-per-query cap. API credits for ~500 live assessments. And one
part-time case handler for weeks 3–4, when the first operator answers come back.

## The bet

One city, one ticket type, one channel. **Copenhagen, private operators' kontrolafgifter, acquired at
the moment of anger** — when the ticket is still under the wiper. We don't need many customers to
prove the model; we need a clean win rate and a payout story we can show on day 31.

Why private first: Parkeringsklagenævnet only hears private tickets, the complaint route is
standardised, and that's where the published decisions are. Kommune fines come in month two.

## Product that ships on day 1 (no more than this)

- Web flow as demoed: photo → honest verdict → Danish appeal letter → "we file it for you".
- We take cases with ≥ 60% model probability *and* a human handler's OK. Everything else gets the
  letter for free with a "you can send this yourself" — that's our top-of-funnel goodwill.
- Pricing: **no win, no fee; 30% of the refunded amount** (≈ 200–270 DKK on a 650–900 DKK ticket).
  Minimum fee none. Customer pays nothing up front, ever.
- Ops: one part-time case handler, the ops dashboard, a shared inbox. Handler files by email to the
  operator, escalates to the nævn on rejection (we front the ~175 DKK complaint fee).

## Channels (in order of expected cost per case)

| # | Channel | Why it works | Week |
|---|---|---|---|
| 1 | **Search** — Google Ads on "kontrolafgift klage", "parkeringsbøde klage", operator names + "klage" | The only moment people look. High intent, tiny volume, cheap. | 1 → |
| 2 | **Operator-specific landing pages** — "Got a NordPark-style fine at [car park]? Check it in 60 s" | Ranks for long-tail; matches the ticket in the driver's hand. | 1 → |
| 3 | **Reddit r/Denmark, Facebook groups (Copenhagen parking, "Parkering – klager")** | Where people already ask "can I fight this?"; answer with the free checker, not an ad. | 2 → |
| 4 | **Physical: QR flyers at the 20 worst car parks** (by nævn decision count) | Under-the-wiper is literally where the ticket is. Cheap test, legal to leaflet on public ground. | 3 |
| 5 | **Referral: "won? send it to a friend, we waive their fee cap"** | Refund moments are shareable; cost only on success. | 3 → |

Not doing in 30 days: TV/OOH, influencers, partnerships with operators (adversarial), app stores
(the iOS build is a demo, not a launch), kommune tickets, other cities.

## Week by week

**Week 1 — plumb and watch.** Launch quietly. Search ads on at 150 DKK/day. Every case reviewed by a
human; every letter read before sending. Instrument the funnel (visits → checks → cases taken →
filed). Target: 50 checks, 10 cases filed.

**Week 2 — tune the honesty.** Compare model verdicts to the handler's decisions; fix the rulebook
where they disagree. Publish the first "we said no" number — it's the trust message. Open the
community channels with the free checker. Target: 150 checks, 30 filed.

**Week 3 — first outcomes.** Operators answer in 2–3 weeks; first refunds land. Turn every win into
a one-line testimonial (with consent) on the landing page. Flyers at the top-20 car parks. Referral
loop live. Target: 300 checks, 60 filed, first 5 wins.

**Week 4 — decide month two.** Read the numbers below. If win rate on filed cases ≥ 55% and CAC per
filed case ≤ 100 DKK, double the ad budget and start kommune tickets. If not, fix the funnel, not the
market.

## The five numbers (reviewed every Monday)

| Metric | Day-30 target | Why it matters |
|---|---|---|
| Checks → cases taken | 20% | Honesty filter is working, not just rejecting everyone |
| Win rate on filed cases | ≥ 55% | The business exists or it doesn't |
| Cost per filed case (ads + flyers) | ≤ 100 DKK | Must be well under the ~230 DKK expected fee |
| Handler minutes per case | ≤ 10 | The automation claim, measured |
| Time to first refund | ≤ 21 days | Cash cycle; also the referral trigger |

Unit economics to beat: fee ≈ 230 DKK × 55% win rate ≈ **125 DKK expected revenue per filed case**
vs ≤ 100 DKK acquisition + ~10 handler minutes. Thin, so volume and automation are the whole game.

## Must-haves before the first real customer

- **GDPR**: plates and tickets are personal data; privacy notice, data minimisation, deletion after
  case close + 1 year, DPA with the hosting/model provider, no training on customer data.
- **Terms**: power of attorney for the appeal, success-fee definition, what happens on partial refund,
  and that *we decide which cases we take*.
- **Legal review of the rulebook** by a Danish lawyer — two hours is enough to remove howlers.
- **Human in the loop** stays: the model drafts and recommends; a handler files. This is also the
  marketing line.
- A fallback for the nævn fee: we front it; if we lose, we eat it. Budget 30 losses × 175 DKK.

## Budget for 30 days (rough)

| Item | DKK |
|---|---|
| Search ads (150/day) | 4,500 |
| Flyers + printing | 1,500 |
| Nævn fees fronted (30 cases) | 5,250 |
| Model/API usage (~500 assessments, Opus) | ~1,000 |
| Case handler, part-time | 15,000 |
| Legal (rulebook + terms review) | 8,000 |
| **Total** | **~35,000 DKK** |

## What "good" looks like on day 31

300+ people checked a ticket, 60 cases filed, a double-digit win count, a public "we said no to 40%
of cases" number, one handler at under 10 minutes a case, and a decision — not a hope — about
month two.
