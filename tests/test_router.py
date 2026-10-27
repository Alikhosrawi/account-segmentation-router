import unittest, sys, os, json, csv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'router'))
import core, run
SCHEMA = core.load_schema('score.schema.json')
P = {'gh:x:1': dict(posting_id='gh:x:1', title='Head of Finance', plain_text='We are building our first finance team across 5 entities. Lead our migration to NetSuite.', source_url='u')}
def sig(**k): return dict(dict(kind='fit', signal_type='finance_complexity', posting_id='gh:x:1', evidence_quote='across 5 entities', confidence=0.9), **k)
def cls(**k): return dict(dict(fit=1, intent=0, signals=[sig()], prompt_version='t'), **k)
def acct(domain, terr='DACH', seg='SMB', tier=2, lane='ok'): return dict(domain=domain, territory=terr, segment=seg, tier=tier, score=dict(lane=lane))
ROSTER = [dict(sdr_id='a', name='A', territories=['DACH'], segments=['SMB'], capacity=2), dict(sdr_id='b', name='B', territories=['DACH'], segments=['SMB'], capacity=1),
          dict(sdr_id='e', name='E', territories=['DACH'], segments=['Enterprise'], capacity=5)]
class Guard(unittest.TestCase):
    def test_ok(self): self.assertEqual(core.guard(cls(), P, SCHEMA)['lane'], 'ok')
    def test_unparseable(self): self.assertEqual(core.guard(core.parse_model_json('sorry'), P, SCHEMA)['lane'], 'needs_human')
    def test_parse_wrapped(self): self.assertEqual(core.parse_model_json('Here: {"a": 1} done')['a'], 1)
    def test_schema_bad_score(self): self.assertIn('schema', core.guard(cls(fit=7), P, SCHEMA)['guard_flags'][0])
    def test_schema_extra_key(self): self.assertEqual(core.guard(cls(extra=1), P, SCHEMA)['lane'], 'needs_human')
    def test_bad_signal_type(self): self.assertEqual(core.guard(cls(signals=[sig(signal_type='vibes')]), P, SCHEMA)['lane'], 'needs_human')
    def test_quote_not_verbatim(self):
        r = core.guard(cls(signals=[sig(evidence_quote='across five entities')]), P, SCHEMA); self.assertEqual(r['lane'], 'needs_human'); self.assertIn('quote_not_verbatim:finance_complexity', r['guard_flags'])
    def test_quote_whitespace_case_tolerant(self): self.assertEqual(core.guard(cls(signals=[sig(evidence_quote='ACROSS  5\nentities')]), P, SCHEMA)['lane'], 'ok')
    def test_quote_from_title_ok(self): self.assertEqual(core.guard(cls(signals=[sig(evidence_quote='Head of Finance')]), P, SCHEMA)['lane'], 'ok')
    def test_unknown_posting(self): self.assertEqual(core.guard(cls(signals=[sig(posting_id='nope')]), P, SCHEMA)['lane'], 'needs_human')
    def test_score_without_evidence(self): self.assertIn('intent_score_without_evidence', core.guard(cls(intent=2), P, SCHEMA)['guard_flags'])
    def test_kind_set_by_code(self):
        r = core.guard(cls(intent=1, signals=[sig(), sig(kind='fit', signal_type='tool_adoption', evidence_quote='Lead our migration to NetSuite')]), P, SCHEMA)
        self.assertEqual(r['lane'], 'ok'); self.assertEqual(r['signals'][1]['kind'], 'intent')
    def test_zero_scores_lane_none(self): self.assertEqual(core.guard(cls(fit=0, signals=[]), P, SCHEMA)['lane'], 'none')
    def test_dedupe_signals(self): self.assertEqual(len(core.guard(cls(signals=[sig(), sig(evidence_quote='Across 5 entities')]), P, SCHEMA)['signals']), 1)
