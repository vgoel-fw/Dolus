#!/usr/bin/env python3
"""Report extraction performance on authored fixtures; no legal accuracy claim."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.engine import draft


def evaluate():
    taxonomy=json.loads((ROOT/'data/taxonomy.json').read_text())
    fixtures=json.loads((ROOT/'data/synthetic_ground_truth.json').read_text())
    counts={f['id']:Counter() for f in taxonomy['factors']}; errors=[]; exact=0
    for fixture in fixtures:
        profile=draft(fixture['text'],taxonomy)['factors']; matches=True
        for factor,expected in fixture['factors'].items():
            actual=profile[factor]['status']; c=counts[factor]
            c['total']+=1;c['correct']+=actual==expected
            c['tp']+=actual=='present' and expected=='present'
            c['fp']+=actual=='present' and expected!='present'
            c['fn']+=actual!='present' and expected=='present'
            if actual!=expected:
                matches=False; errors.append({'fixture':fixture['id'],'factor':factor,'expected':expected,'actual':actual})
        exact+=matches
    def metrics(c):
        return {**c,'precision':round(c['tp']/(c['tp']+c['fp']),4) if c['tp']+c['fp'] else None,
                'recall':round(c['tp']/(c['tp']+c['fn']),4) if c['tp']+c['fn'] else None}
    totals=Counter()
    for c in counts.values():totals.update(c)
    return {'method':'deterministic_draft','taxonomy_version':taxonomy['version'],
            'engine_sha256':hashlib.sha256((ROOT/'app/engine.py').read_bytes()).hexdigest(),
            'fixtures':len(fixtures),'exact_profile_matches':exact,'micro':metrics(totals),
            'per_factor':{k:metrics(v) for k,v in counts.items()},'errors':errors,
            'limitations':['Authored, repetitive synthetic fixtures share vocabulary with the taxonomy; not an independent real-world benchmark.',
            'No absent-factor ground truth, legal conclusions, quote-attribution accuracy, retrieval relevance or empirical calibration evaluated.',
            'Unknown is not counted as present; conservative abstention therefore lowers recall.',
            'Stipulated factors describe the generating recipe; some sentences imply other factors and require independent relabeling.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out');args=p.parse_args()
    result=evaluate();content=json.dumps(result,indent=2)+'\n'
    if args.out:Path(args.out).write_text(content)
    else:print(content,end='')

if __name__=='__main__':main()
