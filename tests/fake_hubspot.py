"""Small stateful stand-in for the HubSpot CRM v3 endpoints router/hubspot.py uses. Response shapes follow fixtures/hubspot."""
import json, os, re, itertools
FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'hubspot')
class FakeHubSpot:
    def __init__(self, status_override=None):
        self.groups, self.props, self.companies, self.tasks, self.log = set(), {}, {}, {}, []
        self.ids = itertools.count(100); self.owners = json.load(open(os.path.join(FX, 'owners.json'))); self.status_override = status_override or {}
    def __call__(self, method, path, body=None):
        self.log.append((method, path))
        for pat, st in self.status_override.items():
            if re.search(pat, f'{method} {path}'): return st, {'message': 'forced'}
        m = re.fullmatch(r'/crm/v3/properties/companies/groups/(\w+)', path)
        if method == 'GET' and m: return (200, {}) if m.group(1) in self.groups else (404, {})
        if method == 'POST' and path == '/crm/v3/properties/companies/groups': self.groups.add(body['name']); return 201, body
        m = re.fullmatch(r'/crm/v3/properties/companies/(\w+)', path)
        if method == 'GET' and m: return (200, self.props[m.group(1)]) if m.group(1) in self.props else (404, {})
        if method == 'POST' and path == '/crm/v3/properties/companies':
            if body['name'] in self.props: return 409, {'message': 'exists'}
            self.props[body['name']] = body; return 201, body
        if method == 'GET' and path.startswith('/crm/v3/owners'): return 200, self.owners
        if path == '/crm/v3/objects/companies/batch/read':
            res = [dict(id=c['id'], properties={k: c['properties'].get(k) for k in body['properties']}) for c in self.companies.values() if c['properties']['segr_domain_key'] in {i['id'] for i in body['inputs']}]
            return (207 if len(res) < len(body['inputs']) else 200), {'results': res}
        if path.startswith('/crm/v3/objects/companies/batch/upsert'):
            assert 'idProperty=segr_domain_key' in path and 'segr_domain_key' in self.props, 'unique property must exist first'
            out = []
            for i in body['inputs']:
                c = self.companies.get(i['id'])
                if c: c['properties'].update(i['properties']); new = False
                else: c = self.companies[i['id']] = dict(id=str(next(self.ids)), properties=dict(i['properties'])); new = True
                out.append(dict(id=c['id'], properties=dict(c['properties']), new=new))
            return 200, {'status': 'COMPLETE', 'results': out}
        m = re.fullmatch(r'/crm/v3/objects/companies/(\d+)', path)
        if method == 'PATCH' and m:
            c = next(c for c in self.companies.values() if c['id'] == m.group(1)); c['properties'].update(body['properties']); return 200, c
        if method == 'POST' and path == '/crm/v3/objects/tasks':
            tid = str(next(self.ids)); self.tasks[tid] = dict(id=tid, **body); return 201, dict(id=tid, properties=body['properties'])
        m = re.fullmatch(r'/crm/v3/objects/tasks/(\d+)', path)
        if method == 'PATCH' and m:
            if m.group(1) not in self.tasks: return 404, {'message': 'not found'}
            self.tasks[m.group(1)]['properties'].update(body['properties']); return 200, self.tasks[m.group(1)]
        return 400, {'message': f'unhandled {method} {path}'}