class Rules(unittest.TestCase):
    def S(self, f, i, c=0.9, lane='ok'): return dict(fit=f, intent=i, lane=lane, signals=[dict(confidence=c)])
    def test_segments(self):
        self.assertEqual([core.segment(b) for b in ('11-50', '201-500', '1001-5000', '10001+', 'unknown')], ['SMB', 'Mid-Market', 'Enterprise', 'Enterprise', 'Unknown'])
        with self.assertRaises(ValueError): core.segment('lots')
    def test_tier1(self): self.assertEqual(core.tier(self.S(2, 2))[0], 1)
    def test_tier1_needs_intent(self): self.assertEqual(core.tier(self.S(3, 1))[0], 2)
    def test_tier3(self): self.assertEqual(core.tier(self.S(1, 0))[0], 3)
    def test_low_conf_cap(self): t, r = core.tier(self.S(3, 3, c=0.5)); self.assertEqual(t, 3); self.assertIn('capped', r[-1])
    def test_needs_human_tier3(self): self.assertEqual(core.tier(self.S(3, 3, lane='needs_human'))[0], 3)
    def test_dedupe_companies(self):
        self.assertEqual(len(core.dedupe_companies([dict(domain='https://www.X.com/'), dict(domain='x.com'), dict(domain='y.com')])), 2)
    def test_account_id_stable(self): self.assertEqual(core.account_id('www.X.com'), core.account_id('x.com'))
class Routing(unittest.TestCase):
    def test_round_robin_capacity_overflow(self):
        a = core.route([acct(d) for d in ('a.com', 'b.com', 'c.com', 'd.com')], ROSTER)
        self.assertEqual([x['sdr']['sdr_id'] for x in a], ['a', 'b', 'a', '']); self.assertEqual(a[3]['sdr']['queue'], 'overflow')
    def test_enterprise_goes_to_ent(self): self.assertEqual(core.route([acct('e.com', seg='Enterprise')], ROSTER)[0]['sdr']['sdr_id'], 'e')
    def test_no_territory_overflow(self): self.assertEqual(core.route([acct('f.com', terr='UKI')], ROSTER)[0]['sdr']['queue'], 'overflow')
    def test_unknown_segment_overflow(self): self.assertEqual(core.route([acct('u.com', seg='Unknown')], ROSTER)[0]['sdr']['queue'], 'overflow')
    def test_score_exceeds_evidence(self): self.assertIn('fit_score_exceeds_evidence', core.guard(cls(fit=2), P, SCHEMA)['guard_flags'])
    def test_html_entities_in_source(self):
        p = {'x': dict(posting_id='x', title='T', plain_text='Reporting &amp;amp; Control team&amp;nbsp;grows')}
        self.assertTrue(core.quote_is_verbatim('Reporting & Control team grows', p['x']['plain_text']))
    def test_baseline(self):
        b = core.baseline_score([dict(posting_id='p', plain_text='We run consolidation across subsidiaries. We are scaling our sales team in DACH.')])
        self.assertEqual((b['fit'], b['intent']), (1, 1))
    def test_needs_human_not_routed(self): self.assertEqual(core.route([acct('g.com', lane='needs_human')], ROSTER)[0]['sdr']['queue'], 'needs_human')
    def test_deterministic_order(self):
        x = [acct('z.com', tier=3), acct('m.com', tier=1)]; core.route(x, ROSTER); self.assertEqual(x[1]['sdr']['sdr_id'], 'a')
class Data(unittest.TestCase):
    def test_companies_file(self):
        rows = list(csv.DictReader(open(os.path.join(ROOT, 'data/companies.csv'))))
        self.assertGreaterEqual(len(rows), 55); self.assertEqual(len(rows), len(core.dedupe_companies(rows)))
        for r in rows: core.segment(r['headcount_band']); self.assertIn(r['ats'], ('ashby', 'greenhouse', 'lever'))
    def test_roster_covers_territories(self):
        terr = {r['territory'] for r in csv.DictReader(open(os.path.join(ROOT, 'data/companies.csv')))} - {'Non-EU HQ'}
        ro = json.load(open(os.path.join(ROOT, 'data/sdrs.SYNTHETIC.json')))['sdrs']
        self.assertTrue(terr <= {t for s in ro for t in s['territories']})
    def test_pick_postings_prefers_finance(self):
        ps = [dict(posting_id='1', title='Backend Engineer', posted='2026-10-01'), dict(posting_id='2', title='Finance Manager', posted='2025-01-01')]
        self.assertEqual(core.pick_postings(ps, 1)[0]['posting_id'], '2')
    def test_render_contains_ids(self):
        t = run.render(open(os.path.join(ROOT, 'prompts/fit_intent_v1.md')).read(), 'X', [dict(P['gh:x:1'], location='Berlin')])
        self.assertIn('[posting_id: gh:x:1]', t); self.assertNotIn('{{', t)
