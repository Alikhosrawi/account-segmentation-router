---
prompt_version: fit_intent_v3
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

RULES FOR SCORES
- fit = number of DIFFERENT fit signal types you found (0-3). intent = number of DIFFERENT intent signal types you found (0-3). A score can never be higher than the evidence you list.
- A fit signal_type (finance_complexity, distributed_spend, finance_tooling) can only support fit; an intent signal_type (finance_hiring, gtm_scaleup, new_market, tool_adoption) can only support intent.
- gtm_scaleup ONLY when the text says the sales / revenue / RevOps TEAM or FUNCTION itself is new, being built, or being expanded ("build our first SDR team", "we are doubling the AE team"). A normal sales job description, a backfill, or a marketing / product-marketing team is NOT gtm_scaleup.
- Sentences describing the company's OWN product or customers (what it sells) are not evidence of fit. Use only facts about how the company itself operates (its entities, countries, finance team, tools it uses internally, staff who travel or spend).
- Each quote can support only ONE signal.
- If you would give a signal confidence below 0.6, leave it out.
- finance_hiring means the hiring is FOR finance, accounting, controlling, procurement or payroll. HR / people roles are not finance_hiring.
- A finance-operations hire (accountant, controller, accounts payable, head of finance, month-end close / consolidation, ERP change, procurement or spend governance) is a CLEAR buying signal: always list it as finance_hiring, quoting the posting text.
- Office or location lists ("offices in Berlin, London and Paris", "we have 12 locations", "75 nationalities") are boilerplate: they are NOT finance_complexity, distributed_spend or finance_hiring.
- A bank's or fintech's own treasury, trading, risk or capital-markets desk is part of its product, NOT finance_hiring or finance_complexity.
- Selling to customers in several NAMED countries or regions (e.g. "customers across DACH, France and the Nordics", a role covering UK and Benelux) IS finance_complexity: the company operates in several markets.

RULES FOR QUOTES (a computer checks every quote; one wrong character sends the company to manual review)
- Copy from the "Text:" part of ONE posting. Do not quote the Title or Location lines.
- Copy ONE continuous stretch of 6 to 20 words, exactly as written: same words, same order, nothing skipped or added (keep small words like "our", "the"). Do not join two sentences. Do not fix typos or translate.
- If you cannot copy an exact passage, leave that signal out and lower the score.
- posting_id must be the id of the posting you copied from. Max 5 signals.

Output ONLY JSON:
{"fit": 0, "intent": 0, "signals": [{"kind": "fit|intent", "signal_type": "...", "posting_id": "...", "evidence_quote": "...", "confidence": 0.0}], "prompt_version": "fit_intent_v3"}

Company: {{company}}
{{postings}}
