#!/usr/bin/env python3
"""precision/recall of the signal layer on data/signal_eval.json, split by rules only vs fused"""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.fusion import analyze_intent


def score(pairs):
    tp = sum(len(e & g) for e, g in pairs); fp = sum(len(g - e) for e, g in pairs); fn = sum(len(e - g) for e, g in pairs)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': round(tp / (tp + fp), 3) if tp + fp else None, 'recall': round(tp / (tp + fn), 3) if tp + fn else None}


def evaluate():
    items = json.loads((ROOT / 'data/signal_eval.json').read_text())['items']
    rules_only, fused, misses = [], [], []
    for it in items:
        got = analyze_intent(it['text'])['signals']
        exp = set(it['expected'])
        r = {s['id'] for s in got if s['status'] in ('supported', 'partial')}
        f = {s['id'] for s in got}
        rules_only.append((exp, r)); fused.append((exp, f))
        if exp != f:
            misses.append({'id': it['id'], 'expected': sorted(exp), 'got': sorted(f)})
    return {'items': len(items), 'rules_only': score(rules_only), 'fused': score(fused), 'misses': misses,
            'limits': ['tiny hand written set, same author as the rules, so treat as a smoke test not a benchmark']}


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
