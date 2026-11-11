#!/usr/bin/env python3
"""Explicit local human source review and structured mapping attestation.

No network, no model, no automatic approvals. Approval receipts do not
claim PDF/DOCX completeness; human must visually compare every table/line.
"""
from __future__ import annotations
import argparse
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
if 'scopeledger' not in sys.modules:
    spec=importlib.util.spec_from_file_location('scopeledger',REPO/'__init__.py',submodule_search_locations=[str(REPO)])
    pkg=importlib.util.module_from_spec(spec);sys.modules['scopeledger']=pkg;spec.loader.exec_module(pkg)
import scopeledger.document_intake as intake
import scopeledger.storage as storage
import scopeledger.auditor as auditor
from scopeledger.intake_gate import dump_exclusive


def verify(args):
    p=intake._secure_path(args.project,args.filename)
    intake.guard_path_ancestry(storage.data_root(), storage.data_root()/'extractions'/args.project)
    manifest_candidates=list((storage.data_root()/'extractions'/args.project).glob('*/'+p.stem.lower().replace(' ','_')[:45]+'.manifest.json'))
    checksum=hashlib.sha256(p.read_bytes()).hexdigest()
    matches=[]
    for f in manifest_candidates:
        intake.guard_path_ancestry(storage.data_root(), f)
        m=json.loads(f.read_text())
        if m['source_sha256']==checksum and m['original']==args.filename and m['role']==args.role:
            matches.append((f,m))
    if len(matches)!=1:raise ValueError('No unique matching extraction manifest; re-inspect document')
    f,m=matches[0]
    if m['issues'] and not args.acknowledge_issues:
        raise ValueError('Extraction flagged issues; inspect original and use --acknowledge-issues if genuinely resolved')
    if not args.checked_original:
        raise ValueError('Requires explicit --checked-original confirmation after visual review')
    original=f.parent/(p.stem.lower().replace(' ','_')[:45]+'.extracted.txt')
    intake.guard_path_ancestry(storage.data_root(), original)
    if hashlib.sha256(original.read_bytes()).hexdigest()!=m['extraction_sha256']:
        raise ValueError('Extraction changed since it was produced')
    receipt={'schema':'1','project':args.project,'original':args.filename,'role':args.role,
             'source_sha256':checksum,'extraction_sha256':m['extraction_sha256'],
             'reviewer_attested_original_and_every_financial_row':True,
             'warnings_human_resolved':bool(not m['issues'] or args.acknowledge_issues),
             'warning':'This is a human claim, not an independent guarantee that nothing was missed.'}
    out=f.parent/(p.stem.lower().replace(' ','_')[:45]+'.review.json')
    dump_exclusive(out,receipt)
    print('REVIEWED:',out)


from scopeledger.intake_gate import snapshot_identity, certify, gate

if __name__=='__main__':
    pa=argparse.ArgumentParser(description='ScopeLedger bounded human review CLI')
    sp=pa.add_subparsers(dest='cmd',required=True)
    a=sp.add_parser('verify-document');a.add_argument('project');a.add_argument('filename');a.add_argument('role',choices=sorted(intake.ROLES));a.add_argument('--checked-original',action='store_true');a.add_argument('--acknowledge-issues',action='store_true')
    b=sp.add_parser('certify-mapping');b.add_argument('project');b.add_argument('--checked-mapping',action='store_true')
    c=sp.add_parser('gate');c.add_argument('project')
    args=pa.parse_args()
    try:
        if args.cmd=='verify-document':verify(args)
        elif args.cmd=='certify-mapping':certify(args)
        else:print(json.dumps(gate(args.project),indent=2))
    except Exception as e:
        print('BLOCKED:',str(e),file=sys.stderr);sys.exit(2)
