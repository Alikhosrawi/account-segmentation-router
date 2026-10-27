"""Guards, segmentation, tiering and SDR routing. Stdlib only. Guard helpers vendored from hiring-signal-scorer."""
import json, re, os, hashlib, html
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Job-ad snapshot is third-party text: kept outside the publishable folder.
SNAPSHOT = os.environ.get('SEGR_SNAPSHOT', os.path.join(ROOT, '..', '_segr_private', 'snapshot', 'postings.jsonl'))
MIN_CONF = 0.6

def validate(obj, schema, path='$'):
    errs = []; t = schema.get('type')
    if 'enum' in schema and obj not in schema['enum']: errs.append(f'{path}: {obj!r} not in enum')
    if t == 'object':
        if not isinstance(obj, dict): return [f'{path}: not an object']
        errs += [f'{path}.{k}: missing' for k in schema.get('required', []) if k not in obj]
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False: errs += [f'{path}.{k}: unexpected' for k in obj if k not in props]
        for k, v in obj.items():
            if k in props: errs += validate(v, props[k], f'{path}.{k}')
    elif t == 'array':
        if not isinstance(obj, list): return [f'{path}: not an array']
        for i, v in enumerate(obj): errs += validate(v, schema.get('items', {}), f'{path}[{i}]')
    elif t == 'string':
        if not isinstance(obj, str): return [f'{path}: not a string']
        if len(obj) < schema.get('minLength', 0): errs.append(f'{path}: too short')
        if 'maxLength' in schema and len(obj) > schema['maxLength']: errs.append(f'{path}: too long')
    elif t in ('number', 'integer'):
        if isinstance(obj, bool) or not isinstance(obj, (int, float)) or (t == 'integer' and not isinstance(obj, int)): return [f'{path}: not {t}']
        if obj < schema.get('minimum', float('-inf')) or obj > schema.get('maximum', float('inf')): errs.append(f'{path}: out of range')
    return errs
