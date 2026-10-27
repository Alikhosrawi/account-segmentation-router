# Pre-registration — segmentation router eval

Frozen 2026-10-26 11:20 CET, before any model scored the 40 eval companies with v2.

## What is frozen
- **Classifier v2 = `prompts/fit_intent_v2a.md`** (prompt_version `fit_intent_v2a`), claude-haiku-4-5, temperature 0. Comparison: v1 (`fit_intent_v1`) and the keyword baseline (`baseline_kw_v1`).
- Split: 40 eval / 18 tune (`eval/split.json`). v2 and v2a were written and checked only on the 18 tune companies.
- Disclosure: in step 1 (before the split existed) v1 was run on 10 companies; 5 of them (DeepL, Planhat, Pleo, Qonto, Storyblok) are now in eval. Their v1 outputs were seen. That trial motivated generic quote rules, not company-specific ones.
- Gold labels: claude-sonnet-4-6 drafts (`eval/labels_draft.json`, separate prompt, never saw classifier output), corrected by Ali. Gold tier is derived from gold fit/intent with the same tier rule as the router.
- Primary metric: tier accuracy on the 40 eval companies. Secondary: Tier-1 precision, fit/intent within ±1, needs_human rate.
- Guards and tier rule: `router/core.py` as hashed below. Any later change is logged as an amendment below and results are reported both ways.

## SHA-256

| file | sha256 |
|---|---|
| `prompts/fit_intent_v1.md` | `857111608cf8ea91cbbbb8e52ac8f736d31dcd55d10fd6db50f6b5269e0f4345` |
| `prompts/fit_intent_v2a.md` | `1bc78049b5a7ed43e10fd21ceea0c31cf72ac8881a5af66304ee1f273fa21a7c` |
| `prompts/label_draft_sonnet_v1.md` | `fb63aab7397538f027a08918294663be669fa92465e08d006791c69b5d57039a` |
| `schemas/score.schema.json` | `8118471ff3f9a1f9ff94c8cc47ba0579d3a5fd1580ff7e7d827051a572cc8659` |
| `router/core.py` | `e0c7ad498ca81ac63ca6c7d87fb3345a572afc479ed1635d44b8e0c7795b362f` |
| `router/run.py` | `1b2d51cae4c9e50f249764763f97a16b7927c27e4942de67070f1bd9909ca605` |
| `scripts/evaluate.py` | `a7f734a51fc417788f5b024c2c58fb962e3bd357851ed167d6a073586e902f8f` |
| `eval/split.json` | `220457c27af502b038a886fad2fa59868a156864421b0507405a20a6e14efdf4` |
| `eval/labels_draft.json` | `47068147bfc36b2460aceb3f2e1961108fa9315bb676add5a12270811b5d07d7` |
| `data/companies.csv` | `5d40bee30ff89ba6ca2e00254c0baa0076e9a37f2b152b690a57ac67d68a7772` |
| `data/sdrs.SYNTHETIC.json` | `e633204f9f71965627502a28122fc89a27e070926dd9b26b9deda933c234e6d5` |
| `(private) snapshot/postings.jsonl` | `96b9ecefc3b5b098a367c2bf4ac0b4478a96780030e64d5aba33cbcef0b98d93` |

## Amendments

### A1 — deterministic competitor rule (post-freeze, 2026-10-26 evening CET)
- **What:** `data/competitors.json` lists Pleo, Moss, Perk and Qonto (matched by normalised domain). After the model scores them, `core.apply_competitor_rule` sets fit 0, intent 0 and Tier 3. `core.route` gives them no SDR, with rule and queue `competitor_excluded`. `hubspot.wants_task` creates no task for them. The model's original output is kept in `score.llm_before_override`.
- **Why:** they are Pleo itself or its direct competitors, so they are never prospects. The human labeller set all four to 0 independently, which flagged the issue.
- **Prompts unchanged:** the hashes of `fit_intent_v1.md`, `fit_intent_v2a.md` and `label_draft_sonnet_v1.md` are as frozen above. The model was **not** re-run. The rule was applied to the recorded outputs with `scripts/apply_competitor_rule.py`.
- **Evaluation:** competitors are **excluded** from every accuracy metric (4 of the 40 eval companies, leaving n = 36), and `evaluate.py` reports `competitors_excluded`. The baseline, v1 and v2 runs are all evaluated the same way.
- **Side effect:** competitors no longer use SDR capacity, so DACH round-robin assignments shifted for 10 non-competitor accounts, and one overflow account (Solaris) is now routed. Tiers and scores of non-competitors are unchanged.
- **Changed files (new sha256):** `router/core.py` `96453778d0f01dce28cf3a145da430707fa652a2146593288e7cd3f12d6f4c88`, `router/run.py` `5a827ff8448ce20ccbd5d765249b0644c9212dcf4a16247c102e2469e8dff2b5`, `scripts/evaluate.py` `b38faab437efd1334e13a10981814970b6091551f5f51072ab65954886ac0cc4`, `data/competitors.json` `6d23567bbf80bc03e18611edaecfbc7e1dafccd28230a086ac8cc4b729a29e3f`.

