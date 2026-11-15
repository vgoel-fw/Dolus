#!/usr/bin/env python3
"""local draft extractor vs the factor annotations on real opinion excerpts in data/cases.json.
annotations are pending attorney review, so this measures agreement with them, not legal accuracy."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.engine import draft


def evaluate():
    taxonomy=json.loads((ROOT/'data/taxonomy.json').read_text())
    cases=[c for c in json.loads((ROOT/'data/cases.json').read_text()) if not c['synthetic']]
    c=Counter(); errors=[]
    for case in cases:
        got=draft(case['opinion_text'],taxonomy)['factors']
        for fid,f in case['factors'].items():
            exp=f['status']=='present'; act=got[fid]['status']=='present'
            c['tp']+=exp and act; c['fp']+=act and not exp; c['fn']+=exp and not act
            if exp!=act: errors.append({'case':case['id'],'factor':fid,'expected':f['status'],'draft':got[fid]['status']})
    p=c['tp']/(c['tp']+c['fp']) if c['tp']+c['fp'] else None; r=c['tp']/(c['tp']+c['fn']) if c['tp']+c['fn'] else None
    return {'cases':len(cases),**c,'precision':round(p,3) if p is not None else None,'recall':round(r,3) if r is not None else None,'errors':errors,
            'limits':['6 opinion excerpts, annotations pending review','opinions discuss factors the court rejects, so present-in-text is not present-as-alleged']}


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--out');args=a.parse_args()
    out=json.dumps(evaluate(),indent=2)+'\n'
    Path(args.out).write_text(out) if args.out else print(out,end='')
