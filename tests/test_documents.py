import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if 'scopeledger' not in sys.modules:
    spec=importlib.util.spec_from_file_location('scopeledger',ROOT/'__init__.py',submodule_search_locations=[str(ROOT)])
    module=importlib.util.module_from_spec(spec);sys.modules['scopeledger']=module;spec.loader.exec_module(module)
from scopeledger import auditor,document_intake,intake_gate,tools

class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        env=patch.dict(os.environ,{'SCOPELEDGER_DATA_HOME':self.tmp.name})
        env.start();self.addCleanup(env.stop)
        self.inbox=Path(self.tmp.name)/'inbox'/'northstar'
        self.inbox.mkdir(parents=True)
        self.project=Path(self.tmp.name)/'projects'/'northstar'
        shutil.copytree(ROOT/'examples/northstar',self.project)
    def stage(self,name):
        shutil.copy2(ROOT/'tests/fixtures'/name,self.inbox/name)
    def test_full_synthetic_document_lineage_gate(self):
        # Fully synthetic human attestations; does NOT establish real-world completeness.
        from scopeledger import intake_gate
        documents=[('northstar_agreement.docx','agreement'),
                   ('northstar_approvals.docx','approvals'),
                   ('northstar_deliveries.pdf','deliveries'),
                   ('northstar_invoices.pdf','invoices')]
        for filename,role in documents:
            self.stage(filename)
            result=document_intake.inspect('northstar',filename,role)
            manifest=Path(result['manifest_path'])
            data=json.loads(manifest.read_text())
            review=manifest.with_name(manifest.name.replace('.manifest.json','.review.json'))
            intake_gate.dump_exclusive(review,{
                'schema':'1','project':'northstar','original':filename,'role':role,
                'source_sha256':data['source_sha256'],'extraction_sha256':data['extraction_sha256'],
                'reviewer_attested_original_and_every_financial_row':True,'warnings_human_resolved':True})
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        identity=intake_gate.snapshot_identity('northstar')
        import hashlib
        digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        path=Path(self.tmp.name)/'attestations'/'northstar'/(digest+'.json')
        intake_gate.dump_exclusive(path,identity)
        self.assertTrue(intake_gate.gate('northstar')['passed'])
        audited=json.loads(tools.scopeledger_audit({'project':'northstar'}))
        self.assertTrue(audited['ok'],audited)
        self.assertEqual(audited['audit']['totals']['ready_minor'],30000)
        (self.inbox/'northstar_invoices.pdf').write_bytes((self.inbox/'northstar_invoices.pdf').read_bytes()+b'\n')
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        self.assertFalse(json.loads(tools.scopeledger_audit({'project':'northstar'}))['ok'])

    def test_docx_word_tables_and_provenance(self):
        self.stage('agreement_with_table.docx')
        v=json.loads(tools.scopeledger_document({'project':'northstar','filename':'agreement_with_table.docx','role':'agreement'}))
        self.assertTrue(v['ok'],v)
        t=Path(v['extracted_path']).read_text()
        self.assertIn('Landing pages | USD 300 each',t)
        m=json.loads(Path(v['manifest_path']).read_text())
        self.assertEqual(m['review_status'],'PENDING_HUMAN_REVIEW')
        self.assertEqual(len(m['source_sha256']),64)
        self.assertEqual(m['financial_mapping_status'],'NOT_MAPPED')
    def test_pdf_two_pages_numeric_and_warning(self):
        self.stage('invoice_two_pages.pdf')
        v=json.loads(tools.scopeledger_document({'project':'northstar','filename':'invoice_two_pages.pdf','role':'invoices'}))
        if not v['ok'] and 'Poppler' in v.get('message',''):
            self.skipTest('Poppler not installed')
        self.assertTrue(v['ok'],v)
        self.assertEqual(v['page_or_section_count'],2)
        m=json.loads(Path(v['manifest_path']).read_text())
        self.assertTrue(all(x['characters']>25 for x in m['page_coverage']))
        self.assertIn('600.00',Path(v['extracted_path']).read_text())
        self.assertEqual(m['review_status'],'PENDING_HUMAN_REVIEW')
    def test_missing_doc_not_accepted(self):
        v=json.loads(tools.scopeledger_document({'project':'northstar','filename':'unknown.pdf','role':'invoices'}))
        self.assertFalse(v['ok'])
    def test_traversal_and_symlink_rejected(self):
        for name in ('../../etc/passwd','.secret.pdf','x.txt'):
            self.assertFalse(json.loads(tools.scopeledger_document({'project':'northstar','filename':name,'role':'invoices'}))['ok'])
        self.stage('agreement_with_table.docx')
        link=self.inbox/'linked.docx';link.symlink_to(self.inbox/'agreement_with_table.docx')
        self.assertFalse(json.loads(tools.scopeledger_document({'project':'northstar','filename':'linked.docx','role':'agreement'}))['ok'])
    def test_intake_blocks_ready_and_draft(self):
        self.stage('agreement_with_table.docx')
        a=json.loads(tools.scopeledger_audit({'project':'northstar'}))
        d=json.loads(tools.scopeledger_draft({'project':'northstar'}))
        self.assertFalse(a['ok']);self.assertFalse(d['ok'])
        self.assertIn('SOURCE_VERIFICATION_BLOCKED',a['message'])
    def test_drive_metadata_cannot_auto_consent(self):
        self.stage('agreement_with_table.docx')
        v=json.loads(tools.scopeledger_document({'project':'northstar','filename':'agreement_with_table.docx','role':'agreement','source_origin':'drive-selected-export'}))
        self.assertFalse(v['ok'])
    def test_changed_original_fails_immutable_extraction(self):
        self.stage('agreement_with_table.docx')
        first=document_intake.inspect('northstar','agreement_with_table.docx','agreement')
        second=document_intake.inspect('northstar','agreement_with_table.docx','agreement')
        self.assertEqual(first['source_sha256'],second['source_sha256'])
        with (self.inbox/'agreement_with_table.docx').open('ab') as f:f.write(b'changed')
        third=document_intake.inspect('northstar','agreement_with_table.docx','agreement')
        self.assertNotEqual(first['source_sha256'],third['source_sha256'])

    def _attest_four_fictional_documents(self):
        """Create only synthetic attestations for an isolated test directory."""
        import hashlib
        for filename, role in (
                ('northstar_agreement.docx','agreement'),
                ('northstar_approvals.docx','approvals'),
                ('northstar_deliveries.pdf','deliveries'),
                ('northstar_invoices.pdf','invoices')):
            self.stage(filename)
            result = document_intake.inspect('northstar', filename, role)
            manifest = Path(result['manifest_path'])
            data = json.loads(manifest.read_text())
            review = manifest.with_name(manifest.name.replace('.manifest.json','.review.json'))
            intake_gate.dump_exclusive(review, {
                'schema':'1','project':'northstar','original':filename,'role':role,
                'source_sha256':data['source_sha256'],
                'extraction_sha256':data['extraction_sha256'],
                'reviewer_attested_original_and_every_financial_row':True,
                'warnings_human_resolved':True})
        identity = intake_gate.snapshot_identity('northstar')
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        receipt = Path(self.tmp.name)/'attestations'/'northstar'/(key+'.json')
        intake_gate.dump_exclusive(receipt, identity)
        self.assertTrue(intake_gate.gate('northstar')['passed'])

    def test_sol_inbox_removal_never_disables_opt_in(self):
        self.stage('northstar_agreement.docx')
        document_intake.inspect('northstar','northstar_agreement.docx','agreement')
        self.assertTrue(intake_gate.intake_is_required('northstar'))
        shutil.rmtree(self.inbox)
        status = intake_gate.gate('northstar')
        self.assertTrue(status['required'])
        self.assertFalse(status['passed'])
        result = json.loads(tools.scopeledger_audit({'project':'northstar'}))
        self.assertFalse(result['ok'])
        self.assertIn('SOURCE_VERIFICATION_BLOCKED',result['message'])

    def test_sol_modified_ledger_between_attestation_and_audit_blocked(self):
        self._attest_four_fictional_documents()
        original = intake_gate.snapshot_identity
        calls = [0]
        def mutate_after_gate_snapshot(slug):
            identity = original(slug)
            calls[0] += 1
            if calls[0] == 2:
                # The test changes an invoice after the attested identity is
                # returned but before the financially relevant analyze() call.
                invoice = self.project/'invoices.csv'
                lines = invoice.read_text().splitlines(keepends=True)
                invoice.write_text(''.join(x for x in lines if 'I001' not in x))
            return identity
        with patch.object(intake_gate,'snapshot_identity',side_effect=mutate_after_gate_snapshot):
            result=json.loads(tools.scopeledger_audit({'project':'northstar'}))
        self.assertFalse(result['ok'],result)
        self.assertIn('SOURCE_VERIFICATION_BLOCKED',result['message'])

    def test_sol_credit_suffix_same_source_line_blocks_mapping(self):
        import hashlib
        self._attest_four_fictional_documents()
        original = self.inbox/'northstar_invoices.pdf'
        digest = hashlib.sha256(original.read_bytes()).hexdigest()[:16]
        folder = Path(self.tmp.name)/'extractions'/'northstar'/digest
        extracted = folder/'northstar_invoices.extracted.txt'
        manifest = folder/'northstar_invoices.manifest.json'
        review = folder/'northstar_invoices.review.json'
        # Synthetic extraction with a recognized invoice sentence followed by
        # an unmapped cancellation/credit on the *same line*.
        t = extracted.read_text()
        t = t.replace('Invoice INV-203 billed one additional landing page at USD 300.',
                      'Invoice INV-203 billed one additional landing page at USD 300. Credit USD 300; invoice cancelled.')
        extracted.write_text(t)
        newhash = hashlib.sha256(t.encode()).hexdigest()
        for record in (manifest,review):
            obj = json.loads(record.read_text())
            obj['extraction_sha256'] = newhash
            record.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError,'extra/unmapped financial content'):
            intake_gate.snapshot_identity('northstar')

    def test_sol_qualified_total_is_not_a_per_unit_price(self):
        from scopeledger import evidence_semantics
        service={'label':'Landing page','included_units':5,'extra_unit_price_minor':30000}
        for phrase in ('Additional landing pages: USD 300 total for two pages.',
                       'Additional landing pages: USD 300 per ten pages.',
                       'Additional landing pages: USD 300 each if approved elsewhere.'):
            with self.subTest(phrase=phrase):
                result = evidence_semantics.contract_terms(
                    'Five landing pages are included. '+phrase,service,'USD')
                self.assertFalse(result['semantic_verified'],result)
        valid = evidence_semantics.contract_terms(
            'Five landing pages are included. Additional landing pages: USD 300 each.',service,'USD')
        self.assertTrue(valid['semantic_verified'],valid)

    def test_sol_docx_content_control_credit_is_visible_and_warned(self):
        import zipfile
        src = ROOT/'tests/fixtures/northstar_agreement.docx'
        destination = self.inbox/'nested_credit.docx'
        with zipfile.ZipFile(src) as source, zipfile.ZipFile(destination,'w') as target:
            for entry in source.infolist():
                contents = source.read(entry.filename)
                if entry.filename == 'word/document.xml':
                    insert=(b'<w:sdt><w:sdtContent><w:p><w:r><w:t>'
                            b'Credit USD 300.00. Invoice INV-203 is cancelled.'
                            b'</w:t></w:r></w:p></w:sdtContent></w:sdt>')
                    self.assertIn(b'</w:body>',contents)
                    contents=contents.replace(b'</w:body>', insert+b'</w:body>')
                target.writestr(entry,contents)
        response=document_intake.inspect('northstar','nested_credit.docx','agreement')
        txt=Path(response['extracted_path']).read_text()
        self.assertIn('Credit USD 300.00. Invoice INV-203 is cancelled.',txt)
        self.assertTrue(any('content control' in x.lower() for x in response['issues']),response['issues'])

    def _stage_extra_docx(self, filename, role, paragraph):
        """Produce a new fictional DOCX with a separate material paragraph."""
        import zipfile
        src = ROOT/'tests/fixtures/northstar_approvals.docx'
        target = self.inbox/filename
        with zipfile.ZipFile(src) as z_in, zipfile.ZipFile(target, 'w') as z_out:
            for info in z_in.infolist():
                body = z_in.read(info.filename)
                if info.filename == 'word/document.xml':
                    from xml.sax.saxutils import escape as xml_escape
                    insert = ("<w:p><w:r><w:t>" + xml_escape(paragraph) + "</w:t></w:r></w:p>").encode()
                    body = body.replace(b'</w:body>', insert+b'</w:body>')
                z_out.writestr(info, body)
        outcome = document_intake.inspect('northstar', filename, role)
        manifest = Path(outcome['manifest_path'])
        meta = json.loads(manifest.read_text())
        receipt = manifest.with_name(manifest.name.replace('.manifest.json', '.review.json'))
        intake_gate.dump_exclusive(receipt, {
            'schema':'1', 'project':'northstar','original':filename,'role':role,
            'source_sha256':meta['source_sha256'], 'extraction_sha256':meta['extraction_sha256'],
            'reviewer_attested_original_and_every_financial_row':True,
            'warnings_human_resolved':True,
        })
        return outcome

    def test_astra_unmapped_plain_invoice_table_row_blocks_mapping(self):
        self._attest_four_fictional_documents()
        self._stage_extra_docx('unmapped_extra_invoice.docx', 'invoices',
                               'D002 | Landing page | 1 | USD 300.00')
        with self.assertRaisesRegex(ValueError, 'extra/unmapped financial'):
            intake_gate.snapshot_identity('northstar')
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        self.assertFalse(json.loads(tools.scopeledger_audit({'project':'northstar'}))['ok'])

    def test_astra_separate_line_revocation_with_no_digits_blocks_mapping(self):
        self._attest_four_fictional_documents()
        self._stage_extra_docx('extra_revocation.docx', 'approvals',
                               'All prior approvals are revoked. Do not bill any additional work.')
        with self.assertRaisesRegex(ValueError, 'cancellation/revocation'):
            intake_gate.snapshot_identity('northstar')
        self.assertFalse(json.loads(tools.scopeledger_draft({'project':'northstar'}))['ok'])

    def test_astra_cancelled_agreement_suppresses_structured_only_ready(self):
        import shutil
        temp = Path(self.tmp.name)/'structured'/'northstar'
        temp.parent.mkdir()
        shutil.copytree(ROOT/'examples/northstar', temp)
        source = temp/'sources/agreement.txt'
        source.write_text(source.read_text()+'\nThis agreement is cancelled. No additional work is chargeable.\n')
        result = auditor.analyze(temp)
        self.assertEqual(result['totals']['ready_minor'], 0)
        self.assertFalse(result['agreement_proof']['semantic_verified'])

    def test_astra_false_review_receipt_refuses_financial_ready(self):
        self._attest_four_fictional_documents()
        folder=Path(self.tmp.name)/'extractions'/'northstar'
        for receipt in folder.glob('*/*.review.json'):
            obj = json.loads(receipt.read_text())
            obj['reviewer_attested_original_and_every_financial_row'] = False
            obj['warnings_human_resolved'] = False
            receipt.write_text(json.dumps(obj))
        status=intake_gate.gate('northstar')
        self.assertFalse(status['passed'], status)
        self.assertIn('not affirmatively attested',status['reason'])
        self.assertFalse(json.loads(tools.scopeledger_audit({'project':'northstar'}))['ok'])

    def test_astra_change_and_restore_cannot_change_computed_amount(self):
        self._attest_four_fictional_documents()
        original = auditor._rows
        transient_reads = []
        def malicious_read(directory, name, columns, frozen=None):
            if name == 'invoices.csv':
                f=self.project/name
                body=f.read_bytes()
                try:
                    f.write_bytes(b'\n'.join(x for x in body.splitlines() if b'I001' not in x)+b'\n')
                    transient_reads.append(True)
                    return original(directory, name, columns, frozen=frozen)
                finally:
                    f.write_bytes(body)
            return original(directory, name, columns, frozen=frozen)
        with patch.object(auditor, '_rows', side_effect=malicious_read):
            result=json.loads(tools.scopeledger_audit({'project':'northstar'}))
        self.assertTrue(transient_reads)
        if result['ok']:
            # A race must NEVER inflate the ready amount or carry a false digest.
            self.assertEqual(result['audit']['totals']['ready_minor'], 30000)
            self.assertEqual(result['audit']['digest'], intake_gate.snapshot_identity('northstar')['structured_digest'])
        else:
            # Conservative refusal is also valid for concurrent modifications.
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])

    def test_astra_xml_namespace_alias_tracks_deleted_text(self):
        import zipfile
        src=ROOT/'tests/fixtures/northstar_approvals.docx'
        dst=self.inbox/'aliased_revision.docx'
        with zipfile.ZipFile(src) as original, zipfile.ZipFile(dst,'w') as created:
            for info in original.infolist():
                data=original.read(info.filename)
                if info.filename=='word/document.xml':
                    data=data.replace(b'</w:body>',
                        b'<w:p><w:del><w:r><w:delText>Credit USD 300.00</w:delText></w:r></w:del></w:p></w:body>')
                    data=data.replace(b'xmlns:w=',b'xmlns:x=').replace(b'w:',b'x:')
                created.writestr(info,data)
        result=document_intake.inspect('northstar','aliased_revision.docx','approvals')
        self.assertTrue(any('tracked edits' in issue.lower() for issue in result['issues']), result)

    def test_astra_extractions_symlink_ancestor_rejected(self):
        self.stage('agreement_with_table.docx')
        outside=Path(self.tmp.name)/'outside'
        outside.mkdir()
        (Path(self.tmp.name)/'extractions').symlink_to(outside, target_is_directory=True)
        result=json.loads(tools.scopeledger_document({'project':'northstar', 'filename':'agreement_with_table.docx', 'role':'agreement'}))
        self.assertFalse(result['ok'], result)
        self.assertIn('symlink',result.get('message','').lower())
        self.assertEqual(list(outside.rglob('*')), [])


    def test_astra_structured_approval_source_revocation_suppresses_ready(self):
        import shutil
        temp = Path(self.tmp.name)/'plain'/'northstar'
        temp.parent.mkdir()
        shutil.copytree(ROOT/'examples/northstar', temp)
        source = temp/'sources/client_messages.txt'
        source.write_text(source.read_text()+'\nAll prior approvals are revoked. Do not bill any additional work.\n')
        outcome = auditor.analyze(temp)
        self.assertEqual(outcome['totals']['ready_minor'], 0)
        self.assertTrue(any('revocation' in e for e in outcome['errors']))

    def test_astra_frozen_bytes_survive_transient_invoice_replacement(self):
        import shutil
        temp = Path(self.tmp.name)/'frozen'/'northstar'
        temp.parent.mkdir()
        shutil.copytree(ROOT/'examples/northstar', temp)
        original = auditor._rows
        replaced=[]
        def switch_once(directory, name, columns, frozen=None):
            if name == 'invoices.csv':
                path=temp/name
                before=path.read_bytes()
                try:
                    path.write_bytes(b'\n'.join(line for line in before.splitlines() if b'I001' not in line)+b'\n')
                    replaced.append(True)
                    return original(directory, name, columns, frozen=frozen)
                finally:
                    path.write_bytes(before)
            return original(directory, name, columns, frozen=frozen)
        with patch.object(auditor,'_rows',side_effect=switch_once):
            audit=auditor.analyze(temp)
        self.assertTrue(replaced)
        self.assertEqual(audit['totals']['ready_minor'],30000)
        clean=auditor.analyze(temp)
        self.assertEqual(audit['digest'],clean['digest'])

if __name__=='__main__':unittest.main()
