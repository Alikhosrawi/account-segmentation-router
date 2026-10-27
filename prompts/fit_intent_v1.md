---
prompt_version: fit_intent_v1
model_default: claude-haiku-4-5
temperature: 0
---
You read up to three public job postings from ONE company and score it for a B2B spend-management product (company cards, expenses, invoices, reimbursements) sold to SMB and mid-market companies in Europe. Default to low scores. Only use what the postings EXPLICITLY say.

FIT (0-3): does the company look like a buyer?
- finance_complexity: several legal entities, currencies or countries; many cost centres; a finance/controlling team that is growing.
- distributed_spend: many employees spending company money (field teams, several offices, frequent travel, events).
- finance_tooling: names an ERP / accounting / spend tool the company uses (e.g. NetSuite, SAP, DATEV, Xero, Pleo, Spendesk).
INTENT (0-3): is now a good moment to reach out?
- finance_hiring: building or expanding finance, controlling, accounting or procurement.
- gtm_scaleup: building a new or expanding sales / revenue / RevOps team.
- new_market: entering a NAMED new country or region.
- tool_adoption: migrating to or rolling out a NAMED finance or GTM tool. Listing tools as required experience is NOT adoption.
Not signals: generic growth blurbs, mission statements, funding news, benefits, language requirements, normal backfill roles.

Each score above 0 must be backed by at least one signal. evidence_quote: copy ONE passage character for character from the cited posting, max 25 words, no "..." and no edits. posting_id must be one of the ids below. Max 5 signals.

Output ONLY JSON:
{"fit": 0, "intent": 0, "signals": [{"kind": "fit|intent", "signal_type": "...", "posting_id": "...", "evidence_quote": "...", "confidence": 0.0}], "prompt_version": "fit_intent_v1"}

Company: {{company}}
{{postings}}
