#!/usr/bin/env python3
"""precision/recall of the signal layer.

real: sentences from checksummed CourtListener opinions (data/signal_eval_real.json), split dev/test by opinion.
"""
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.fusion import analyze_intent


def score(pairs):
    tp = sum(len(e & g) for e, g in pairs); fp = sum(len(g - e) for e, g in pairs); fn = sum(len(e - g) for e, g in pairs)
    p = tp / (tp + fp) if tp + fp else None; r = tp / (tp + fn) if tp + fn else None
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': round(p, 3) if p is not None else None, 'recall': round(r, 3) if r is not None else None,
            'f1': round(2 * p * r / (p + r), 3) if p and r else 0.0}


def verify(data):
    docs = {d['id']: d for d in json.loads((ROOT / 'data/flp_opinions.json').read_text())}
    for it in data['items']:
        d = docs[it['document_id']]
        if hashlib.sha256(d['text'].encode()).hexdigest() != it['source_sha256'] or d['text'][it['start']:it['end']] != it['text']:
            raise ValueError('eval item does not match its checksummed source: ' + it['id'])


def run(items):
    rules_only, fused, misses = [], [], []
    for it in items:
        got = analyze_intent(it['text'])['signals']
        exp = set(it['expected'])
        r = {s['id'] for s in got if s['status'] != 'semantic_only'}
        f = {s['id'] for s in got}
        rules_only.append((exp, r)); fused.append((exp, f))
        if exp != f:
            misses.append({'id': it['id'], 'expected': sorted(exp), 'got': sorted(f), 'text': it['text'][:160]})
    neg = [(set(), f) for (e, f) in fused if not e]
    return {'n': len(items), 'positives': sum(bool(i['expected']) for i in items), 'rules_only': score(rules_only), 'fused': score(fused),
            'false_alarm_rate_on_negatives': round(sum(bool(f) for _, f in neg) / len(neg), 3) if neg else None, 'misses': misses}


def evaluate():
    real = json.loads((ROOT / 'data/signal_eval_real.json').read_text()); verify(real)
    return {'real_dev': run([i for i in real['items'] if i['split'] == 'dev']),
            'real_test': run([i for i in real['items'] if i['split'] == 'test']),
            'limits': ['one labeler, sentence level only (multi-sentence patterns are undercounted)', 'small n: report the counts, not just the ratios']}


if __name__ == '__main__':
    r = evaluate()
    if '--full' in sys.argv:
        print(json.dumps(r, indent=2)); sys.exit()
    for k in ('real_dev', 'real_test'):
        x = r[k]
        print(f"{k:10} n={x['n']:3} pos={x['positives']:2}  rules P/R {x['rules_only']['precision']}/{x['rules_only']['recall']}  fused P/R/F1 {x['fused']['precision']}/{x['fused']['recall']}/{x['fused']['f1']}  false alarms on negatives {x['false_alarm_rate_on_negatives']}")
