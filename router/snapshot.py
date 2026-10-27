#!/usr/bin/env python3
"""Fetch public boards for companies.csv -> data/snapshot/postings.jsonl (picked postings) + board_status.csv. Read-only."""
import csv, json, os, sys, argparse, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ats_fetch as A, core
F = {'ashby': A.ash, 'greenhouse': A.ghf, 'lever': A.lev}
def to_posting(j, c):
    return dict(posting_id=f"{j['src']}:{j['co']}:{j['id']}", company=c['company'], domain=c['domain'], title=j['title'] or '',
                location=j['loc'] or '', posted=j.get('posted') or '', source_url=j['url'] or '', plain_text=j['desc'] or '')
def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--companies', default=os.path.join(core.ROOT, 'data/companies.csv'))
    ap.add_argument('--k', type=int, default=3); ap.add_argument('--out', default=os.path.dirname(core.SNAPSHOT))
    a = ap.parse_args(argv); cos = core.dedupe_companies(list(csv.DictReader(open(a.companies))))
    os.makedirs(a.out, exist_ok=True)
    with cf.ThreadPoolExecutor(10) as ex: res = list(ex.map(lambda c: (c, F[c['ats']](c['board_slug'])), cos))
    with open(os.path.join(a.out, 'postings.jsonl'), 'w') as f, open(os.path.join(a.out, 'board_status.csv'), 'w') as g:
        g.write('domain,ats,board_slug,status,postings\n')
        for c, (_, st, js) in res:
            g.write(f"{c['domain']},{c['ats']},{c['board_slug']},{st},{len(js)}\n")
            for p in core.pick_postings([to_posting(j, c) for j in js], a.k): f.write(json.dumps(p, ensure_ascii=False) + '\n')
    print(sum(1 for _, (_, st, js) in res if st == 200 and js), 'of', len(cos), 'boards fetched')
if __name__ == '__main__': main()
