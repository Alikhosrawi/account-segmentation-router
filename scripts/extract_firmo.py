"""Extract headcount band + HQ country from saved public web-search results (private folder) with claude-haiku-4-5.
Guard: each value needs a quote that appears verbatim in the cited result; else 'unknown'. Writes data/firmographics.csv."""
import json, os, sys, csv, re, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'router'))
import core, run
R = core.ROOT; SRC = os.path.join(R, '..', '_segr_private', 'firmo_search'); REP = os.path.join(R, '..', '_segr_private', 'firmo_replay')
os.makedirs(REP, exist_ok=True)
BANDS = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1001-5000', '5001-10000', '10001+']
def band_of(n):
    for b, hi in zip(BANDS, [10, 50, 200, 500, 1000, 5000, 10000, 10**9]):
        if n <= hi: return b
PROMPT = """From the web search results below about the company {company} (website {domain}), extract:
1. employees: the most recent explicit employee count or LinkedIn "Company size" band FOR THIS COMPANY (not another company with a similar name).
2. hq_country: ISO-2 country of its headquarters.
For each, copy a short quote character for character from ONE result and give that result's index. If the results do not state it for this company, use null.
Output ONLY JSON: {{"employees": {{"value": "e.g. 501-1,000 or 950", "quote": "...", "result": 0}} or null, "hq_country": {{"value": "DE", "quote": "...", "result": 0}} or null}}

{results}"""
def load(d):
    s = open(os.path.join(SRC, d + '.txt')).read(); s = s[s.index('{'):s.rindex('}') + 1]
    out = []
    for w in json.loads(s)['results']['web'][:5]:
        txt = (w.get('title') or '') + '\n' + (w.get('description') or '') + '\n' + '\n'.join((w.get('contents') or {}).get('highlights') or [])
        out.append(dict(url=w['url'], text=re.sub(r'[*\\#]', '', txt)[:2500]))  # strip markdown so quotes compare on text
    return out
def to_band(v):
    v = v.replace(',', '').replace('.', '') if re.fullmatch(r'[\d,.\s+~-]+(employees)?', v.strip(), re.I) or 'employee' in v.lower() else v.replace(',', '')
    m = re.search(r'(\d+)\s*-\s*(\d+)', v)
    if m: return band_of(int(m.group(2)))
    m = re.search(r'(\d+)', v)
    return band_of(int(m.group(1))) if m else None
def main():
    rows = list(csv.DictReader(open(os.path.join(R, 'data/companies.csv')))); tok = [0, 0]; out = []
    for c in rows:
        res = load(c['domain']); f = os.path.join(REP, c['domain'] + '.json')
        if os.path.exists(f): text = json.load(open(f))['reply']
        else:
            body = '\n\n'.join(f'[result {i}] {r["url"]}\n{r["text"]}' for i, r in enumerate(res))
            text, u = run.call_live(PROMPT.format(company=c['company'], domain=c['domain'], results=body), 'claude-haiku-4-5')
            tok[0] += u.get('input_tokens', 0); tok[1] += u.get('output_tokens', 0)
            json.dump(dict(domain=c['domain'], usage=u, reply=text), open(f, 'w'), ensure_ascii=False)
        j = core.parse_model_json(text) or {}
        rec = dict(domain=c['domain'])
        for k in ('employees', 'hq_country'):
            x = j.get(k); ok = isinstance(x, dict) and isinstance(x.get('result'), int) and 0 <= x['result'] < len(res) and x.get('value') and core.quote_is_verbatim(re.sub(r'[*\\#]', '', x.get('quote', '')), res[x['result']]['text'])
            rec[k] = str(x['value']) if ok else ''; rec[k + '_quote'] = x.get('quote', '') if ok else ''; rec[k + '_source'] = res[x['result']]['url'] if ok else ''
        rec['headcount_band'] = (to_band(rec['employees']) if rec['employees'] else None) or 'unknown'
        out.append(rec)
    with open(os.path.join(R, 'data/firmographics.csv'), 'w', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print('tokens', tok, 'usd', round(tok[0] * 1e-6 + tok[1] * 5e-6, 4))
    for r in out: print(r['domain'], '|', r['employees'], '->', r['headcount_band'], '|', r['hq_country'], '|', r['employees_source'][:50])
if __name__ == '__main__': main()
