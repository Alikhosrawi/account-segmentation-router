# Eval results — reviewed labels (26 Oct 2026)

Labels: `eval/labels_reviewed.csv`, hand-labelled by the author (fit/intent + gut tier). Raw metrics: `eval/results.raw.jsonl` (`python3 scripts/evaluate.py eval/labels_reviewed.csv out/accounts.baseline.baseline_kw_v1.eval.jsonl out/accounts.live.fit_intent_v1.eval.jsonl out/accounts.live.fit_intent_v2a.eval.jsonl`).
n = 36 (40 eval companies minus the 4 competitors, amendment A1). Prompts were **not** changed after seeing these labels.

## Headline (primary = author's gut tier, amendment A2)

| | Keyword baseline | v1 | v2 (frozen v2a) |
|---|---|---|---|
| Tier accuracy vs gut tier | 0.417 (15/36) | 0.444 (16/36) | **0.528 (19/36)** |
| Tier-1 precision | n/a (0 predicted) | 1.00 (1/1) | n/a (0 predicted) |
| Tier-1 recall (8 gold Tier 1) | 0 / 8 | 1 / 8 | **0 / 8** |
| Fit exact / within 1 | 0.28 / 0.64 | 0.25 / 0.86 | 0.42 / 0.92 |
| Intent exact / within 1 | 0.31 / 0.44 | 0.42 / 0.97 | 0.22 / 0.94 |
| Needs human | 0 / 36 | 12 / 36 (33%) | 3 / 36 (8%) |
| *Secondary: tier accuracy vs formula tier from author fit/intent* | 0.278 | 0.306 | 0.333 |

Confusion matrix, v2 vs gut tier (rows = gold, cols = predicted 1/2/3): T1 `0 7 1`, T2 `0 8 5`, T3 `0 4 11`.
v1: T1 `1 4 3`, T2 `0 2 11`, T3 `0 2 13`. Baseline: T1 `0 2 6`, T2 `0 0 13`, T3 `0 0 15`.

Gold Tier 1 (gut): Bitpanda, Buena, DeepL, Enpal, GoCardless, Lovable, Mirakl, TrueLayer.

## Label self-consistency
The author's own fit/intent run through the router's tier formula gives **18** Tier 1; the gut call gives **8**. Formula vs gut agree on 20/36 (0.556); all 8 gut Tier 1 are formula Tier 1, plus 9 gut-Tier-2 and 1 gut-Tier-3 (N26). Cause: intent was scored 2 for most RevOps/sales hires, against the stated rule that those should count 1 at most. This is why the gut tier is primary: it is the "who should sales call this week" judgement, and it is stricter and more coherent than the formula output.

## Main error patterns (v2)
1. **Tier 1 missed by one intent point (7 of 8).** v2 finds the right evidence (`finance_hiring`, `finance_tooling`) but scores intent 1, so fit 2 + intent 1 = 3 lands in Tier 2. Buena, Enpal, GoCardless, Mirakl (fit 2, intent 1); Bitpanda, TrueLayer (1/1); DeepL (1/2). Lovable (gut Tier 1) went to needs_human. A finance/accounting hire is not being counted as a clear intent signal.
2. **Boilerplate read as finance hiring (Tier 2, gut Tier 3).** Make, Matillion, Raisin, N26 each get a `finance_hiring`/`finance_complexity` pair from office lists or a bank's own treasury desk.
3. **Multi-country GTM gets fit 0 (Tier 3, gut Tier 2).** Contentful, Parloa, Pigment: v2 returns no fit signal, or no signals at all, for companies the author sees as multi-market.

## Caveats
- n = 36 and one labeller (the author): a single company moves accuracy by 2.8 points. No confidence interval is claimed.
- The primary ground truth (gut tier) differs from the pre-registered one (formula tier from human fit/intent). Disclosed as amendment A2; both are reported.
- Labels were made with AI drafts visible; the author changed many but anchoring is possible.
- HeyJobs is a bad data row (its only ad is "TEST Sales Manager"). Kept in n; all systems put it in Tier 3, matching the gut call.
- Scores used 0–2 in practice on a 0–3 header scale; fit/intent exact-match is therefore conservative for any 3s.
- These results suggest fixing intent scoring for finance hires, but any such change must be a new prompt version tested on the tune split and a fresh holdout, not this eval set.

## v3 — post-hoc, tuned after seeing v2 error patterns on eval; n=36 single labeller (amendment A3)
v2 stays the preregistered headline. v3 was frozen with hashes (A3) before it scored eval; tuned in one iteration on the 18 tune companies only. Output: `out/accounts.replay.fit_intent_v3.eval.jsonl`.

| | v2 (frozen v2a, headline) | v3 (post-hoc) |
|---|---|---|
| Tier accuracy vs gut tier | 0.528 (19/36) | 0.583 (21/36) |
| Tier-1 precision | n/a (0 predicted) | 1.00 (2/2) |
| Tier-1 recall (8 gold) | 0/8 | 2/8 |
| Fit exact / within 1 | 0.42 / 0.92 | 0.42 / 0.81 |
| Intent exact / within 1 | 0.22 / 0.94 | 0.56 / 0.92 |
| Needs human | 3/36 (8%) | 5/36 (14%) |
| Tier acc. vs formula tier | 0.333 | 0.361 |

Confusion v3 vs gut (rows gold, cols pred 1/2/3): T1 `2 3 3`, T2 `0 5 8`, T3 `0 1 14`.

Changes vs v2 (12 companies): **fixed** Enpal, GoCardless (now Tier 1, finance-ops hire), Make, Matillion, Raisin, N26 (boilerplate / treasury no longer counted, now Tier 3). **Regressed** Buena and Mirakl (gut Tier 1; v3 scored them 2/1 and 2/2 but a quote failed the verbatim check -> needs_human), Aircall, Brevo, Storyblok (gut Tier 2 -> Tier 3, fit dropped to 0: the extra prompt rules made the model more conservative on fit), Celonis (gut 3 -> 2). The multi-country fit rule did not help Contentful, Parloa or Pigment.

Caveat: these numbers are optimistic, since the fix targets errors seen on this eval set. A fair test needs fresh companies.
