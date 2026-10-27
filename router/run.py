#!/usr/bin/env python3
"""Score (replay|live) -> guard -> segment -> tier -> route -> out/accounts.<mode>.jsonl + summary.
  --mode replay : data/replay/<domain>.json (raw model reply); no key needed
  --mode live   : Anthropic Messages API, key from env ANTHROPIC_API_KEY (never logged); --save-replay records replies
"""
import argparse, csv, json, os, sys, datetime, urllib.request, urllib.error, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
ROOT = core.ROOT; MAX_CHARS = 2500
PRICE = {'claude-haiku-4-5': (1.0, 5.0)}  # USD per 1M input / output tokens
def render(tpl, company, posts):
    body = tpl.split('---', 2)[2].strip()
    blocks = '\n\n'.join(f"[posting_id: {p['posting_id']}]\nTitle: {p['title']}\nLocation: {p['location']}\nText:\n{p['plain_text'][:MAX_CHARS]}" for p in posts)
    return body.replace('{{company}}', company).replace('{{postings}}', blocks)
def prompt_version(tpl): return re.search(r'prompt_version:\s*(\S+)', tpl).group(1)
def call_live(prompt, model):
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', method='POST',
        headers={'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        data=json.dumps({'model': model, 'max_tokens': 700, 'temperature': 0, 'messages': [{'role': 'user', 'content': prompt}]}).encode())
    for attempt in range(3):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=90).read())
            return ''.join(c.get('text', '') for c in d.get('content', [])), d.get('usage', {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 529) and attempt < 2: time.sleep(5 * (attempt + 1)); continue
            raise RuntimeError(f'Anthropic HTTP {e.code}') from None
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['replay', 'live', 'baseline'], default='replay')
    ap.add_argument('--companies', default=os.path.join(ROOT, 'data/companies.csv'))
    ap.add_argument('--postings', default=core.SNAPSHOT)
    ap.add_argument('--prompt', default=os.path.join(ROOT, 'prompts/fit_intent_v1.md'))
    ap.add_argument('--roster', default=os.path.join(ROOT, 'data/sdrs.SYNTHETIC.json'))
    ap.add_argument('--replay-dir', help='default data/replay/<prompt_version>')
    ap.add_argument('--model', default='claude-haiku-4-5'); ap.add_argument('--domains', help='comma list to restrict'); ap.add_argument('--split', choices=['eval', 'tune'])
    ap.add_argument('--limit', type=int); ap.add_argument('--save-replay', action='store_true'); ap.add_argument('--force', action='store_true', help='live: re-call even if a replay exists')
    ap.add_argument('--competitors', default=os.path.join(ROOT, 'data/competitors.json'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'out'))
    a = ap.parse_args(argv)
    tpl = open(a.prompt).read(); pv = 'baseline_kw_v1' if a.mode == 'baseline' else prompt_version(tpl); a.replay_dir = a.replay_dir or os.path.join(ROOT, 'data/replay', pv); schema = core.load_schema('score.schema.json')
    cos = core.dedupe_companies(list(csv.DictReader(open(a.companies))))
    if a.domains: keep = {core.norm_domain(d) for d in a.domains.split(',')}; cos = [c for c in cos if c['domain'] in keep]
    if a.split: keep = set(json.load(open(os.path.join(ROOT, 'eval/split.json')))[a.split]); cos = [c for c in cos if c['domain'] in keep]
    cos = cos[:a.limit]
    posts = {}
    for l in open(a.postings):
        if l.strip(): p = json.loads(l); posts.setdefault(core.norm_domain(p['domain']), []).append(p)
    run_id = f"{a.mode}-{pv}-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    tok = {'input_tokens': 0, 'output_tokens': 0}; accts, missing = [], []
    os.makedirs(a.replay_dir, exist_ok=True)
    for c in cos:
        ps = posts.get(c['domain'], []); f = os.path.join(a.replay_dir, c['domain'] + '.json')
        if a.mode == 'baseline': text = json.dumps(core.baseline_score(ps))
        elif a.mode == 'live' and os.path.exists(f) and not a.force:
            text = json.load(open(f))['reply']  # already recorded for this prompt version: do not pay twice
        elif a.mode == 'live':
            text, usage = call_live(render(tpl, c['company'], ps), a.model)
            for k in tok: tok[k] += usage.get(k, 0)
            if a.save_replay:
                json.dump(dict(domain=c['domain'], model=a.model, temperature=0, prompt_version=pv, posting_ids=[p['posting_id'] for p in ps], usage=usage, reply=text),
                          open(f, 'w'), ensure_ascii=False, indent=1)
        else:
            if not os.path.exists(f): missing.append(c['domain']); continue
            text = json.load(open(f))['reply']
        cls = core.parse_model_json(text)
        if isinstance(cls, dict) and 'prompt_version' not in cls: cls['prompt_version'] = pv
        score = core.guard(cls, {p['posting_id']: p for p in ps}, schema)
        if pv.startswith('fit_intent_v3'): core.apply_v3_rules(score, ps)
        seg = core.segment(c['headcount_band']); t, reasons = core.tier(score)
        reasons += score.get('v3_rules', [])
        src = {p['posting_id']: p['source_url'] for p in ps}
        for s in score['signals']: s['source_url'] = src.get(s['posting_id'], '')
        accts.append(dict(account_id=core.account_id(c['domain']), company=c['company'], domain=c['domain'],
                          territory=c['territory'], headcount_band=c['headcount_band'], headcount_source=c['headcount_source'], hq_country=c['hq_country'],
                          segment=seg, tier=t, tier_reasons=reasons, score=score, run_id=run_id))
    comps = core.load_competitors(a.competitors)
    for x in accts: core.apply_competitor_rule(x, comps)
    core.route(accts, json.load(open(a.roster))['sdrs'])
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, f'accounts.{a.mode}.{pv}' + (f'.{a.split}' if a.split else '') + '.jsonl'), 'w') as fo:
        for x in sorted(accts, key=lambda x: (x['tier'], x['domain'])): fo.write(json.dumps(x, ensure_ascii=False) + '\n')
    pin, pout = PRICE.get(a.model, (0, 0))
    summ = dict(run_id=run_id, companies=len(cos), scored=len(accts), missing_replay=missing,
                competitors_excluded=sum(1 for x in accts if x.get('competitor')),
                lanes={l: sum(1 for x in accts if x['score']['lane'] == l) for l in ('ok', 'none', 'needs_human')},
                tiers={t: sum(1 for x in accts if x['tier'] == t) for t in (1, 2, 3)},
                queues={q: sum(1 for x in accts if x['sdr']['queue'] == q) for q in ('assigned', 'overflow', 'needs_human')},
                tokens=tok, est_cost_usd=round(tok['input_tokens'] / 1e6 * pin + tok['output_tokens'] / 1e6 * pout, 4))
    print(json.dumps(summ)); return summ
if __name__ == '__main__': main()