@unittest.skipUnless(os.path.exists(core.SNAPSHOT), 'private job-ad snapshot not present (publish copy)')
class ReplayE2E(unittest.TestCase):
    def test_replay_run(self):
        import tempfile, io, contextlib
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            s = run.main(['--mode', 'replay', '--out', d, '--prompt', os.path.join(ROOT, 'prompts/fit_intent_v2a.md'), '--domains', 'agicap.com,pleo.io,storyblok.com'])
            rows = [json.loads(l) for l in open(os.path.join(d, 'accounts.replay.fit_intent_v2a.jsonl'))]
        self.assertEqual(s['scored'], 3); self.assertEqual(s['tokens']['input_tokens'], 0)
        for r in rows:
            if r['score']['lane'] == 'ok':
                ps = {json.loads(l)['posting_id']: json.loads(l) for l in open(core.SNAPSHOT)}
                for g in r['score']['signals']: self.assertTrue(core.quote_is_verbatim(g['evidence_quote'], ps[g['posting_id']]['title'] + '\n' + ps[g['posting_id']]['plain_text']))
class Evaluate(unittest.TestCase):
    def test_gold_uses_ali_override(self):
        import tempfile; sys.path.insert(0, os.path.join(ROOT, 'scripts')); import evaluate as E
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as t:
            t.write('domain,draft_fit,draft_intent,ali_fit,ali_intent\na.com,1,1,,\nb.com,0,0,3,2\n')
        g = E.gold(t.name); self.assertEqual(g['a.com']['tier'], 2); self.assertEqual(g['b.com']['tier'], 1); self.assertTrue(g['b.com']['changed'])
        r = E.evaluate(g, [dict(domain='a.com', tier=2, score=dict(fit=1, intent=1, lane='ok')), dict(domain='b.com', tier=3, score=dict(fit=0, intent=0, lane='needs_human'))])
        self.assertEqual((r['tier_accuracy'], r['needs_human']), (0.5, 1))
if __name__ == '__main__': unittest.main()

