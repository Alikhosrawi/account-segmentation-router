# Segmentation + SDR routing engine — design (step 1)

Companion to an earlier hiring-signal scorer build. Same rules: Python stdlib only, the model proposes, code decides.
Written before the code; the code follows these shapes (`router/shapes.py`).

## Pipeline

```
companies.csv ──► fetch boards (ats_fetch.py, reused) ──► pick ≤3 relevant postings / company
      │                                                         │
      │                                     Claude (haiku-4-5, temp 0, strict JSON)
      │                                                         │
      │                                guards: schema · verbatim quote per signal ·
      │                                conf<0.6 caps tier · dedupe by domain
      ▼                                                         ▼
 Segment (rules, headcount band) ───────► Tier (rules: fit + intent) ───► SdrAssignment (rules)
                                                                              │
                                                       out/accounts.jsonl  (HubSpot-shaped, step 2: Sheet/HubSpot)
```

The model never assigns segment, tier or SDR. It only reads postings and returns scores with quotes.

## Types

| Type | Fields | Set by |
|---|---|---|
| `Company` | `company, domain (dedupe key), ats, board_slug, headcount_band (+raw, quote, source), hq_country (+basis, quote, source), territory` | `data/companies.csv` |
| `Posting` | `posting_id, company, domain, title, location, source_url, plain_text` | fetcher |
| `Signal` | `kind ∈ {fit, intent}`, `signal_type`, `posting_id`, `evidence_quote` (verbatim), `confidence 0–1` | model, then guard |
| `Score` | `fit 0–3`, `intent 0–3`, `signals[Signal]`, `prompt_version`, `guard_flags[]`, `lane ∈ {ok, needs_human, none}` | model + guard |
| `Segment` | `SMB` (≤200), `Mid-Market` (201–1000), `Enterprise` (>1000), `Unknown` (no cited source → overflow) | rules on headcount band |
| `Tier` | `1–3` + `tier_reasons[]` | rules on Score |
| `SdrAssignment` | `sdr_id, sdr_name, rule, queue` (`assigned` / `overflow` / `needs_human`) | router |

### Signal types
- fit (does this company look like a spend-management buyer?): `finance_complexity` (multi-entity, multi-currency, many cost centres, scaling finance team), `distributed_spend` (many employees spending: field teams, offices in several countries, travel), `finance_tooling` (names an ERP / accounting / spend stack, e.g. NetSuite, DATEV, Xero).
- intent (is now a good moment?): `finance_hiring` (building/expanding finance, controlling, procurement), `gtm_scaleup`, `new_market`, `tool_adoption` (migrating/rolling out a named finance or GTM tool).

A score of 0 needs no quote. Every signal needs a quote that appears verbatim in the posting it cites, else the whole company goes to `needs_human`.

## Rules

- Tier: `points = fit + intent`; Tier 1 if `points ≥ 4 and intent ≥ 2`; Tier 2 if `points ≥ 2`; else Tier 3. If every cited signal has `confidence < 0.6` → Tier 3 (capped, reason recorded).
- Routing: Enterprise → named-account SDR for the territory; SMB/Mid-Market → round-robin among SDRs whose `territories` and `segments` match and whose `capacity` is not used up; nobody eligible → `overflow` queue; `needs_human` accounts are not routed. Order is deterministic (tier, then domain) so reruns give the same assignment.
- SDR roster `data/sdrs.SYNTHETIC.json` is fictional.

## Data honesty
- Company names, domains and boards are real and public (checked 2026-10-26; 5 wrong-company boards removed).
- Headcount and HQ come from cited public pages (`data/companies.csv`); unverifiable values are marked. Territory = mapping from HQ country; non-EU HQ → overflow.
- The SDR roster is fictional.

## Modes
`replay` (default, no key, reads `data/replay/`), `live --save-replay` (records raw replies), `snapshot` postings in `data/snapshot/`.