### A2 — primary tier ground truth = author's gut tier (post-freeze, 2026-10-26 evening CET)
- **What:** the pre-registration defined gold tier as the router's tier rule applied to human fit/intent. The author also gave a holistic "gut" tier per company. The **primary** tier metric now uses the gut tier; the formula tier is still computed and reported as a secondary metric.
- **Why:** run through the formula, the author's own fit/intent give 18 Tier 1, while the gut call gives 8. Generic RevOps/sales hiring was scored as intent 2, against the stated rule. The gut tier is the sales judgement the tool exists to reproduce. Decided before computing any model-vs-label numbers.
- **Unchanged:** prompts, split, guards and tier rule. No model was re-run and no prompt was edited after seeing the labels.
- **Labels:** `eval/labels_reviewed.csv` (sha256 `7ff7252f077d550b9bb184238884d13a2c5c37729e56f30b346254920c163aa7`). Hand-labelled by the author. HeyJobs is flagged `bad_data` and kept.
- **Changed files (new sha256):** `scripts/evaluate.py` `406ce3563b25d4be80ff99c33414cdc84a94c7cfccbdfa5a4006974dc8a98f23` (adds gut_tier, confusion matrices, Tier-1 recall, exact-match and label self-consistency).

### A3 — classifier v3, post-hoc (frozen 2026-10-26 22:00 CET, before v3 scored any eval company)
- **Status: post-hoc.** v3 was designed after seeing v2's error patterns on the eval set (`eval/RESULTS.md`). Its eval numbers are therefore optimistic and are reported **next to**, never instead of, the preregistered v2 headline. n = 36, single labeller (the author).
- **What changed:** `prompts/fit_intent_v3.md` = v2a plus four rules (finance-ops hire is always `finance_hiring`; office/location lists are boilerplate; a bank's own treasury/trading desk is not a finance signal; selling into several named countries/regions is `finance_complexity`). Deterministic post-guard rules in `core.apply_v3_rules` (only for prompt versions `fit_intent_v3*`, lane ok/none): (a) drop `finance_hiring` signals whose posting title is not a finance role, or is a treasury/trading role, and cap scores at remaining evidence; (b) if any posting title matches the finance-ops classifier `core.FINOPS_TITLE` (accountant, controller, AP/AR, head of finance, payroll, procurement, ERP, consolidation, month-end; excluding FP&A, treasury, trading, risk, sales/account roles), intent is raised to at least 2. Tier rule unchanged.
- **Tuning:** one iteration, only on the 18 tune companies (`--split tune`, $0.08). Eval labels were not opened while building v3. Tune result: Tide (Senior Financial Controller) -> Tier 1, n8n (Accountant) intent 2; the title check dropped GoStudent's HR-based finance_hiring.
- **Frozen sha256:** `prompts/fit_intent_v3.md` `30ab76ccbf8c116508f330287d19998cad1f8446a421981dfc02b6c9e111e7f0`, `router/core.py` `76e84acfb35622e801d0bf68d1c13d3ac0cea2006fc7779f4c082ec7e2d41a9e`, `router/run.py` `44289bd740021295f8b011c901ffe9512dcdd5ee52ece3eb2455fb889ab9689a`, `scripts/evaluate.py` unchanged (`406ce356…`).
