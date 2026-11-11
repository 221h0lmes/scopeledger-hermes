"""Fictional supplied-ledger and complete-clause financial regressions."""
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile
from xml.sax.saxutils import escape

import test_scopeledger as core_fixtures
import test_documents as document_fixtures
from scopeledger import auditor, document_intake, evidence_semantics, intake_gate, tools

ORIGINAL_QUOTA = 'Five landing pages are included.'
EXTRA_INVOICE = 'D002 | Invoice INV-204 billed one additional landing page at USD 300.'


class FinancialIntegrityTests(unittest.TestCase):
    setUp = core_fixtures.ScopeLedgerTests.setUp

    def append_source(self, line, filename='invoices.txt'):
        path = self.proj / 'sources' / filename
        with path.open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')

    def native_audit(self):
        result = json.loads(tools.scopeledger_audit({'project': 'northstar'}))
        self.assertTrue(result['ok'], result)
        return result['audit']

    def native_draft(self):
        result = json.loads(tools.scopeledger_draft({'project': 'northstar'}))
        self.assertTrue(result['ok'], result)
        return result

    def assert_unreconciled(self, audit):
        self.assertEqual(audit['totals']['ready_minor'], 0, audit)
        self.assertFalse(audit['ledger_complete'], audit)
        self.assertTrue(any('Invoice ' in error for error in audit['errors']), audit)
        self.assertFalse(any(item['status'] == 'READY_FOR_OWNER_REVIEW' for item in audit['findings']))

    def change_quota(self, clause):
        path = self.proj / 'sources/agreement.txt'
        path.write_text(path.read_text().replace(ORIGINAL_QUOTA, clause))
        path = self.proj / 'project.json'
        project = json.loads(path.read_text())
        project['agreement_source']['quote'] = project['agreement_source']['quote'].replace(ORIGINAL_QUOTA, clause)
        path.write_text(json.dumps(project))

    def assert_quota_blocked(self, clause):
        self.change_quota(clause)
        audit = self.native_audit()
        self.assertTrue(audit['agreement_proof']['matched'])
        self.assertFalse(audit['agreement_proof']['semantic_verified'], audit)
        self.assertEqual(audit['totals']['ready_minor'], 0, audit)
        self.assertEqual(self.native_draft()['ready_minor'], 0)

    def test_omitted_inv204_withholds_native_audit_and_draft(self):
        self.append_source(EXTRA_INVOICE)
        audit = self.native_audit()
        self.assert_unreconciled(audit)
        self.assertIn('INV-204', '\n'.join(audit['errors']))
        self.assertIn('sources/invoices.txt:4', '\n'.join(audit['errors']))
        self.assertEqual(self.native_draft()['ready_minor'], 0)
        findings = {item['delivery_id']: item for item in audit['findings']}
        self.assertEqual(findings['D002']['status'], 'PROVISIONAL_INCOMPLETE_LEDGER')
        self.assertEqual(findings['D005']['status'], 'EVIDENCE_OR_BILLING_EXCEPTION')

    def test_invoice_present_in_source_and_ledger_is_counted(self):
        self.append_source(EXTRA_INVOICE)
        with (self.proj / 'invoices.csv').open('a') as stream:
            stream.write('I003,D002,1,invoices.txt,' + EXTRA_INVOICE.split(' | ', 1)[1] + '\n')
        audit = self.native_audit()
        self.assertTrue(audit['ledger_complete'], audit)
        item = next(item for item in audit['findings'] if item['delivery_id'] == 'D002')
        self.assertEqual(item['invoiced_extra_units'], 2)
        self.assertEqual(item['status'], 'ALREADY_INVOICED')
        self.assertEqual(audit['totals']['already_invoiced_minor'], 60000)
        self.assertEqual(self.native_draft()['ready_minor'], 0)

    def test_duplicate_invoice_evidence_under_distinct_row_ids(self):
        path = self.proj / 'invoices.csv'
        row = path.read_text().splitlines()[1].replace('I001,', 'I099,', 1)
        path.write_text(path.read_text() + row + '\n')
        self.assert_unreconciled(self.native_audit())
        self.assertEqual(self.native_draft()['ready_minor'], 0)

    def test_valid_partial_invoice_preserves_northstar(self):
        audit = self.native_audit()
        self.assertTrue(audit['ledger_complete'], audit)
        self.assertEqual(audit['totals']['ready_minor'], 30000)
        self.assertEqual(audit['totals']['possible_minor'], 15000)
        self.assertEqual(self.native_draft()['ready_minor'], 30000)

    def test_source_invoice_explicitly_linked_to_other_delivery(self):
        path = self.proj / 'invoices.csv'
        path.write_text(path.read_text().replace('I001,D002,', 'I001,D001,'))
        self.assert_unreconciled(self.native_audit())
        self.assertEqual(self.native_draft()['ready_minor'], 0)

    def test_unmapped_invoice_in_unlinked_source_file(self):
        self.append_source(EXTRA_INVOICE, 'supplemental_notes.txt')
        audit = self.native_audit()
        self.assert_unreconciled(audit)
        self.assertIn('supplemental_notes.txt:1', '\n'.join(audit['errors']))

    def test_unrelated_prose_in_invoice_source_does_not_block(self):
        self.append_source('Invoice questions may be discussed at the next team meeting.')
        self.append_source('This export includes a fictional demonstration for the owner.')
        audit = self.native_audit()
        self.assertTrue(audit['ledger_complete'], audit)
        self.assertEqual(audit['totals']['ready_minor'], 30000)

    def test_same_invoice_identity_with_conflicting_quantities(self):
        line = 'D002 | Invoice INV-203 billed two additional landing pages at USD 300.'
        self.append_source(line, 'supplemental_notes.txt')
        with (self.proj / 'invoices.csv').open('a') as stream:
            stream.write('I003,D002,2,supplemental_notes.txt,' + line.split(' | ', 1)[1] + '\n')
        audit = self.native_audit()
        self.assert_unreconciled(audit)
        self.assertIn('identity', '\n'.join(audit['errors']).lower())

    def test_same_invoice_evidence_copied_to_other_source_is_not_independent(self):
        self.append_source('D002 | Invoice INV-203 billed one additional landing page at USD 300.', 'supplemental_notes.txt')
        self.assert_unreconciled(self.native_audit())

    def test_unbound_supplied_invoice_is_unreconciled(self):
        self.append_source(EXTRA_INVOICE.split(' | ', 1)[1], 'supplemental_notes.txt')
        self.assert_unreconciled(self.native_audit())

    def test_invoice_with_unsupported_fraction_is_not_silently_ignored(self):
        self.append_source('D002 | Invoice INV-204 billed 0.5 additional landing pages at USD 300.')
        self.assert_unreconciled(self.native_audit())

    def test_negated_quota_structured_audit_and_draft(self):
        self.assert_quota_blocked('Not five landing pages are included.')

    def test_fractional_quota_structured_audit_and_draft(self):
        self.assert_quota_blocked('0.5 landing pages are included.')

    def test_valid_integer_word_quota(self):
        audit = self.native_audit()
        self.assertTrue(audit['agreement_proof']['semantic_verified'])
        self.assertEqual(audit['totals']['ready_minor'], 30000)

    def test_valid_integer_digit_quota(self):
        self.change_quota('5 landing pages are included.')
        audit = self.native_audit()
        self.assertTrue(audit['agreement_proof']['semantic_verified'])
        self.assertEqual(audit['totals']['ready_minor'], 30000)
        self.assertEqual(self.native_draft()['ready_minor'], 30000)

    def test_contradictory_second_quota(self):
        self.append_source('Six landing pages are included.', 'agreement.txt')
        audit = self.native_audit()
        self.assertFalse(audit['agreement_proof']['semantic_verified'])
        self.assertEqual(audit['totals']['ready_minor'], 0)
        self.assertEqual(self.native_draft()['ready_minor'], 0)

    def test_unsupported_decimal_quota(self):
        self.assert_quota_blocked('5.0 landing pages are included.')

    def test_complete_quota_clause_context(self):
        service = {'label': 'Landing page', 'included_units': 5, 'extra_unit_price_minor': 30000}
        for clause in ('Not five landing pages are included.', 'Not\nfive landing pages are included.',
                       '0.5 landing pages are included.',
                       '5.0 landing pages are included.', '-5 landing pages are included.',
                       '15 landing pages are included.', 'Only if agreed, five landing pages are included.',
                       'Five landing pages are included if later approved.', 'Five landing pages are not included.',
                       'Five landing pages are included. Not five landing pages are included.',
                       'Five landing pages are included. 0.5 landing pages are included.'):
            with self.subTest(clause=clause):
                proof = evidence_semantics.contract_terms(clause + ' Additional landing pages: USD 300 each.', service, 'USD')
                self.assertFalse(proof['semantic_verified'], (clause, proof))
        # Preserve the old rejection of a conflicting rate occurrence, even
        # when its surrounding sentence is outside the affirmative grammar.
        text = 'Five landing pages are included. Additional landing pages: USD 300 each. Not additional landing pages: USD 900 each.'
        self.assertFalse(evidence_semantics.contract_terms(text, service, 'USD')['semantic_verified'])

    def _stage_reviewed_documents(self, quota=ORIGINAL_QUOTA):
        inbox = Path(self.temp.name) / 'inbox/northstar'
        inbox.mkdir(parents=True)
        for filename, role in (('northstar_agreement.docx', 'agreement'),
                               ('northstar_approvals.docx', 'approvals'),
                               ('northstar_deliveries.pdf', 'deliveries'),
                               ('northstar_invoices.pdf', 'invoices')):
            original = document_fixtures.ROOT / 'tests/fixtures' / filename
            data = original.read_bytes()
            if role == 'agreement' and quota != ORIGINAL_QUOTA:
                output = io.BytesIO()
                with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, 'w') as target:
                    for info in source.infolist():
                        part = source.read(info.filename)
                        if info.filename == 'word/document.xml':
                            self.assertIn(ORIGINAL_QUOTA.encode(), part)
                            part = part.replace(ORIGINAL_QUOTA.encode(), escape(quota).encode())
                        target.writestr(info, part)
                data = output.getvalue()
            (inbox / filename).write_bytes(data)
            result = document_intake.inspect('northstar', filename, role)
            manifest = Path(result['manifest_path'])
            meta = json.loads(manifest.read_text())
            intake_gate.dump_exclusive(manifest.with_name(manifest.name.replace('.manifest.json', '.review.json')), {
                'schema': '1', 'project': 'northstar', 'original': filename, 'role': role,
                'source_sha256': meta['source_sha256'], 'extraction_sha256': meta['extraction_sha256'],
                'reviewer_attested_original_and_every_financial_row': True, 'warnings_human_resolved': True})

    def _certify_if_accepted(self):
        identity = intake_gate.snapshot_identity('northstar')
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        intake_gate.dump_exclusive(Path(self.temp.name) / 'attestations/northstar' / (key + '.json'), identity)

    def assert_document_quota_blocked(self, clause):
        self.change_quota(clause)
        self._stage_reviewed_documents(clause)
        # Even a fully affirmative synthetic human review cannot override terms.
        with self.assertRaisesRegex(ValueError, 'service terms'):
            self._certify_if_accepted()
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        for handler in (tools.scopeledger_audit, tools.scopeledger_draft):
            result = json.loads(handler({'project': 'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])
        self.assertFalse((Path(self.temp.name) / 'reports').exists())

    def test_negated_quota_original_documents_and_attestation(self):
        self.assert_document_quota_blocked('Not five landing pages are included.')

    def test_fractional_quota_original_documents_and_attestation(self):
        self.assert_document_quota_blocked('0.5 landing pages are included.')

    def test_contradictory_quota_original_documents_and_attestation(self):
        self.assert_document_quota_blocked('Five landing pages are included. Six landing pages are included.')

    def test_unsupported_decimal_original_documents_and_attestation(self):
        self.assert_document_quota_blocked('5.0 landing pages are included.')

    def test_valid_word_quota_original_documents(self):
        self._stage_reviewed_documents()
        self._certify_if_accepted()
        self.assertTrue(intake_gate.gate('northstar')['passed'])
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 30000)
        self.assertEqual(self.native_draft()['ready_minor'], 30000)

    def test_valid_digit_quota_original_documents(self):
        clause = '5 landing pages are included.'
        self.change_quota(clause)
        self._stage_reviewed_documents(clause)
        self._certify_if_accepted()
        self.assertTrue(intake_gate.gate('northstar')['passed'])
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 30000)
        self.assertEqual(self.native_draft()['ready_minor'], 30000)

    def test_unmapped_structured_source_invoice_cannot_be_attested(self):
        self.append_source(EXTRA_INVOICE)
        self._stage_reviewed_documents()
        with self.assertRaisesRegex(ValueError, '(?i)unreconciled.*invoice|invoice.*reconcil'):
            self._certify_if_accepted()
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        for handler in (tools.scopeledger_audit, tools.scopeledger_draft):
            result = json.loads(handler({'project': 'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])
