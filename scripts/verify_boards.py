"""Verify each candidate public ATS board fetches (HTTP 200, >=1 posting). Read-only."""
import sys, os, json, concurrent.futures as cf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'router'))
import ats_fetch as A
F = {'ashby': A.ash, 'greenhouse': A.ghf, 'lever': A.lev}
rows = [l.split(' ', 2)[:2] + [l.split(' ', 2)[2]] for l in open(sys.argv[1]).read().splitlines() if l.strip()]
def chk(r):
    ats, slug, rest = r; s, c, out = F[ats](slug); return r, c, len(out)
with cf.ThreadPoolExecutor(12) as ex:
    for r, c, n in ex.map(chk, rows): print(json.dumps(dict(ats=r[0], slug=r[1], rest=r[2], status=c, postings=n)))
