#!/usr/bin/env python3
"""Idempotent write-back of routed accounts to HubSpot (CRM v3). Stdlib only.

  python3 router/hubspot.py --accounts out/accounts.replay.fit_intent_v2a.jsonl --dry-run      # no network, prints plan
  python3 router/hubspot.py --accounts ... --live [--record fixtures/hubspot/recorded]          # needs env HUBSPOT_TOKEN

Idempotency
  - companies: batch upsert keyed on custom unique property `segr_domain_key` (= normalised domain);
    HubSpot's own `domain` is not unique, so it cannot be the upsert key.
  - tasks: one task per account. Its id is stored on the company (`segr_task_id`); reruns PATCH it, never duplicate.
  - properties / group: created only if missing.
The token is read from the environment and is never logged or written to fixtures.
"""
import argparse, json, os, sys, time, urllib.request, urllib.error, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
API = 'https://api.hubapi.com'
GROUP = dict(name='segmentation_router', label='Segmentation router', displayOrder=-1)
def _prop(name, label, type_, field, **kw): return dict(name=name, label=label, type=type_, fieldType=field, groupName=GROUP['name'], **kw)
PROPS = [
    _prop('segr_domain_key', 'Router domain key', 'string', 'text', hasUniqueValue=True),
    _prop('segr_segment', 'Segment', 'enumeration', 'select', options=[dict(label=x, value=x, displayOrder=i) for i, x in enumerate(['SMB', 'Mid-Market', 'Enterprise', 'Unknown'])]),
    _prop('segr_tier', 'Tier', 'number', 'number'),
    _prop('segr_fit_score', 'Fit score (0-3)', 'number', 'number'),
    _prop('segr_intent_score', 'Intent score (0-3)', 'number', 'number'),
    _prop('segr_evidence', 'Evidence (verbatim quotes + sources)', 'string', 'textarea'),
    _prop('segr_routed_sdr', 'Routed SDR', 'string', 'text'),
    _prop('segr_routing_rule', 'Routing rule', 'string', 'text'),
    _prop('segr_needs_human', 'Needs human review', 'enumeration', 'booleancheckbox', options=[dict(label='Yes', value='true', displayOrder=0), dict(label='No', value='false', displayOrder=1)]),
    _prop('segr_run_id', 'Router run id', 'string', 'text'),
    _prop('segr_task_id', 'Router task id', 'string', 'text'),
]

class HubSpotError(RuntimeError): pass

def live_transport(token, record_dir=None, sleep=time.sleep):
    n = [0]
    def call(method, path, body=None):
        req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r: st, raw = r.status, r.read()
                break
            except urllib.error.HTTPError as e:
                st, raw = e.code, e.read()
                if st in (429, 500, 502, 503, 504) and attempt < 3: sleep(2 ** attempt); continue
                break
        data = json.loads(raw) if raw else {}
        if record_dir:
            os.makedirs(record_dir, exist_ok=True); n[0] += 1
            json.dump(dict(method=method, path=path, body=body, status=st, response=data),
                      open(os.path.join(record_dir, f'{n[0]:03d}.json'), 'w'), indent=1, ensure_ascii=False)
        return st, data
    return call

class DryRun:
    """Answers nothing from the network: every read is treated as 'not there yet' so the plan shows the full first-run write set."""
    def __init__(self): self.plan = []
    def __call__(self, method, path, body=None):
        self.plan.append(dict(method=method, path=path, body=body))
        if method == 'GET' and path.startswith('/crm/v3/owners'): return 200, {'results': []}
        if method == 'GET': return 404, {}
        if '/batch/read' in path: return 200, {'results': []}
        if '/batch/upsert' in path: return 200, {'results': [dict(id=f'dry-{i}', properties=o['properties']) for i, o in enumerate(body['inputs'])]}
        if method == 'POST' and path == '/crm/v3/objects/tasks': return 201, {'id': f'dry-task-{len(self.plan)}'}
        return 200, {}

def _ok(st, data, what):
    if st not in (200, 201, 204, 207): raise HubSpotError(f'{what}: HTTP {st}: {str(data.get("message", ""))[:200]}')
    return data

def evidence_text(a, limit=60000):
    lines = [f'{s["signal_type"]} ({s["confidence"]:.2f}): "{s["evidence_quote"]}" {s.get("source_url", "")}' for s in a['score']['signals']]
    if a['score'].get('guard_flags'): lines.append('guard: ' + ', '.join(a['score']['guard_flags']))
    return '\n'.join(lines)[:limit]

def company_props(a, owner_id):
    p = dict(segr_domain_key=a['domain'], name=a['company'], domain=a['domain'], segr_segment=a['segment'], segr_tier=str(a['tier']),
             segr_fit_score=str(a['score']['fit']), segr_intent_score=str(a['score']['intent']), segr_evidence=evidence_text(a),
             segr_routed_sdr=a['sdr'].get('sdr_name') or a['sdr']['queue'], segr_routing_rule=a['sdr']['rule'],
             segr_needs_human='true' if a['score']['lane'] == 'needs_human' else 'false', segr_run_id=a['run_id'])
    if owner_id: p['hubspot_owner_id'] = owner_id
    return p

def wants_task(a): return not a.get('competitor') and a['tier'] in (1, 2) and a['score']['lane'] == 'ok' and a['sdr']['queue'] == 'assigned'

