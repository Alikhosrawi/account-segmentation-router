"""Apply the deterministic competitor rule to recorded run output without calling the LLM.
Usage: python3 scripts/apply_competitor_rule.py out/accounts.replay.fit_intent_v2a.jsonl [...]  (rewrites in place, re-routes)"""
import json, sys, os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); sys.path.insert(0, os.path.join(ROOT, 'router'))
import core
def apply(path, roster_path=os.path.join(ROOT, 'data/sdrs.SYNTHETIC.json')):
    accts = [json.loads(l) for l in open(path) if l.strip()]; comps = core.load_competitors()
    before = {a['domain']: (a['sdr']['sdr_id'], a['sdr']['queue']) for a in accts}
    for a in accts: core.apply_competitor_rule(a, comps)
    core.route(accts, json.load(open(roster_path))['sdrs'])
    with open(path, 'w') as fo:
        for x in sorted(accts, key=lambda x: (x['tier'], x['domain'])): fo.write(json.dumps(x, ensure_ascii=False) + '\n')
    moved = sorted(a['domain'] for a in accts if not a.get('competitor') and before[a['domain']] != (a['sdr']['sdr_id'], a['sdr']['queue']))
    return dict(file=os.path.basename(path), competitors=sorted(a['domain'] for a in accts if a.get('competitor')), other_accounts_rerouted=moved)
if __name__ == '__main__':
    for f in sys.argv[1:]: print(json.dumps(apply(f)))
