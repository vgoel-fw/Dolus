"""scienter signal detection: symbolic rules + temporal reasoning.

every hit points at an exact span of the input. nothing here decides scienter,
it flags patterns courts talk about so an attorney can look at them.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEGATORS = {'no', 'not', 'never', 'without', 'neither', 'nor', 'denied', 'denies', 'lacked', 'lacks', "didn't", 'absent', 'nothing'}
_BOUNDARY = re.compile(r'(?<=[.!?])["\'’”)]*\s+(?=[A-Z0-9"“(\[])|\n\s*')
_ABBREV = re.compile(r'(?:\b(?:v|vs|inc|corp|co|ltd|no|nos|mr|ms|mrs|dr|sec|cir|st|jr|sr|e\.g|i\.e|u\.s|f|supp|cal|n\.y)\.|\b[A-Z]\.)$', re.I)


def load_rules(path=None):
    rules = json.loads(Path(path or ROOT / 'data/scienter_signals.json').read_text())
    validate_rules(rules)
    for s in rules['signals']:
        s['_roles'] = {k: [re.compile(r'(?<![\w-])(?:' + p + r')(?![\w])', re.I) for p in v] for k, v in s['roles'].items()}
        s['_exclude'] = [re.compile(p, re.I) for p in s.get('exclude', [])]
        s['_generic'] = [re.compile(p, re.I) for p in s.get('generic', [])]
    for c in rules['counter_signals']:
        c['_patterns'] = [re.compile(r'(?<![\w-])(?:' + p + r')(?![\w])', re.I) for p in c['patterns']]
    return rules


def validate_rules(rules):
    ids = set()
    for s in rules.get('signals', []):
        for k in ('id', 'label', 'family', 'roles', 'rule', 'prototypes'):
            if k not in s:
                raise ValueError(f'signal missing {k}')
        if s['id'] in ids:
            raise ValueError('duplicate signal ' + s['id'])
        ids.add(s['id'])
        needed = set(s['rule']['all']) | set(s['rule'].get('partial', []))
        if needed - set(s['roles']):
            raise ValueError(f"{s['id']} rule uses unknown role")
        for patterns in s['roles'].values():
            for p in patterns:
                re.compile(p)
    for c in rules.get('counter_signals', []):
        if any(t != '*' and t not in ids for t in c['counters']):
            raise ValueError(c['id'] + ' counters an unknown signal')
    for st in rules.get('statutes', []):
        if st['scienter'] not in {'element', 'not_an_element', 'split', 'derivative'}:
            raise ValueError('bad scienter value for ' + st['id'])
        if set(st.get('emphasis', {})) - ids:
            raise ValueError(st['id'] + ' emphasizes an unknown signal')


def sentences(text):
    """sentence spans with offsets into the original text"""
    spans, start = [], 0
    for m in _BOUNDARY.finditer(text):
        piece = text[start:m.start()]
        if '\n' not in m.group(0) and _ABBREV.search(piece.rstrip()):
            continue  # "v." "Inc." etc, not a real sentence end
        spans.append((start, m.start())); start = m.end()
    spans.append((start, len(text)))
    out = []
    for a, b in spans:
        raw = text[a:b]
        body = raw.strip()
        if len(body) > 2:
            st = a + len(raw) - len(raw.lstrip())
            out.append({'start': st, 'end': st + len(body), 'text': body})
    return out


def _negated(sentence, start):
    before = sentence[max(0, start - 70):start]
    before = re.split(r'[;:]|\b(?:but|although|whereas|however)\b', before, flags=re.I)[-1]
    return any(w in NEGATORS for w in re.findall(r"[a-z']+", before.lower())[-6:])


def _role_hits(signal, sent):
    text = sent['text']
    if any(x.search(text) for x in signal['_exclude']):
        return {}
    hits = {}
    for role, patterns in signal['_roles'].items():
        for p in patterns:
            m = p.search(text)
            if m and not _negated(text, m.start()):
                hits[role] = m.group(0)
                break
    return hits


# temporal --------------------------------------------------------------

MONTHS = {m: i + 1 for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'])}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS['sept'] = 9
_DATE = re.compile(r'\b(?:(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.? (?:(?P<day>\d{1,2}),? )?(?P<year>(?:19|20)\d{2})|(?P<iy>(?:19|20)\d{2})-(?P<im>\d{2})-(?P<id>\d{2})|(?P<um>\d{1,2})/(?P<ud>\d{1,2})/(?P<uy>(?:19|20)\d{2}))\b', re.I)
_NUM = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'several': 4, 'a few': 3, 'few': 3}
_REL = re.compile(r'\b(?P<n>\d+|an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|several|a few)\s+(?:business\s+)?(?P<unit>day|week|month)s?\s+(?P<dir>before|prior to|ahead of|after|following|later)', re.I)
_UNIT = {'day': 1, 'week': 7, 'month': 30}
EVENT_ROLES = {'trade': 'suspicious_trading_timing', 'anchor': 'suspicious_trading_timing', 'change': 'trading_plan_timing', 'departure': 'departure_timing'}


def parse_dates(text):
    found = []
    for m in _DATE.finditer(text):
        try:
            if m.group('mon'):
                d = date(int(m.group('year')), MONTHS[m.group('mon').lower()[:3]], int(m.group('day') or 1))
                precision = 'day' if m.group('day') else 'month'
            elif m.group('iy'):
                d = date(int(m.group('iy')), int(m.group('im')), int(m.group('id'))); precision = 'day'
            else:
                d = date(int(m.group('uy')), int(m.group('um')), int(m.group('ud'))); precision = 'day'
        except (ValueError, KeyError):
            continue
        found.append({'date': d, 'precision': precision, 'start': m.start(), 'end': m.end()})
    return found


def relative_offsets(text):
    out = []
    for m in _REL.finditer(text):
        n = m.group('n').lower()
        days = (int(n) if n.isdigit() else _NUM.get(n, 1)) * _UNIT[m.group('unit').lower()]
        sign = -1 if m.group('dir').lower() in {'before', 'prior to', 'ahead of'} else 1
        out.append({'days': sign * days, 'quote': m.group(0)})
    return out


def timeline(text, sents, rules):
    """dated or relatively placed events of the types the timing rules care about"""
    by_id = {s['id']: s for s in rules['signals']}
    events = []
    for sent in sents:
        dates = parse_dates(sent['text'])
        rel = relative_offsets(sent['text'])
        for role, sid in EVENT_ROLES.items():
            pats = by_id[sid]['_roles'].get(role, [])
            m = next((x for p in pats for x in [p.search(sent['text'])] if x and not _negated(sent['text'], x.start())), None)
            if not m:
                continue
            events.append({'type': role, 'quote': sent['text'], 'start': sent['start'], 'end': sent['end'],
                           'date': dates[0]['date'].isoformat() if dates else None,
                           'precision': dates[0]['precision'] if dates else None,
                           'relative_days': rel[0]['days'] if rel else None})
    order = {'trade': 0, 'change': 0, 'departure': 1, 'anchor': 2}
    events.sort(key=lambda e: (e['date'] is None, e['date'] or '', order[e['type']], e['start']))
    return events


def intervals(events, frm, to, max_days, either_order=False):
    """days between dated events of two types. also uses 'N weeks before' when an event sentence
    mentions the other event type itself"""
    out = []
    a = [e for e in events if e['type'] == frm]
    b = [e for e in events if e['type'] == to]
    for x in a:
        for y in b:
            if x['date'] and y['date'] and x['start'] != y['start']:
                gap = (date.fromisoformat(y['date']) - date.fromisoformat(x['date'])).days
                if (0 <= gap <= max_days) or (either_order and abs(gap) <= max_days):
                    out.append({'from': x['quote'], 'to': y['quote'], 'days': gap, 'basis': 'dates', 'approximate': 'month' in (x['precision'], y['precision'])})
            elif x['start'] == y['start'] and x['relative_days'] is not None and abs(x['relative_days']) <= max_days:
                out.append({'from': x['quote'], 'to': y['quote'], 'days': abs(x['relative_days']), 'basis': 'stated offset', 'approximate': True})
    return out


# symbolic evaluation ----------------------------------------------------

def _window_ok(per_sentence, i, roles, scope):
    lo, hi = (0, len(per_sentence)) if scope >= 99 else (max(0, i - scope), min(len(per_sentence), i + scope + 1))
    got = {}
    for j in range(lo, hi):
        for r, q in per_sentence[j].items():
            if r in roles and r not in got:
                got[r] = (j, q)
    return got


def symbolic(text, rules, sents=None):
    """per signal: which rule roles were satisfied and where"""
    sents = sents if sents is not None else sentences(text)
    events = timeline(text, sents, rules)
    results = {}
    for s in rules['signals']:
        per = [_role_hits(s, x) for x in sents]
        need = s['rule']['all']; partial = s['rule'].get('partial', []); scope = s['rule'].get('scope', 1)
        best = None
        for i, hits in enumerate(per):
            if not hits:
                continue
            got = _window_ok(per, i, set(need), scope)
            covered = [r for r in need if r in got]
            if best is None or len(covered) > len(best['covered']):
                best = {'covered': covered, 'bindings': {r: {'quote': sents[j]['text'], 'start': sents[j]['start'], 'end': sents[j]['end'], 'match': q} for r, (j, q) in got.items()}}
            if len(covered) == len(need):
                break
        temporal = []
        t = s['rule'].get('temporal')
        if t:
            temporal = intervals(events, t['from'], t['to'], t['max_days'], t.get('either_order', False))
        status = None
        if best:
            if len(best['covered']) == len(need):
                status = 'supported'
            elif t and temporal and all(r in best['covered'] for r in partial):
                # dated events close together stand in for proximity language
                status = 'supported'
                best['covered'] = sorted(set(best['covered']) | {'proximity'} & set(need))
            elif partial and all(r in best['covered'] for r in partial):
                status = 'partial'
        if status is None:
            continue
        generic = [p.pattern for p in s['_generic'] if p.search(text)]
        results[s['id']] = {'status': status, 'coverage': round(len(best['covered']) / len(need), 3),
                            'covered_roles': best['covered'], 'missing_roles': [r for r in need if r not in best['covered']],
                            'bindings': best['bindings'], 'intervals': temporal, 'generic_only': bool(generic) and status != 'supported'}
    return results, events


def counter_signals(text, rules, sents=None):
    sents = sents if sents is not None else sentences(text)
    out = []
    for c in rules['counter_signals']:
        for sent in sents:
            m = next((x for p in c['_patterns'] for x in [p.search(sent['text'])] if x), None)
            if m:
                out.append({'id': c['id'], 'label': c['label'], 'counters': c['counters'], 'quote': sent['text'], 'start': sent['start'], 'end': sent['end']})
                break
    return out


def statute_view(rules, statute, circuit):
    st = next((x for x in rules['statutes'] if x['id'] == statute), None)
    if st is None:
        raise ValueError('Unknown statute.')
    return {'id': st['id'], 'label': st['label'], 'scienter': st['scienter'], 'standard': st['standard'],
            'circuit_note': st.get('circuits', {}).get(circuit, ''), 'authorities': st['authorities'], 'emphasis': st.get('emphasis', {})}


def detect(text, rules, statute='10b', circuit='9'):
    """symbolic-only detection. app.fusion.analyze_intent adds the semantic layer on top."""
    if not isinstance(text, str) or not text.strip() or len(text) > 100000:
        raise ValueError('Supply text of 1–100,000 characters.')
    sents = sentences(text)
    sym, events = symbolic(text, rules, sents)
    counters = counter_signals(text, rules, sents)
    view = statute_view(rules, statute, circuit)
    out = []
    for s in rules['signals']:
        hit = sym.get(s['id'])
        if not hit:
            continue
        out.append({'id': s['id'], 'label': s['label'], 'family': s['family'], 'description': s['description'], **hit,
                    'opposing': [c for c in counters if s['id'] in c['counters'] or '*' in c['counters']],
                    'related_factors': s.get('related_factors', []), 'questions': s.get('questions', []), 'authorities': s.get('authorities', [])})
    return {'signals': out, 'timeline': events, 'counter_signals': counters, 'statute': view, 'method': 'symbolic rules + temporal intervals'}
