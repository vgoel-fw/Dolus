"""neuro-symbolic fusion for scienter signals.

perception: the encoder scores every sentence against each signal's prototype sentences.
reasoning: app.signals checks the rule (roles, window, dates, negation) and binds exact quotes.
fusion: the rule decides the status, the encoder ranks and catches paraphrases the rules miss
(those come back as semantic_only and are always marked for review). counter-signals are
listed next to each signal instead of being netted out, since the court weighs them together.
"""
from .encoder import get_encoder
from .signals import load_rules, sentences, symbolic, counter_signals, statute_view

_rules = None
_proto_cache = {}
SYMBOLIC_WEIGHT = 0.65
COVERAGE = {'supported': 1.0, 'partial': 0.5}


def rules():
    global _rules
    if _rules is None:
        _rules = load_rules()
    return _rules


def _prototypes(encoder, rs):
    key = (encoder.name, id(rs))
    if key not in _proto_cache:
        _proto_cache[key] = {s['id']: encoder.encode(s['prototypes']) for s in rs['signals']}
    return _proto_cache[key]


def semantic_scores(sents, encoder=None, rs=None):
    """best sentence + score per signal"""
    encoder = encoder or get_encoder(); rs = rs or rules()
    protos = _prototypes(encoder, rs)
    vecs = encoder.encode([s['text'] for s in sents]) if sents else []
    # one or two word fragments match anything, damp them
    damp = [min(1.0, len(s['text'].split()) / 8) for s in sents]
    grid = {sid: [damp[i] * max((encoder.cosine(v, p) for p in pv), default=0.0) for i, v in enumerate(vecs)] for sid, pv in protos.items()}
    top = [max(grid, key=lambda sid: grid[sid][i]) for i in range(len(vecs))]
    out = {}
    for sid, scores in grid.items():
        where = max(range(len(scores)), key=scores.__getitem__) if scores else None
        best = scores[where] if where is not None else 0.0
        # argmax flag so one sentence doesn't light up five neighbouring signals
        out[sid] = (round(best, 3), sents[where] if where is not None else None, where is not None and top[where] == sid)
    return out


def _rationale(sig, hit):
    rule = sig['rule']
    if hit['status'] == 'supported':
        why = ' + '.join(hit['covered_roles']) + f" found within {rule.get('scope', 1)} sentence(s)"
        if hit['intervals']:
            i = hit['intervals'][0]
            why += f"; {abs(i['days'])} day gap ({i['basis']})"
        return why
    return 'found ' + ', '.join(hit['covered_roles']) + '; missing ' + ', '.join(hit['missing_roles'])


def analyze_intent(text, statute='10b', circuit='9', encoder=None, rs=None):
    if not isinstance(text, str) or not text.strip() or len(text) > 100000:
        raise ValueError('Supply text of 1–100,000 characters.')
    if not isinstance(statute, str):
        raise ValueError('statute must be text.')
    encoder = encoder or get_encoder(); rs = rs or rules()
    view = statute_view(rs, statute, circuit)
    sents = sentences(text)
    sym, events = symbolic(text, rs, sents)
    counters = counter_signals(text, rs, sents)
    sem = semantic_scores(sents, encoder, rs)
    # sentences a rule already explains don't get to propose extra semantic-only signals
    explained = {b['start'] for h in sym.values() for b in h['bindings'].values()}
    explained |= {c['start'] for c in counters}  # a counter-signal sentence isn't evidence for the signal it counters
    out = []
    for sig in rs['signals']:
        hit = sym.get(sig['id'])
        neural, best, is_top = sem[sig['id']]
        if hit:
            status = hit['status']
        elif neural >= encoder.threshold and best and is_top and best['start'] not in explained:
            status = 'semantic_only'
            hit = {'status': status, 'coverage': 0.0, 'covered_roles': [], 'missing_roles': sig['rule']['all'],
                   'bindings': {}, 'intervals': [], 'generic_only': False}
        else:
            continue
        confidence = SYMBOLIC_WEIGHT * COVERAGE.get(status, 0.0) + (1 - SYMBOLIC_WEIGHT) * neural
        emphasis = view['emphasis'].get(sig['id'], 1.0)
        opposing = [c for c in counters if sig['id'] in c['counters'] or '*' in c['counters']]
        out.append({
            'id': sig['id'], 'label': sig['label'], 'family': sig['family'], 'description': sig['description'],
            **hit, 'status': status,
            'neural_score': neural,
            'semantic_match': {k: best[k] for k in ('text', 'start', 'end')} if best and neural > 0 else None,
            'confidence': round(confidence, 3), 'rank_score': round(confidence * emphasis, 3),
            'rationale': _rationale(sig, hit) if status != 'semantic_only' else 'close paraphrase of known patterns, no rule satisfied. read it yourself',
            'needs_review': True,
            'opposing': opposing,
            'statute_note': '' if view['scienter'] in {'element', 'derivative', 'split'} else f"Scienter is not an element of {view['label']}; this matters only if the claim sounds in fraud.",
            'related_factors': sig.get('related_factors', []), 'questions': sig.get('questions', []), 'authorities': sig.get('authorities', []),
        })
    out.sort(key=lambda s: (-s['rank_score'], s['id']))
    return {'signals': out, 'timeline': events, 'counter_signals': counters, 'statute': view,
            'encoder': encoder.name, 'threshold': encoder.threshold,
            'method': f'neuro-symbolic: {encoder.name} sentence similarity + rule engine with temporal intervals; rules set status, similarity ranks and proposes',
            'warnings': ['Signals are research prompts, not findings. Confidence ranks signals; it is not a probability that scienter is pleaded.']}