class Competitor(unittest.TestCase):
    C = {'pleo.io', 'getmoss.com', 'perk.com', 'qonto.com'}
    def A(self, d, tier=2, lane='ok'): return dict(domain=d, territory='DACH', segment='SMB', tier=tier, tier_reasons=[], score=dict(fit=2, intent=2, lane=lane, signals=[]))
    def test_config_lists_four(self): self.assertEqual(core.load_competitors(), self.C)
    def test_override_scores_and_tier(self):
        a = core.apply_competitor_rule(self.A('www.Pleo.io'), self.C)
        self.assertEqual((a['score']['fit'], a['score']['intent'], a['tier']), (0, 0, 3)); self.assertTrue(a['competitor'])
        self.assertEqual(a['score']['llm_before_override'], dict(fit=2, intent=2, lane='ok', tier=2))
    def test_idempotent(self):
        a = core.apply_competitor_rule(core.apply_competitor_rule(self.A('qonto.com'), self.C), self.C)
        self.assertEqual(a['score']['llm_before_override']['fit'], 2)
    def test_non_competitor_untouched(self):
        a = core.apply_competitor_rule(self.A('agicap.com'), self.C); self.assertEqual((a['tier'], a['score']['fit']), (2, 2)); self.assertNotIn('competitor', a)
    def test_routing_no_sdr(self):
        accs = [core.apply_competitor_rule(self.A(d), self.C) for d in ('getmoss.com', 'x.com')]; core.route(accs, ROSTER)
        self.assertEqual(accs[0]['sdr'], dict(sdr_id='', sdr_name='', rule='competitor_excluded', queue='competitor_excluded')); self.assertEqual(accs[1]['sdr']['queue'], 'assigned')
    def test_competitor_does_not_use_capacity(self):
        accs = [core.apply_competitor_rule(self.A(d), self.C) for d in ('getmoss.com', 'perk.com', 'pleo.io', 'a.com', 'b.com', 'c.com')]; core.route(accs, ROSTER)
        self.assertEqual(sum(a['sdr']['queue'] == 'assigned' for a in accs), 3)
    def test_no_task(self):
        import hubspot
        a = core.apply_competitor_rule(self.A('perk.com'), self.C); a['sdr'] = dict(sdr_id='a', sdr_name='A', rule='r', queue='assigned'); a['tier'] = 2
        self.assertFalse(hubspot.wants_task(a))
    def test_evaluate_excludes(self):
        sys.path.insert(0, os.path.join(ROOT, 'scripts')); import evaluate
        g = {d: dict(fit=0, intent=0, tier=3) for d in ('pleo.io', 'a.com')}
        accs = [dict(domain=d, tier=3, score=dict(fit=0, intent=0, lane='ok')) for d in ('pleo.io', 'a.com')]
        r = evaluate.evaluate(g, accs, self.C); self.assertEqual((r['n'], r['competitors_excluded'], r['competitors_excluded_domains']), (1, 1, ['pleo.io']))

class V3Rules(unittest.TestCase):
    def P(self, *titles): return [dict(posting_id=f'p{i}', title=t, plain_text='') for i, t in enumerate(titles)]
    def sc(self, fit, intent, sigs): return dict(fit=fit, intent=intent, lane='ok' if fit or intent else 'none', signals=sigs)
    def s(self, st, pid='p0'): return dict(kind=core.KIND[st], signal_type=st, posting_id=pid, evidence_quote='q', confidence=0.9)
    def test_finops_title_sets_intent_2(self):
        r = core.apply_v3_rules(self.sc(2, 1, [self.s('finance_complexity'), self.s('finance_tooling'), self.s('finance_hiring')]), self.P('Senior Accountant (m/f/d)'))
        self.assertEqual(r['intent'], 2); self.assertEqual(core.tier(r)[0], 1)
    def test_finops_titles(self):
        for t in ('Financial Controller', 'Accounts Payable Specialist', 'Head of Finance', 'Procurement Manager', 'Buchhalter (m/w/d)', 'ERP Project Lead'):
            self.assertTrue(core.finops_titles(self.P(t)), t)
        for t in ('Account Executive', 'Treasury Trader', 'Senior FP&A Analyst', 'Key Account Manager', 'Director of Financial Risk', 'Engineering Manager - Financial Products'):
            self.assertFalse(core.finops_titles(self.P(t)), t)
    def test_drops_finance_hiring_from_non_finance_posting(self):
        r = core.apply_v3_rules(self.sc(1, 1, [self.s('finance_complexity'), self.s('finance_hiring')]), self.P('People Operations Manager'))
        self.assertEqual((r['intent'], len(r['signals'])), (0, 1))
    def test_drops_treasury_desk(self):
        r = core.apply_v3_rules(self.sc(0, 1, [self.s('finance_hiring')]), self.P('Treasury Trader'))
        self.assertEqual((r['intent'], r['lane']), (0, 'none'))
    def test_needs_human_untouched(self):
        sc = dict(fit=0, intent=0, lane='needs_human', signals=[]); self.assertEqual(core.apply_v3_rules(sc, self.P('Accountant'))['intent'], 0)
    def test_idempotent(self):
        p = self.P('Accountant'); r = core.apply_v3_rules(self.sc(1, 1, [self.s('finance_hiring')]), p)
        self.assertEqual(core.apply_v3_rules(dict(r), p)['intent'], 2)