def load_schema(name): return json.load(open(os.path.join(ROOT, 'schemas', name)))
def parse_model_json(text):
    m = re.search(r'\{.*\}', text or '', re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except json.JSONDecodeError: return None
_Q = str.maketrans({'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '-', '\u00a0': ' '})
def norm(s):  # html entities are decoded twice because some boards double-escape (&amp;nbsp;)
    return re.sub(r'\s+', ' ', html.unescape(html.unescape(s or '')).translate(_Q)).strip().lower()
def quote_is_verbatim(q, src): q = norm(q); return bool(q) and q in norm(src)
def norm_domain(d): return re.sub(r'^(https?://)?(www\.)?', '', (d or '').strip().lower()).rstrip('/')
def account_id(domain): return 'acc_' + hashlib.sha1(norm_domain(domain).encode()).hexdigest()[:10]

def dedupe_companies(rows):
    """Keep first row per normalised domain."""
    seen, out = set(), []
    for r in rows:
        d = norm_domain(r['domain'])
        if d in seen: continue
        seen.add(d); out.append(dict(r, domain=d))
    return out

KIND = dict(finance_complexity='fit', distributed_spend='fit', finance_tooling='fit', finance_hiring='intent', gtm_scaleup='intent', new_market='intent', tool_adoption='intent')
def guard(cls, postings_by_id, schema):
    """cls: parsed model JSON. Returns Score dict (with lane, guard_flags)."""
    if cls is None: return dict(fit=0, intent=0, signals=[], prompt_version='?', guard_flags=['unparseable'], lane='needs_human')
    errs = validate(cls, schema)
    if errs: return dict(fit=0, intent=0, signals=[], prompt_version=str(cls.get('prompt_version', '?')) if isinstance(cls, dict) else '?', guard_flags=['schema:' + e for e in errs[:5]], lane='needs_human')
    flags = []
    for s in cls['signals']:  # code, not the model, decides which score a signal backs
        s['kind'] = KIND[s['signal_type']]
    for s in cls['signals']:
        p = postings_by_id.get(s['posting_id'])
        if p is None: flags.append(f'unknown_posting:{s["posting_id"]}')
        elif not quote_is_verbatim(s['evidence_quote'], p['title'] + '\n' + p['plain_text']): flags.append(f'quote_not_verbatim:{s["signal_type"]}')
    for kind in ('fit', 'intent'):
        types = {s['signal_type'] for s in cls['signals'] if s['kind'] == kind}
        if cls[kind] > 0 and not types: flags.append(f'{kind}_score_without_evidence')
        elif cls[kind] > len(types): flags.append(f'{kind}_score_exceeds_evidence')
    rec = dict(cls, guard_flags=flags)
    if flags: return dict(rec, lane='needs_human')
    # dedupe identical (type, quote) signals
    seen, sig = set(), []
    for s in cls['signals']:
        k = (s['signal_type'], norm(s['evidence_quote']))
        if k not in seen: seen.add(k); sig.append(s)
    rec['signals'] = sig
    return dict(rec, lane='ok' if (cls['fit'] or cls['intent']) else 'none')

BAND_SEGMENT = {'1-10': 'SMB', '11-50': 'SMB', '51-200': 'SMB', '201-500': 'Mid-Market', '501-1000': 'Mid-Market',
                '1001-5000': 'Enterprise', '5001-10000': 'Enterprise', '10001+': 'Enterprise', 'unknown': 'Unknown'}
def segment(band):
    if band not in BAND_SEGMENT: raise ValueError(f'unknown headcount band {band!r}')
    return BAND_SEGMENT[band]

def tier(score, min_conf=MIN_CONF):
    """Rules only. Returns (tier, reasons)."""
    if score['lane'] != 'ok': return 3, [f"lane {score['lane']}: Tier 3"]
    pts = score['fit'] + score['intent']; r = [f"fit {score['fit']} + intent {score['intent']} = {pts}"]
    t = 1 if pts >= 4 and score['intent'] >= 2 else 2 if pts >= 2 else 3
    if score['signals'] and all(s['confidence'] < min_conf for s in score['signals']) and t < 3:
        r.append(f'all signals below confidence {min_conf}: capped at Tier 3'); t = 3
    return t, r

def route(accounts, roster):
    """Deterministic: sort by (tier, domain); Enterprise and SMB/MM both round-robin over eligible SDRs with capacity left.
    Mutates and returns accounts with 'sdr' = SdrAssignment."""
    load = {s['sdr_id']: 0 for s in roster}; rr = {}
    for a in sorted(accounts, key=lambda x: (x['tier'], x['domain'])):
        if a.get('competitor'):
            a['sdr'] = dict(sdr_id='', sdr_name='', rule=COMPETITOR_RULE, queue=COMPETITOR_RULE); continue
        if a['score']['lane'] == 'needs_human':
            a['sdr'] = dict(sdr_id='', sdr_name='', rule='guard failed: human review before routing', queue='needs_human'); continue
        key = (a['territory'], a['segment'])
        if a['segment'] == 'Unknown':
            a['sdr'] = dict(sdr_id='', sdr_name='', rule='headcount unknown: research before routing', queue='overflow'); continue
        elig = [s for s in roster if a['territory'] in s['territories'] and a['segment'] in s['segments']]
        free = [s for s in elig if load[s['sdr_id']] < s['capacity']]
        if not free:
            a['sdr'] = dict(sdr_id='', sdr_name='', rule=f'no SDR with capacity for {key[0]}/{key[1]} ({len(elig)} eligible)', queue='overflow'); continue
        i = rr.get(key, 0) % len(free); s = free[i]; rr[key] = rr.get(key, 0) + 1
        load[s['sdr_id']] += 1
        a['sdr'] = dict(sdr_id=s['sdr_id'], sdr_name=s['name'], rule=f'{key[0]}/{key[1]} round-robin ({len(free)} with capacity)', queue='assigned')
    return accounts

COMPETITOR_RULE = 'competitor_excluded'
def load_competitors(path=None):
    path = path or os.path.join(ROOT, 'data', 'competitors.json')
    return {norm_domain(c['domain']) for c in json.load(open(path))['competitors']}

def apply_competitor_rule(a, competitors):
    """Deterministic override after LLM scoring: competitor -> fit 0, intent 0, Tier 3, no SDR (set in route), no task.
    The model's original scores are kept under score['llm_before_override'] for audit. Idempotent."""
    if norm_domain(a['domain']) not in competitors: a.pop('competitor', None); return a
    sc = a['score']
    if not a.get('competitor'): sc['llm_before_override'] = dict(fit=sc['fit'], intent=sc['intent'], lane=sc['lane'], tier=a['tier'])
    sc['fit'] = 0; sc['intent'] = 0
    if sc['lane'] == 'needs_human': sc['lane'] = 'ok'  # deterministic rule settles it; no human review needed
    a['competitor'] = True; a['tier'] = 3; a['tier_reasons'] = ['competitor (data/competitors.json): fit 0, intent 0, Tier 3']
    return a

GTM_FIN = re.compile(r'financ|account|controll|procure|treasur|payroll|cfo|fp&a|revops|revenue|sales|business develop|account exec|sdr|bdr|partner|operations|expansion|country|market', re.I)
def pick_postings(posts, k=3):
    """Prefer finance/GTM titles, then newest; stable."""
    return sorted(posts, key=lambda p: (0 if GTM_FIN.search(p['title'] or '') else 1, -(int(p.get('posted', '0000-00-00').replace('-', '') or 0)), p['posting_id']))[:k]

# ---------- rules-only keyword baseline (no model) ----------
BASELINE = {
 'finance_complexity': r'\b(multi[- ]entit\w*|legal entities|intercompany|consolidation|multi[- ]currenc\w*|subsidiar\w*)\b',
 'distributed_spend': r'\b(field (sales|team|staff)|travel (up to|regularly)|regular travel|company car|expense(s)? (report|claim))\b',
 'finance_tooling': r'\b(netsuite|sap s/4|datev|xero|sage intacct|quickbooks|navan|pleo|spendesk|moss|ramp|coupa|d365|dynamics 365)\b',
 'finance_hiring': r'\b(build\w*|grow\w*|expand\w*|scal\w*)\b[^.]{0,60}\b(finance|accounting|controlling|procurement|fp&a|treasury) (team|function)\b',
 'gtm_scaleup': r'\b(build\w*|scal\w*|expand\w*|grow\w*)\b[^.]{0,60}\b(sales team|sdr team|bdr team|revops|revenue operations|go-to-market team|sales org\w*)\b',
 'new_market': r'\b(launch\w*|expand\w*|enter\w*)\b[^.]{0,40}\b(new market|into (the )?(dach|france|uk|spain|italy|nordics|benelux|us|germany|poland))\b',
 'tool_adoption': r'\b(migrat\w*|roll(ing)?[- ]out|implement\w*)\b[^.]{0,60}\b(salesforce|hubspot|netsuite|sap|datev|coupa|d365)\b',
}
def baseline_score(posts, version='baseline_kw_v1'):
    sig = []
    for st, rx in BASELINE.items():
        r = re.compile(rx, re.I)
        for p in posts:
            for sent in re.split(r'(?<=[.!?])\s+', p['plain_text']):
                if r.search(sent): sig.append(dict(kind=KIND[st], signal_type=st, posting_id=p['posting_id'], evidence_quote=sent.strip()[:300], confidence=0.7)); break
            else: continue
            break
    fit = min(3, len({s['signal_type'] for s in sig if s['kind'] == 'fit'})); intent = min(3, len({s['signal_type'] for s in sig if s['kind'] == 'intent'}))
    return dict(fit=fit, intent=intent, signals=sig, prompt_version=version)

# ---------- v3 deterministic rules (amendment A3) ----------
# Finance-ops role titles: a clear buying signal -> intent >= 2. FP&A, treasury, trading, risk, account exec/manager excluded.
FINOPS_TITLE = re.compile(r'\b(accountant|accounting|bookkeep\w*|controller|controlling|accounts payable|accounts receivable|head of finance|finance (manager|director|lead|operations|ops)|vp,? finance|cfo|chief financial|payroll|procurement|purchasing|buchhalt\w*|comptable|comptabilit\w*|contr[oô]leur de gestion|consolidation|month[- ]end|erp)\b', re.I)
FINOPS_EXCLUDE = re.compile(r'\b(treasury|trader|trading|fp&a|risk|account (executive|manager)|sales|customer|partner|engineer|developer|product)\b', re.I)
FINANCE_TITLE = re.compile(r'financ|account(ant|ing|s payable)|controll|procure|purchas|payroll|cfo|fp&a|buchhalt|comptab|erp\b', re.I)
def finops_titles(posts):
    return [p for p in posts if FINOPS_TITLE.search(p.get('title') or '') and not FINOPS_EXCLUDE.search(p.get('title') or '')]
def apply_v3_rules(score, posts):
    """Post-guard, deterministic. (a) drop model finance_hiring signals whose posting title is not a finance role
    (office boilerplate, bank treasury desks); (b) a finance-ops role title sets intent >= 2. Only lane ok/none. Idempotent."""
    if score['lane'] not in ('ok', 'none'): return score
    by = {p['posting_id']: p for p in posts}; notes = []
    keep = []
    for s in score['signals']:
        t = (by.get(s['posting_id']) or {}).get('title') or ''
        if s['signal_type'] == 'finance_hiring' and (not FINANCE_TITLE.search(t) or re.search(r'treasury|trader|trading', t, re.I)):
            notes.append(f'v3: dropped finance_hiring from non-finance posting "{t.strip()}"'); continue
        keep.append(s)
    score['signals'] = keep
    for k in ('fit', 'intent'):
        n = len({s['signal_type'] for s in keep if s['kind'] == k})
        if score[k] > n: notes.append(f'v3: {k} {score[k]} -> {n} (evidence dropped)'); score[k] = n
    fo = finops_titles(posts)
    if fo and score['intent'] < 2:
        notes.append(f'v3: finance-ops hire "{fo[0]["title"].strip()}": intent {score["intent"]} -> 2'); score['intent'] = 2
    if notes:
        score['v3_rules'] = notes
        score['lane'] = 'ok' if (score['fit'] or score['intent']) else 'none'
    return score
