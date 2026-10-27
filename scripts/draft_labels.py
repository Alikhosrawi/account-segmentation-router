"""Draft eval labels with claude-sonnet-4-6 (independent of the classifier prompt). Records raw replies to eval/label_drafts/."""
import json, os, sys, csv
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'router'))
import core, run
R = core.ROOT; tpl = open(os.path.join(R, 'prompts/label_draft_sonnet_v1.md')).read()
ev = json.load(open(os.path.join(R, 'eval/split.json')))['eval']
cos = {c['domain']: c for c in csv.DictReader(open(os.path.join(R, 'data/companies.csv')))}
posts = {}
for l in open(core.SNAPSHOT): p = json.loads(l); posts.setdefault(p['domain'], []).append(p)
od = os.path.join(R, 'eval/label_drafts'); os.makedirs(od, exist_ok=True); tok = [0, 0]
for d in ev:
    f = os.path.join(od, d + '.json')
    if os.path.exists(f): continue
    text, u = run.call_live(run.render(tpl, cos[d]['company'], posts.get(d, [])), 'claude-sonnet-4-6')
    tok[0] += u.get('input_tokens', 0); tok[1] += u.get('output_tokens', 0)
    json.dump(dict(domain=d, model='claude-sonnet-4-6', temperature=0, usage=u, reply=text), open(f, 'w'), ensure_ascii=False, indent=1)
print('tokens', tok, 'usd', round(tok[0] * 3e-6 + tok[1] * 15e-6, 4))
