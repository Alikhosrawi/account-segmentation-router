import unittest, sys, os, json, datetime, tempfile, io, contextlib, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'router')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hubspot as H
from fake_hubspot import FakeHubSpot
NOW = datetime.datetime(2026, 10, 26, 10, 0, tzinfo=datetime.timezone.utc)
def acct(d, tier=2, lane='ok', queue='assigned', sdr='sdr_01'):
    return dict(account_id='acc_' + d, company=d.split('.')[0].title(), domain=d, segment='Mid-Market', tier=tier, run_id='r1', territory='DACH',
                score=dict(fit=1, intent=1, lane=lane, guard_flags=[], signals=[dict(kind='fit', signal_type='finance_complexity', posting_id='p', evidence_quote='across 5 entities', confidence=0.9, source_url='https://x')]),
                sdr=dict(sdr_id=sdr if queue == 'assigned' else '', sdr_name='SDR A' if queue == 'assigned' else '', rule='DACH/Mid-Market round-robin', queue=queue))
ACC = [acct('a.com', 1), acct('b.com', 2), acct('c.com', 3), acct('d.com', 2, lane='needs_human', queue='needs_human'), acct('e.com', 2, queue='overflow')]
class Sync(unittest.TestCase):
    def test_first_run_creates_everything(self):
        f = FakeHubSpot(); s = H.sync(ACC, f, {'sdr_01': 'sdr.a@example.com'}, now=NOW)
        self.assertTrue(s['group_created']); self.assertEqual(len(s['properties_created']), len(H.PROPS))
        self.assertEqual(s['companies_upserted'], 5); self.assertEqual(s['tasks_created'], 2)   # only Tier 1/2, ok, assigned
        self.assertEqual(f.companies['a.com']['properties']['hubspot_owner_id'], '9001')
        self.assertEqual(f.companies['d.com']['properties']['segr_needs_human'], 'true')
        t = next(iter(f.tasks.values())); self.assertEqual(t['associations'][0]['types'][0]['associationTypeId'], 192)
    def test_rerun_is_idempotent(self):
        f = FakeHubSpot(); H.sync(ACC, f, now=NOW); n_co, n_t = len(f.companies), len(f.tasks)
        s = H.sync(ACC, f, now=NOW)
        self.assertEqual((len(f.companies), len(f.tasks)), (n_co, n_t)); self.assertEqual(s['properties_created'], []); self.assertFalse(s['group_created'])
        self.assertEqual((s['tasks_created'], s['tasks_updated']), (0, 2))
    def test_changed_tier_updates_same_task(self):
        f = FakeHubSpot(); H.sync(ACC, f, now=NOW); tid = f.companies['b.com']['properties']['segr_task_id']
        H.sync([acct('b.com', 1)], f, now=NOW)
        self.assertEqual(f.companies['b.com']['properties']['segr_task_id'], tid); self.assertIn('Tier 1', f.tasks[tid]['properties']['hs_task_subject']); self.assertEqual(f.tasks[tid]['properties']['hs_task_priority'], 'HIGH')
    def test_deleted_task_is_recreated(self):
        f = FakeHubSpot(); H.sync(ACC, f, now=NOW); f.tasks.clear()
        s = H.sync(ACC, f, now=NOW); self.assertEqual(s['tasks_created'], 2)
    def test_unmapped_owner_reported_and_default_owner(self):
        f = FakeHubSpot(); s = H.sync(ACC, f, {}, default_owner_email='owner@example.com', now=NOW)
        self.assertEqual(s['owners_unmapped'], []); self.assertEqual(f.companies['a.com']['properties']['hubspot_owner_id'], '9002')
        s = H.sync(ACC, FakeHubSpot(), {}, now=NOW); self.assertIn('sdr_01', s['owners_unmapped'])
    def test_auth_error_raises(self):
        with self.assertRaises(H.HubSpotError): H.sync(ACC, FakeHubSpot({r'GET /crm/v3/owners': 401}), now=NOW)
    def test_upsert_keyed_on_unique_property(self):
        f = FakeHubSpot(); H.sync(ACC, f, now=NOW)
        self.assertTrue(f.props['segr_domain_key']['hasUniqueValue']); self.assertIn(('POST', '/crm/v3/objects/companies/batch/upsert?idProperty=segr_domain_key'), f.log)
    def test_due_dates(self):
        p = H.task_props(acct('a.com', 1), None, NOW); self.assertEqual(p['hs_timestamp'], '2026-10-28T10:00:00Z')
    def test_dry_run_no_network_full_plan(self):
        dr = H.DryRun(); s = H.sync(ACC, dr, now=NOW)
        self.assertEqual(s['companies_upserted'], 5); self.assertEqual(s['tasks_created'], 2)
        self.assertTrue(all(r['path'].startswith('/crm/v3/') for r in dr.plan))
    def test_fixture_shapes(self):
        up = json.load(open(os.path.join(ROOT, 'tests/fixtures/hubspot/upsert_response.json'))); self.assertIn('id', up['results'][0])
class Transport(unittest.TestCase):
    def test_token_never_recorded(self):
        class R:
            status = 200
            def __enter__(s): return s
            def __exit__(s, *a): pass
            def read(s): return b'{"results": []}'
        orig = urllib.request.urlopen; seen = {}
        def fake(req, timeout=0): seen['auth'] = req.get_header('Authorization'); return R()
        urllib.request.urlopen = fake
        try:
            with tempfile.TemporaryDirectory() as d:
                st, data = H.live_transport('pat-secret-123', d)('GET', '/crm/v3/owners?limit=500')
                blob = ''.join(open(os.path.join(d, f)).read() for f in os.listdir(d))
        finally: urllib.request.urlopen = orig
        self.assertEqual(seen['auth'], 'Bearer pat-secret-123'); self.assertNotIn('pat-secret-123', blob); self.assertEqual(st, 200)
    def test_cli_live_without_token_exits(self):
        old = os.environ.pop('HUBSPOT_TOKEN', None)
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as t: t.write(json.dumps(ACC[0]) + '\n')
            with self.assertRaises(SystemExit): H.main(['--accounts', t.name, '--live'])
        finally:
            if old is not None: os.environ['HUBSPOT_TOKEN'] = old
if __name__ == '__main__': unittest.main()
