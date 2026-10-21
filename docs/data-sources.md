# Data sources — parking ticket appeals (DK)

Checked 21 Oct 2026. All endpoints below were called live and returned data.

## Legal Parking (the app) — unusable as a source

Closed consumer app, no public API, no open dataset, no docs.
Publisher: Innova Apps ApS / Alex Gameli Heyman, Valby — support@innovaapps.ai.
Its privacy label covers payment info, precise location, email, phone, user ID,
so even a partnership is a GDPR data-sharing agreement, not a data pull.

It is a renderer on top of the open data below. Skip it. Pull the sources directly.

## Københavns Kommune WFS — street rules and signage

Base: `https://wfs-kbhkort.kk.dk/k101/ows` — Open Data DK, no API key, no auth.

| Layer (`k101:`) | Rows | Useful fields |
|---|---|---|
| `p_pladser` | 29,579 | `vejnavn`, `vejside`, `antal_pladser`, `p_ordning`, `p_type`, `restriktion`, `restriktionstekst`, temporary-suspension dates |
| `skilte_total` | 37,414 | geometry, `hovedtavle_1` (e.g. `C62`), up to 3 `undertavle`, sign text, `status`, `ejer` |
| `beboerzone_pr_adresse` | 85,364 | address → resident-permit zone |
| `p_zoner_kbh` | 115 | zone polygons: betalings-, beboer-, flex-, prikgade, tidsrestriktion |
| `parkomat` | 1,602 | meters |
| `p_hus` | 31 | garages |

GeoJSON pull:

```bash
curl "https://wfs-kbhkort.kk.dk/k101/ows?service=WFS&version=2.0.0&request=GetFeature\
&typeNames=k101:p_pladser&outputFormat=application/json&srsName=EPSG:4326"
```

Row count without downloading: swap `outputFormat=...` for `resultType=hits`.

Licence is per-dataset on Open Data DK — confirm before any commercial launch.

## Parkeringsklagenævnet — labelled appeal outcomes

1,108 published decisions. Each is a real-text PDF (~1.5 MB, not scans) and each
arrives pre-labelled with the outcome plus a category and free-text tags.

- Outcome: `medhold` / `ikkemedhold` / `afvist`
- 11 categories: Digital registrering, Skiltning, P-skive, P-billet, Opmærkning og
  områdets indretning, Standsning og observation, Motorcykel/knallert,
  Handicapparkering, P-tilladelse, Gæste-/periodekort, Formalitet og gyldighedsbetingelser
- Tags seen: "ANPR, fejltastning", "QR kode", "Adm gebyr", "Skiltning, helligdag", …

List (JSON: `numResults` + list HTML containing a GUID per case):

```bash
curl -X POST https://www.parkeringsklagenaevnet.dk/da/afgoerelser/ \
  -d "action=getVerdicts&query=&status=medhold&categoryId=25"
```

PDF: `https://www.parkeringsklagenaevnet.dk/da/afgoerelser/?action=getVerdict&token=<guid>`

Caps at **100 results per query, no page parameter**. To reach all 1,108, enumerate
`status` (3) × `categoryId` (11) = 33 buckets, then split any bucket that returns 100
using `query` terms. Full corpus is ~1.7 GB of PDF — rate-limit the crawl.

## Two gaps that shape the MVP

1. **Scope.** The nævn only hears *private* parking companies (kontrolafgifter).
   Municipal p-afgifter go to parkering.kk.dk behind MitID, and there is **no public
   corpus of municipal outcomes**. Target private tickets first.
2. **Selection bias.** These are *udvalgte* (selected) decisions. In the first 100 pulled,
   83 were `medhold`. That is not the real win rate. Use the corpus to learn what a winning
   argument looks like, never as a win-probability prior.

## Not checked

Frederiksberg, Aarhus, Aalborg and Roskilde open data. Full WFS schemas (one sample
feature inspected per layer). Open Data DK licence terms per dataset.
