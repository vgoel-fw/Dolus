#!/usr/bin/env python3
"""run the scienter signal detector on a text file. local only, nothing leaves the machine."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.signals import load_rules, detect


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file'); p.add_argument('--statute', default='10b'); p.add_argument('--circuit', default='9', choices=['2', '9'])
    p.add_argument('--json', action='store_true')
    a = p.parse_args()
    r = detect(Path(a.file).read_text(), load_rules(), statute=a.statute, circuit=a.circuit)
    if a.json:
        print(json.dumps(r, indent=2)); return
    print(r['statute']['label'], '-', r['statute']['standard'])
    for s in r['signals']:
        print(f"\n[{s['status']}] {s['label']}  ({s['family']})")
        for role, b in s['bindings'].items():
            print(f"  {role}: {b['quote']}")
        for i in s['intervals']:
            print(f"  gap: {i['days']} days ({i['basis']})")
        for c in s['opposing']:
            print(f"  against: {c['label']} - {c['quote']}")
    if not r['signals']:
        print('\nno signals found')


if __name__ == '__main__':
    main()
