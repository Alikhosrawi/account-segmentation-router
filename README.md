# Account segmentation + SDR routing engine

Built by Ali Khosravi with [Claude Code](https://claude.com/claude-code) as co-pilot. Python stdlib only.

*One chore, gone:* deciding which accounts an SDR team should work this week, and who should work them. The engine reads each company's public job ads, asks Claude Haiku 4.5 for **fit** (does this look like a buyer?) and **intent** (is now a good moment?) with a word-for-word quote for every claim, checks those quotes in code, then uses plain rules to set segment, tier and owner, and can write it all to HubSpot as companies, owners and tasks.

> **What is real and what is not.** 58 real companies with public Greenhouse / Ashby / Lever boards (checked 26 Oct 2026). Headcount and HQ country come from public web pages, with the page and the quote stored per company in `data/companies.csv`. Sources are aggregators (LinkedIn, PitchBook, Latka, Dealroom…) and can be stale. The SDR roster (`data/sdrs.SYNTHETIC.json`) is fictional. The product being sold is a generic European spend-management tool. Scores say nothing about the real companies; they show how the pipeline works.

Accuracy is measured against **hand labels by the author** (`eval/labels_reviewed.csv`, n = 36 after excluding competitors). See `eval/RESULTS.md` for caveats.

## How it works

| Step | Code | What it does |
|---|---|---|
| Snapshot | `router/snapshot.py` | Picks up to 3 recent finance / sales / ops ads per company from the public ATS APIs (`router/ats_fetch.py`). Frozen and hashed; the ad text itself is not published. |
| Firmographics | `scripts/extract_firmo.py` | Haiku reads saved web-search results and extracts headcount and HQ country. Each value needs a quote found verbatim on the cited page, otherwise `unknown`. |
| Score | `router/run.py`, `prompts/fit_intent_v*.md` | Haiku 4.5, temperature 0, strict JSON: `fit` 0–3, `intent` 0–3, and up to 5 signals, each with `posting_id`, verbatim `evidence_quote`, `confidence`. Replies are recorded so every run can be replayed for free. |
| Guards | `router/core.py` | Schema, verbatim quote check, evidence caps, confidence tier cap. |
| Segment | rules | SMB ≤200 staff, Mid-Market 201–1000, Enterprise >1000, Unknown if no cited source. |
| Tier | rules | Tier 1: fit+intent ≥4 and intent ≥2. Tier 2: fit+intent ≥2. Else Tier 3. All signals below 0.6 confidence: capped at Tier 3. |
| Route | rules | Round-robin over SDRs matching territory + segment with capacity left. No match → `overflow`; guard failure → `needs_human`, never routed. Deterministic order. |
| Competitors | `data/competitors.json` | Deterministic rule after scoring: Pleo, Moss, Perk and Qonto (matched by domain) get fit 0, intent 0, Tier 3, routing rule `competitor_excluded`, no SDR and no task. The model's original scores are kept on the record for audit. |
| Write-back | `router/hubspot.py` | HubSpot CRM v3: custom properties, idempotent company upsert, owner mapping, one task per routed Tier 1/2 account. `--dry-run` sends nothing. |

The model never sets segment, tier or owner.

## Architecture

```
companies.csv ──► ATS fetch ──► ≤3 postings / company
      │                              │
      │                    Claude Haiku (temp 0, JSON)
      │                              │
      │              guards: schema · verbatim quote · evidence caps
      ▼                              ▼
 Segment (rules) ──────────► Tier (rules) ───► SDR assignment (rules)
                                                      │
                                               out/accounts.jsonl
                                                      │
                                               HubSpot (optional)
```

See `DESIGN.md` for types and rules, and `PREREGISTRATION.md` for the frozen eval protocol.

## Results (eval set)

Pre-registered in `PREREGISTRATION.md` before v2 scored the eval set. v2 was tuned only on the 18 tune companies. Primary ground truth is the author's **gut tier** (amendment A2); formula tier from fit/intent is secondary.

| | Keyword baseline | v1 prompt | v2 prompt (preregistered) | v3 (post-hoc) |
|---|---|---|---|---|
| Tier accuracy vs gut tier (n = 36) | 42% | 44% | **53%** | 58% |
| Tier-1 precision / recall (8 gold Tier 1) | – / 0/8 | 1/1 / 1/8 | – / 0/8 | **2/2 / 2/8** |
| needs human | 0/36 | 12/36 | 3/36 | 5/36 |

v2 is the headline (preregistered). v3 was tuned after seeing v2 error patterns on eval, so its numbers are optimistic — reported next to, never instead of, v2. Details: `eval/RESULTS.md`.

Competitors are excluded from accuracy (fixed rule, not the model). Full run notes and caveats are in `eval/RESULTS.md`.

## Limitations

- **Over-calling on weak evidence.** Ordinary SDR job ads can still be read as "sales team scaling". The quote guard catches invented evidence, not weak evidence.
- **v2 finds no Tier 1.** Finance hires are often scored as weak intent. Not fixed on the eval set (would be cheating).
- **Competitors are a hand-maintained list**, not a model decision.
- **Headcount freshness.** Aggregator numbers lag.
- **n = 36, one labeller.** A single company moves accuracy by ~2.8 points. No confidence interval is claimed.
- **Job-ad snapshot is private.** Third-party posting text stays outside the repo; replay/eval tests that need it skip when absent.

## Run it

```bash
cp .env.example .env   # fill ANTHROPIC_API_KEY / HUBSPOT_TOKEN only if you call live APIs

python3 router/run.py --mode replay --prompt prompts/fit_intent_v2a.md
python3 router/run.py --mode baseline
python3 scripts/apply_competitor_rule.py out/accounts.replay.fit_intent_v2a.jsonl
python3 router/hubspot.py --accounts out/accounts.replay.fit_intent_v2a.jsonl --dry-run
# HUBSPOT_TOKEN=… python3 router/hubspot.py --accounts … --live --default-owner-email you@company.com
python3 -m unittest discover -s tests
python3 scripts/evaluate.py eval/labels_reviewed.csv out/accounts.*.eval.jsonl
```

Replay needs a private job-ad snapshot (`SEGR_SNAPSHOT=path`); tests that need it skip without it. Live scoring needs `ANTHROPIC_API_KEY`. Live HubSpot write-back needs `HUBSPOT_TOKEN`.

## Cost

About **$1.32** of Anthropic API spend in total for this build (label drafts, firmographics extraction, three prompt versions including v3, eval and full runs; summed from recorded `usage` in `data/replay/` and `eval/label_drafts/`). A weekly rerun of 58 companies with v2 costs about $0.25.

## License

MIT — see `LICENSE`.
