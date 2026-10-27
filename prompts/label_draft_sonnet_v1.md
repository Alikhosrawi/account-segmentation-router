---
prompt_version: label_draft_v1
model_default: claude-sonnet-4-6
temperature: 0
---
You are drafting GROUND-TRUTH labels that a human will check. You did not see any classifier output. Read up to three public job postings from ONE company and judge it as a prospect for a B2B spend-management product (company cards, expenses, invoices) sold in Europe.

fit (0-3): how clearly do the postings show a likely buyer? Evidence: several entities/countries/currencies, a finance or controlling team, many employees spending (field teams, offices, travel), finance/ERP tools in use. 0 = postings show nothing, 3 = several strong, explicit indicators.
intent (0-3): how clearly do the postings show a good moment now? Evidence: building/expanding finance, controlling or procurement; building/expanding sales or RevOps; entering a NAMED new country; migrating to a named finance or sales tool. Generic growth language, backfills, mission text and required-experience tool lists do not count. 0 = none, 3 = several explicit indicators.
Be conservative: only what the text explicitly says.

Output ONLY JSON: {"fit": 0, "intent": 0, "reason": "one plain-English sentence, max 30 words, naming the key evidence", "key_quote": "short passage copied exactly from a posting, or empty"}

Company: {{company}}
{{postings}}
