"""Score runs against the human-reviewed labels. Usage: python3 scripts/evaluate.py eval/labels_reviewed.csv out/accounts.*.eval.jsonl
labels csv needs: domain, draft_fit, draft_intent, ali_fit, ali_intent (ali_* blank = agrees with draft).
Optional gut_tier column (amendment A2): if present it is the primary tier ground truth; formula_tier is always
derived from fit/intent with core.tier and reported as a secondary view."""
import csv, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'router'))
import core
def gold(path):
    g = {}
    for r in csv.DictReader(open(path)):
        if not r.get('domain'): continue
        f = int(r['ali_fit']) if (r.get('ali_fit') or '').strip() else int(r['draft_fit'])
        i = int(r['ali_intent']) if (r.get('ali_intent') or '').strip() else int(r['draft_intent'])
        ft = core.tier(dict(fit=f, intent=i, lane='ok', signals=[]))[0]
        gut = int(r['gut_tier']) if (r.get('gut_tier') or '').strip() else None
        g[r['domain']] = dict(fit=f, intent=i, tier=gut if gut else ft, formula_tier=ft, gut_tier=gut,
                              bad_data=bool((r.get('bad_data') or '').strip()),
                              changed=bool((r.get('ali_fit') or '').strip() or (r.get('ali_intent') or '').strip()))
    return g
def _tier_stats(pairs, prefix=''):
    n = len(pairs); cm = {f'{t}': {f'{p}': sum(1 for x, y in pairs if x == t and y == p) for p in (1, 2, 3)} for t in (1, 2, 3)}
    pp = [x for x, y in pairs if y == 1]; tp = [y for x, y in pairs if x == 1]
    return {prefix + 'tier_accuracy': round(sum(x == y for x, y in pairs) / n, 3),
            prefix + 'confusion_true_by_pred': cm,
            prefix + 'tier1_precision': round(sum(x == 1 for x in pp) / len(pp), 3) if pp else None,
            prefix + 'tier1_recall': round(sum(y == 1 for y in tp) / len(tp), 3) if tp else None,
            prefix + 'tier1_predicted': len(pp), prefix + 'tier1_gold': len(tp)}
def evaluate(g, accts, competitors=None):
    """Competitors (data/competitors.json) are excluded: their output is a fixed rule, not a model judgement."""
    comps = core.load_competitors() if competitors is None else competitors
    inlab = [a for a in accts if a['domain'] in g]
    excl = sorted(a['domain'] for a in inlab if core.norm_domain(a['domain']) in comps)
    rows = [(g[a['domain']], a) for a in inlab if core.norm_domain(a['domain']) not in comps]
    n = len(rows)
    if not n: return dict(n=0, competitors_excluded=len(excl))
    nh = sum(1 for _, a in rows if a['score']['lane'] == 'needs_human')
    out = dict(n=n, **_tier_stats([(x['tier'], a['tier']) for x, a in rows]))
    if all('formula_tier' in x for x, _ in rows):
        out.update(_tier_stats([(x['formula_tier'], a['tier']) for x, a in rows], 'formula_'))
    out.update(fit_exact=round(sum(x['fit'] == a['score']['fit'] for x, a in rows) / n, 3),
               fit_within1=round(sum(abs(x['fit'] - a['score']['fit']) <= 1 for x, a in rows) / n, 3),
               intent_exact=round(sum(x['intent'] == a['score']['intent'] for x, a in rows) / n, 3),
               intent_within1=round(sum(abs(x['intent'] - a['score']['intent']) <= 1 for x, a in rows) / n, 3),
               needs_human_rate=round(nh / n, 3), needs_human=nh,
               competitors_excluded=len(excl), competitors_excluded_domains=excl)
    return out
def reviewer_consistency(g, competitors=None):
    """Author gut tier vs the formula tier from author fit/intent (non-competitors)."""
    comps = core.load_competitors() if competitors is None else competitors
    r = [x for d, x in g.items() if core.norm_domain(d) not in comps and x.get('gut_tier')]
    if not r: return {}
    return dict(n=len(r), **_tier_stats([(x['gut_tier'], x['formula_tier']) for x in r], 'formula_vs_gut_'))
if __name__ == '__main__':
    g = gold(sys.argv[1]); print(json.dumps(dict(labels=len(g), changed_by_human=sum(x['changed'] for x in g.values()), reviewer_consistency=reviewer_consistency(g))))
    for f in sys.argv[2:]: print(os.path.basename(f), json.dumps(evaluate(g, [json.loads(l) for l in open(f)])))