def task_props(a, owner_id, now):
    due = (now + datetime.timedelta(days=2 if a['tier'] == 1 else 5)).replace(microsecond=0)
    p = dict(hs_task_subject=f'Router: reach out to {a["company"]} (Tier {a["tier"]}, {a["segment"]})',
             hs_task_body=f'Routed to {a["sdr"]["sdr_name"]} by rule: {a["sdr"]["rule"]}.\n\nWhy now (verbatim from public job ads):\n' + evidence_text(a, 4000),
             hs_task_status='NOT_STARTED', hs_task_priority='HIGH' if a['tier'] == 1 else 'MEDIUM', hs_timestamp=due.strftime('%Y-%m-%dT%H:%M:%SZ'))
    if owner_id: p['hubspot_owner_id'] = owner_id
    return p

def sync(accounts, call, owner_map=None, default_owner_email=None, now=None):
    """Returns a summary dict. owner_map: sdr_id -> owner email."""
    now = now or datetime.datetime.now(datetime.timezone.utc); owner_map = owner_map or {}
    s = dict(group_created=False, properties_created=[], companies_upserted=0, tasks_created=0, tasks_updated=0, owners_unmapped=set())
    # 1. property group + properties (create if missing)
    st, _ = call('GET', f'/crm/v3/properties/companies/groups/{GROUP["name"]}')
    if st == 404: _ok(*call('POST', '/crm/v3/properties/companies/groups', GROUP), 'create group'); s['group_created'] = True
    for p in PROPS:
        st, _ = call('GET', f'/crm/v3/properties/companies/{p["name"]}')
        if st == 404: _ok(*call('POST', '/crm/v3/properties/companies', p), f'create property {p["name"]}'); s['properties_created'].append(p['name'])
        elif st != 200: raise HubSpotError(f'read property {p["name"]}: HTTP {st}')
    # 2. owners (email -> id)
    owners = {o.get('email', '').lower(): o['id'] for o in _ok(*call('GET', '/crm/v3/owners?limit=500'), 'list owners').get('results', [])}
    def owner_for(a):
        em = (owner_map.get(a['sdr'].get('sdr_id')) or default_owner_email or '').lower()
        if a['sdr'].get('sdr_id') and not owners.get(em): s['owners_unmapped'].add(a['sdr']['sdr_id'])
        return owners.get(em)
    # 3. existing task ids on companies
    existing = {}
    for i in range(0, len(accounts), 100):
        chunk = accounts[i:i + 100]
        d = _ok(*call('POST', '/crm/v3/objects/companies/batch/read', dict(idProperty='segr_domain_key', properties=['segr_domain_key', 'segr_task_id'], inputs=[dict(id=a['domain']) for a in chunk])), 'read companies')
        for r in d.get('results', []): existing[r['properties'].get('segr_domain_key')] = (r['id'], r['properties'].get('segr_task_id'))
    # 4. upsert companies
    ids = {}
    for i in range(0, len(accounts), 100):
        chunk = accounts[i:i + 100]
        d = _ok(*call('POST', '/crm/v3/objects/companies/batch/upsert?idProperty=segr_domain_key',
                      dict(inputs=[dict(idProperty='segr_domain_key', id=a['domain'], properties=company_props(a, owner_for(a))) for a in chunk])), 'upsert companies')
        for r in d.get('results', []): ids[r['properties'].get('segr_domain_key')] = r['id']
        s['companies_upserted'] += len(d.get('results', []))
    # 5. one task per Tier 1/2 routed account
    for a in accounts:
        if not wants_task(a) or a['domain'] not in ids: continue
        props = task_props(a, owner_for(a), now); tid = (existing.get(a['domain']) or (None, None))[1]
        if tid:
            st, _ = call('PATCH', f'/crm/v3/objects/tasks/{tid}', dict(properties=props))
            if st == 200: s['tasks_updated'] += 1; continue
            if st != 404: raise HubSpotError(f'update task {tid}: HTTP {st}')
        d = _ok(*call('POST', '/crm/v3/objects/tasks', dict(properties=props, associations=[dict(to=dict(id=ids[a['domain']]), types=[dict(associationCategory='HUBSPOT_DEFINED', associationTypeId=192)])])), 'create task')
        _ok(*call('PATCH', f'/crm/v3/objects/companies/{ids[a["domain"]]}', dict(properties=dict(segr_task_id=d['id']))), 'store task id')
        s['tasks_created'] += 1
    s['owners_unmapped'] = sorted(s['owners_unmapped'])
    return s

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--accounts', required=True)
    g = ap.add_mutually_exclusive_group(required=True); g.add_argument('--dry-run', action='store_true'); g.add_argument('--live', action='store_true')
    ap.add_argument('--owner-map', help='JSON file {sdr_id: owner_email}')
    ap.add_argument('--default-owner-email', help='HubSpot user who owns records when an SDR has no HubSpot user (demo portals)')
    ap.add_argument('--record', help='live: write request/response pairs here (token never included)')
    a = ap.parse_args(argv)
    accts = [json.loads(l) for l in open(a.accounts) if l.strip()]
    om = json.load(open(a.owner_map)) if a.owner_map else {}
    if a.dry_run:
        dr = DryRun(); s = sync(accts, dr, om, a.default_owner_email)
        print(json.dumps(dict(mode='dry-run', requests=len(dr.plan), **s), indent=1))
        for r in dr.plan[:3] + dr.plan[-2:]: print(r['method'], r['path'])
        return s
    tok = os.environ.get('HUBSPOT_TOKEN')
    if not tok: sys.exit('HUBSPOT_TOKEN is not set; use --dry-run')
    s = sync(accts, live_transport(tok, a.record), om, a.default_owner_email)
    print(json.dumps(dict(mode='live', **s), indent=1)); return s
if __name__ == '__main__': main()
