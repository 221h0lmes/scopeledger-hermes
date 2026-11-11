"""Input-review lock verification, checked before any financially ready audit."""
import hashlib
import json
from collections import Counter
import re
from . import auditor,document_intake as intake,storage


def require_document_intake(slug):
    """Sticky opt-in stored outside source folders, never silently disabled."""
    if not isinstance(slug, str) or not auditor.SLUG.fullmatch(slug):
        raise ValueError('Invalid project slug')
    marker = storage.data_root() / 'document_intake_required' / (slug + '.json')
    dump_exclusive(marker, {'schema': '1', 'project': slug, 'document_intake_required': True})
    return marker


def intake_is_required(slug):
    """Also recognize intake evidence from older versions without a marker."""
    if not isinstance(slug, str) or not auditor.SLUG.fullmatch(slug):
        raise ValueError('Invalid project slug')
    root = storage.data_root()
    marker = root / 'document_intake_required' / (slug + '.json')
    if marker.exists() or marker.is_symlink():
        return True
    for part in ('inbox', 'extractions', 'attestations'):
        target = root / part / slug
        if target.exists() or target.is_symlink():
            return True
    return False


def dump_exclusive(path, obj):
    value=json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
    intake.write_immutable(path, value)


def snapshot_identity(slug):
    root=storage.data_root()
    intake.guard_path_ancestry(root, root/'inbox'/slug)
    intake.guard_path_ancestry(root, root/'extractions'/slug)
    intake.guard_path_ancestry(root, root/'attestations'/slug)
    project=auditor._project_root(root/'projects',slug)
    sources_dir=root/'inbox'/slug
    if not sources_dir.is_dir() or sources_dir.is_symlink():raise ValueError('No permitted intake folder')
    docs=sorted(p for p in sources_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.pdf','.docx'})
    if len(docs)<4:raise ValueError('Expected original documents for agreement, delivery, approval, and invoice roles')
    seen_roles=set(); inputs=[]; documents_by_role={role: [] for role in intake.ROLES}
    for doc in docs:
        intake.guard_path_ancestry(root, doc)
        src_hash=hashlib.sha256(doc.read_bytes()).hexdigest()
        folder=root/'extractions'/slug/src_hash[:16]
        stem=doc.stem.lower().replace(' ','_')[:45]
        intake.guard_path_ancestry(root, folder)
        man=folder/(stem+'.manifest.json'); reviewed=folder/(stem+'.review.json')
        intake.guard_path_ancestry(root, man)
        intake.guard_path_ancestry(root, reviewed)
        if not man.is_file() or not reviewed.is_file():raise ValueError(f'Unreviewed document: {doc.name}')
        m=json.loads(man.read_text()); r=json.loads(reviewed.read_text())
        if src_hash!=m['source_sha256'] or src_hash!=r['source_sha256'] or m['extraction_sha256']!=r['extraction_sha256']:
            raise ValueError(f'Changed document: {doc.name}')
        # A matching hash does not mean that a human actually approved the
        # original. Require explicit, correctly scoped positive decisions.
        if (r.get('schema') != '1' or r.get('project') != slug or
            r.get('original') != doc.name or r.get('role') != m.get('role') or
            r.get('reviewer_attested_original_and_every_financial_row') is not True or
            r.get('warnings_human_resolved') is not True):
            raise ValueError(f'Human verification not affirmatively attested: {doc.name}')
        if m.get('schema_version') != '1' or m.get('role') not in intake.ROLES:
            raise ValueError(f'Invalid extraction manifest role/schema: {doc.name}')
        if m.get('input_snapshot') != 'captured-bytes-v1':
            raise ValueError(f'Extraction predates captured-byte provenance; re-inspect original: {doc.name}')
        if m.get('project') != slug or m.get('original') != doc.name:
            raise ValueError('Extraction manifest does not match this selected document')
        extracted=folder/(stem+'.extracted.txt')
        intake.guard_path_ancestry(root, extracted)
        extracted_bytes = extracted.read_bytes()
        if not extracted.is_file() or hashlib.sha256(extracted_bytes).hexdigest()!=m['extraction_sha256']:
            raise ValueError(f'Extracted text changed: {doc.name}')
        documents_by_role[m['role']].append(extracted_bytes.decode('utf-8'))
        seen_roles.add(m['role'])
        inputs.append({'name':doc.name,'role':m['role'],'sha256':src_hash,'extraction_sha256':m['extraction_sha256']})
    if seen_roles!=intake.ROLES:raise ValueError('Four required document roles not independently verified')
    # A signed checkbox is not evidence that a PDF's rows match the structured ledger.
    # Reject every missing bound quote and every unrepresented content line.
    def norm(v):
        return ' '.join(v.casefold().split())
    frozen = auditor._capture_project_inputs(project)
    raw = auditor.project_info(project, frozen=frozen)
    services = {service['code']: service for service in raw['services']}

    def lines(role):
        # Formatting markers are ignorable only when the ENTIRE line is a
        # marker. A document paragraph can itself start with "[PAGE 1]".
        return [norm(line) for doc in documents_by_role[role] for line in doc.splitlines()
                if norm(line) and not re.fullmatch(r'\[(?:page (?:[0-9]+|docx body)|docx body)\]', norm(line))]

    # Credits/taxes/discounts are unsupported adjustments, not zero-valued
    # ledger entries. Positive terms or a human checkbox cannot account for
    # them. Scan every role, including agreements, before matching excerpts.
    for role in intake.ROLES:
        if auditor.evidence_semantics.MATERIAL_REVERSAL.search('\n'.join(documents_by_role[role])):
            raise ValueError(f'{role}: extra/unmapped financial content or possible credit/adjustment/cancellation/revocation requires owner reconciliation')

    agreement = '\n'.join(documents_by_role['agreement'])
    anchor = raw['agreement_source'].get('quote', '')
    if not anchor or norm(anchor) not in norm(agreement):
        raise ValueError('Agreement anchor not found in original extraction')
    for service in raw['services']:
        proof = auditor.evidence_semantics.contract_terms(agreement, service, raw['currency'], services=raw['services'])
        if not proof['semantic_verified']:
            raise ValueError('Agreement PDF/DOCX does not substantiate service terms: ' + service['code'])
    # Unsupported clauses cannot hide outside the recognized quota/rate
    # excerpts. Even nonnumeric text must agree with the supplied agreement.
    agreement_context = {norm(line) for line in auditor._frozen_text(
        frozen, 'sources/' + raw['agreement_source']['file']).splitlines() if norm(line)}
    for line in lines('agreement'):
        if line not in agreement_context:
            raise ValueError('agreement: extra/unmapped financial content or unsupported clause requires reconciliation: ' + line[:90])

    delivery_rows = auditor._rows(project, 'deliveries.csv',
        {'delivery_id','service_code','units','delivered_on','source_file','source_quote'}, frozen=frozen)
    deliveries = {row['delivery_id']: row for row in delivery_rows}
    for role, csv_name in (('deliveries', 'deliveries.csv'),
                           ('approvals', 'approvals.csv'), ('invoices', 'invoices.csv')):
        records = delivery_rows if role == 'deliveries' else auditor._rows(project, csv_name,
            {'approval_id','delivery_id','status','approved_units','source_file','source_quote'} if role == 'approvals' else
            {'invoice_line_id','delivery_id','invoiced_units','source_file','source_quote'}, frozen=frozen)
        available = Counter(lines(role))
        mapped = set()
        for row in records:
            eid, quote = row['delivery_id'], norm(row['source_quote'])
            expected = norm(eid + ' | ' + row['source_quote'])
            if expected in mapped:
                raise ValueError(f'{role}: duplicate/reused original evidence occurrence for delivery {eid}')
            if not quote or available[expected] != 1:
                raise ValueError(f'{role}: original document delivery identity, quote or occurrence does not match delivery {eid}')
            if eid not in deliveries:
                raise ValueError(f'{role}: unknown delivery identity {eid}')
            delivery = deliveries[eid]
            service = services[delivery['service_code']]
            if role == 'deliveries':
                proof = auditor.evidence_semantics.delivery_quote(row['source_quote'],
                    auditor._num(row['units'], 'delivery units', allow_zero=False), service, row['delivered_on'])
            elif role == 'approvals':
                proof = auditor.evidence_semantics.approval_quote(row['source_quote'], row['status'],
                    auditor._num(row['approved_units'], 'approval units'), service, raw['currency'], service['extra_unit_price_minor'])
            else:
                proof = auditor.evidence_semantics.invoice_quote(row['source_quote'],
                    auditor._num(row['invoiced_units'], 'invoice units', allow_zero=False),
                    service, raw['currency'], service['extra_unit_price_minor'])
            if not proof['semantic_verified']:
                raise ValueError(f'{role}: source fields/service/quantity not verified for delivery {eid}: ' + proof['semantic_reason'])
            mapped.add(expected)
        for line in available:
            if line not in mapped and not auditor.evidence_semantics.source_metadata(line, role):
                raise ValueError(f'{role}: extra/unmapped financial content or possible denial/revocation requires owner reconciliation: {line[:90]}')
    audit = auditor.analyze(project, frozen=frozen)
    if not audit['ledger_complete']:
        reason = next((error for error in audit['errors'] if error.startswith('Invoice ')), 'Unresolved ledger reference')
        raise ValueError('Unreconciled supplied invoice/approval ledger: ' + reason)
    if not audit['source_context_complete']:
        raise ValueError('Unreconciled supplied source context: ' + '; '.join(audit['errors'])[:180])
    # Digest includes original structured records and source text that were reviewed.
    return {'documents':inputs,'structured_digest':audit['digest'],'project':slug}


def certify(args):
    if not args.checked_mapping:raise ValueError('Requires --checked-mapping after reconciling every structured row to its original PDF/DOCX')
    require_document_intake(args.project)
    identity=snapshot_identity(args.project)
    output=storage.data_root()/'attestations'/args.project/(hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()+'.json')
    dump_exclusive(output,identity)
    print('MAPPING ATTESTED:',output)
    print('This is a reviewed snapshot, not an independent guarantee of invoice completeness.')


def gate(slug):
    root=storage.data_root(); inbox=root/'inbox'/slug
    required = intake_is_required(slug)
    if not required:
        return {'required':False,'passed':False,'reason':'Legacy structured records; no document intake opted in'}
    if not inbox.exists():
        return {'required':True,'passed':False,'reason':'Previously opted-in original-document inbox is missing'}
    if inbox.is_symlink():return {'required':True,'passed':False,'reason':'Unsafe inbox'}
    try: identity=snapshot_identity(slug)
    except (ValueError,OSError,KeyError,TypeError) as e:
        return {'required':True,'passed':False,'reason':str(e)[:250]}
    path=root/'attestations'/slug/(hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()+'.json')
    approved=False
    if path.is_file() and not path.is_symlink():
        try: approved=(json.loads(path.read_text())==identity)
        except (ValueError,OSError): approved=False
    return {'required':True,'passed':approved,
            'reason':'Human-reviewed document mapping matches source and structured hashes' if approved else 'Structured mapping has not been attested for current source versions'}

