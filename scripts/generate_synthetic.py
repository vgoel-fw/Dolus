#!/usr/bin/env python3
"""Create deterministic synthetic variations with inherited stipulated factor profiles.
These are fixture permutations, not independent real-world evaluation data.
"""
import argparse
import json
from pathlib import Path
import random
ROOT=Path(__file__).resolve().parents[1]

def generate(count=6,seed=42):
    rng=random.Random(seed)
    cases=[c for c in json.loads((ROOT/'data/cases.json').read_text()) if c['synthetic']]
    truth={c['id']:c for c in json.loads((ROOT/'data/synthetic_ground_truth.json').read_text())}
    result=[]
    for i in range(count):
        original=rng.choice(cases);entry=truth[original['id']]
        result.append({'id':f'generated-{seed}-{i+1:03}','title':f'Synthetic scenario {seed}-{i+1}',
                       'text':entry['text'],'circuit':original['circuit'],'defendant_scope':original['defendant_scope'],
                       'posture':original['posture'],'factors':entry['factors'],'synthetic':True,
                       'source_fixture':original['id'],'notice':'Fictional fixture permutation; no independent validation or predicted legal outcome.'})
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--count',type=int,default=6);p.add_argument('--seed',type=int,default=42);p.add_argument('--out',required=True);a=p.parse_args()
    if not 1<=a.count<=1000:p.error('count must be 1–1000')
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(generate(a.count,a.seed),f,indent=2)
    print(f'Wrote {a.count} synthetic patterns; inherited ground truth only.')
