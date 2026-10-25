"""Explicit-path actual-development audit. Exit 2=BLOCKED; never activates code."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from ai.activation_validation import assess_warehouse, ActivationProfile, CoverageAcceptance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--warehouse',type=Path,help='Explicit actual development DuckDB; no automatic database access')
    parser.add_argument('--years',type=int,nargs='+',default=[2000,2010,2019])
    parser.add_argument('--ages',nargs='+',default=['40-44','60-64','80-84'])
    parser.add_argument('--minimum-counties',type=int)
    parser.add_argument('--minimum-paired-percent',type=float)
    parser.add_argument('--minimum-rural-percent',type=float)
    parser.add_argument('--coverage-review-reference')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    values=(args.minimum_counties,args.minimum_paired_percent,args.minimum_rural_percent,args.coverage_review_reference)
    if any(v is not None for v in values) and not all(v is not None for v in values):
        parser.error('Supply all acceptance fields together; no unreviewed coverage defaults')
    acceptance=CoverageAcceptance(*values) if all(v is not None for v in values) else None
    report=assess_warehouse(args.warehouse,profile=ActivationProfile(years=tuple(args.years),ages=tuple(args.ages),acceptance=acceptance))
    payload=json.dumps(report,indent=2,allow_nan=False)
    if args.output:
        if args.warehouse and args.output.resolve()==args.warehouse.resolve():
            parser.error('Output must never overwrite the warehouse')
        args.output.write_text(payload+'\n')
    print(payload)
    if any(c['status']=='FAIL' for c in report['checks']): return 1
    return 0 if all(c['data_gate_ready'] for c in report['capabilities'].values()) else 2


if __name__=='__main__':
    raise SystemExit(main())
