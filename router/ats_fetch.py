"""Read-only fetchers for public ATS job-board APIs (Greenhouse, Ashby, Lever). Stdlib only."""
import json, re, datetime, urllib.request, urllib.error, html
UA = {'User-Agent': 'Mozilla/5.0 (hiring-signal-scorer demo, read-only)'}
def get(url):
    try:
        r=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30); return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, b''
    except Exception as e: return str(e)[:40], b''
def clean(s): return re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',html.unescape(s or ''))).strip()
def ash(s):
    c,b=get(f"https://api.ashbyhq.com/posting-api/job-board/{s}?includeCompensation=true"); out=[]
    if c==200:
        try: d=json.loads(b)
        except: return s,'badjson',[]
        for j in d.get('jobs',[]):
            locs=[j.get('location') or '']+[x.get('location','') for x in (j.get('secondaryLocations') or [])]
            pa=((j.get('address') or {}).get('postalAddress') or {})
            comp=(j.get('compensation') or {}).get('compensationTierSummary') or ''
            out.append(dict(src='ashby',co=s,id=j.get('id'),title=j.get('title'),loc=' / '.join(l for l in locs if l)+(' |'+pa.get('addressCountry','') if pa.get('addressCountry') else ''),remote=j.get('isRemote'),wp=j.get('workplaceType') or '',posted=(j.get('publishedAt') or '')[:10],url=j.get('jobUrl'),comp=comp,emp=j.get('employmentType') or '',dept=j.get('department') or '',desc=j.get('descriptionPlain') or clean(j.get('descriptionHtml'))))
    return s,c,out
def ghf(s):
    c,b=get(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs?content=true"); out=[]
    if c==200:
        d=json.loads(b)
        for j in d.get('jobs',[]):
            out.append(dict(src='greenhouse',co=s,id=str(j.get('id')),title=j.get('title'),loc=(j.get('location') or {}).get('name',''),remote=None,wp='',posted=(j.get('first_published') or j.get('updated_at') or '')[:10],updated=(j.get('updated_at') or '')[:10],url=j.get('absolute_url'),comp='',emp='',dept=', '.join(x.get('name','') for x in j.get('departments') or []),desc=clean(j.get('content'))))
    return s,c,out
def lev(s):
    c,b=get(f"https://api.lever.co/v0/postings/{s}?mode=json"); out=[]
    if c==200:
        try: d=json.loads(b)
        except: return s,'badjson',[]
        for j in d:
            cat=j.get('categories') or {}
            desc=clean(j.get('description'))+' '+' '.join(clean(x.get('text'))+': '+clean(x.get('content')) for x in j.get('lists') or [])+' '+clean(j.get('additional'))
            out.append(dict(src='lever',co=s,id=j.get('id'),title=j.get('text'),loc=cat.get('location','')+' / '+' / '.join(cat.get('allLocations') or []),remote=None,wp=j.get('workplaceType') or '',posted=datetime.datetime.fromtimestamp((j.get('createdAt') or 0)/1000).strftime('%Y-%m-%d'),url=j.get('hostedUrl'),comp=str(j.get('salaryRange') or ''),emp=cat.get('commitment',''),dept=cat.get('team',''),desc=desc))
    return s,c,out
