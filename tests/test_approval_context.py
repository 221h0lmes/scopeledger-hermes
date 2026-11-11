"""Fictional approval/invoice context checks across wrapping and source positions."""
import json
from pathlib import Path
import re
import unittest

import test_financial_integrity as fixtures
import test_release_repairs as document_fixtures
from scopeledger import auditor, document_intake, intake_gate, tools

DENIAL = 'D002 | I do not\napprove any additional landing pages.'
CONDITION = 'The following approvals apply only after a separate purchase order is signed.'
PAID = 'Invoice INV-EXTRA: one additional landing page, USD three hundred, paid.'


class ApprovalContextTests(unittest.TestCase):
    setUp = fixtures.FinancialIntegrityTests.setUp
    native_audit = fixtures.FinancialIntegrityTests.native_audit
    native_draft = fixtures.FinancialIntegrityTests.native_draft
    _certify_if_accepted = fixtures.FinancialIntegrityTests._certify_if_accepted

    def insert(self, filename, text, position):
        path = self.proj / 'sources' / filename
        old = path.read_text() if path.exists() else ''
        if position == 'before':
            value = text + '\n' + old
        elif position == 'after_title':
            first, remainder = old.split('\n', 1)
            value = first + '\n' + text + '\n' + remainder
        else:
            value = old + text + '\n'
        path.write_text(value)

    def stage_originals(self):
        inbox = Path(self.temp.name) / 'inbox/northstar'
        inbox.mkdir(parents=True)
        for role, source in (('agreement', 'agreement.txt'), ('deliveries', 'work_log.txt'),
                             ('approvals', 'client_messages.txt'), ('invoices', 'invoices.txt')):
            filename = role + '.docx'
            text = (self.proj / 'sources' / source).read_text()
            (inbox / filename).write_bytes(document_fixtures.ReleaseRepairTests._docx_bytes(self, text))
            result = document_intake.inspect('northstar', filename, role)
            manifest = Path(result['manifest_path'])
            meta = json.loads(manifest.read_text())
            intake_gate.dump_exclusive(manifest.with_name(manifest.name.replace('.manifest.json', '.review.json')), {
                'schema': '1', 'project': 'northstar', 'original': filename, 'role': role,
                'source_sha256': meta['source_sha256'], 'extraction_sha256': meta['extraction_sha256'],
                'reviewer_attested_original_and_every_financial_row': True, 'warnings_human_resolved': True})

    def assert_blocked_originals(self):
        self.stage_originals()
        with self.assertRaises(ValueError):
            self._certify_if_accepted()
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        for handler in (tools.scopeledger_audit, tools.scopeledger_draft):
            result = json.loads(handler({'project': 'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])

    def assert_zero_structured(self):
        audit = self.native_audit()
        self.assertEqual(audit['totals']['ready_minor'], 0)
        self.assertTrue(audit['errors'])
        self.assertFalse(any(item['status'] == 'READY_FOR_OWNER_REVIEW' for item in audit['findings']))
        draft = self.native_draft()
        self.assertEqual(draft['ready_minor'], 0)
        markdown = Path(draft['draft_path']).read_text()
        amount = next(line for line in markdown.splitlines() if line.startswith('- Sourced, approved'))
        self.assertIn('**USD 0.00**', amount)
        self.assertEqual(re.search(r'<div class="value">(.*?)</div>', Path(draft['html_preview_path']).read_text())[1], 'USD 0.00')
        return audit

    def test_wrapped_denial_in_supplement_both_workflows(self):
        self.insert('supplement.txt', DENIAL, 'after')
        audit = self.assert_zero_structured()
        self.assertIn('unaccounted denial', '\n'.join(audit['errors']))
        self.assertEqual(audit['totals']['possible_minor'], 0)
        self.assert_blocked_originals()

    def test_unwrapped_denial_in_supplement_both_workflows(self):
        self.insert('supplement.txt', DENIAL.replace('\n', ' '), 'after')
        self.assert_zero_structured()
        self.assert_blocked_originals()

    def test_wrapped_denial_before_approval_records_both_workflows(self):
        self.insert('client_messages.txt', DENIAL.split(' | ', 1)[1], 'before')
        self.assert_zero_structured()
        self.assert_blocked_originals()

    def test_unwrapped_denial_before_approval_records_both_workflows(self):
        self.insert('client_messages.txt', DENIAL.split(' | ', 1)[1].replace('\n', ' '), 'before')
        self.assert_zero_structured()
        self.assert_blocked_originals()

    def test_conditional_approval_preamble_both_workflows(self):
        self.insert('client_messages.txt', CONDITION, 'before')
        self.assert_zero_structured()
        self.assert_blocked_originals()

    def test_conditional_approval_footer_both_workflows(self):
        self.insert('client_messages.txt', CONDITION, 'after')
        self.assert_zero_structured()
        self.assert_blocked_originals()

    def test_paid_invoice_preamble_both_workflows(self):
        self.insert('invoices.txt', PAID, 'before')
        audit = self.assert_zero_structured()
        self.assertFalse(audit['ledger_complete'])
        self.assert_blocked_originals()

    def test_paid_invoice_footer_both_workflows(self):
        self.insert('invoices.txt', PAID, 'after')
        audit = self.assert_zero_structured()
        self.assertFalse(audit['ledger_complete'])
        self.assert_blocked_originals()

    def test_paid_invoice_unlinked_supplement_both_workflows(self):
        self.insert('supplement.txt', PAID, 'after')
        self.assert_zero_structured()
        self.assert_blocked_originals()

    def test_conditional_approval_unlinked_supplement_both_workflows(self):
        self.insert('supplement.txt', CONDITION, 'after')
        self.assert_zero_structured()
        self.assert_blocked_originals()

    def test_unknown_context_cannot_be_exempted_by_position_or_keywords(self):
        files = ('client_messages.txt', 'invoices.txt')
        positions = ('before', 'after_title', 'after')
        statements = (CONDITION, PAID, 'The prior decision is hereby countermanded.',
                      'A separate signature is still necessary.', 'Nothing above is operative yet.')
        originals = {name: (self.proj / 'sources' / name).read_text() for name in files}
        for filename in files:
            for position in positions:
                for statement in statements:
                    path = self.proj / 'sources' / filename
                    path.write_text(originals[filename])
                    self.insert(filename, statement, position)
                    with self.subTest(filename=filename, position=position, statement=statement):
                        result = auditor.analyze(self.proj)
                        self.assertEqual(result['totals']['ready_minor'], 0)
                        self.assertFalse(result['source_context_complete'])
                    path.write_text(originals[filename])

    def test_denial_detection_is_invariant_at_each_word_boundary(self):
        statement = 'D002 | I do not approve any additional landing pages.'
        path = self.proj / 'sources/supplement.txt'
        for whitespace in ('\n', '\r\n', '\n\n', '\t', '\u2028'):
            for position, char in enumerate(statement):
                if char != ' ':
                    continue
                path.write_text(statement[:position] + whitespace + statement[position + 1:] + '\n')
                with self.subTest(position=position, whitespace=repr(whitespace)):
                    result = auditor.analyze(self.proj)
                    self.assertEqual(result['totals']['ready_minor'], 0)
                    self.assertFalse(result['source_context_complete'])
                    self.assertIn('unaccounted denial', '\n'.join(result['errors']))

    def test_valid_northstar_sources_and_headings_still_certify(self):
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 30000)
        self.stage_originals()
        self._certify_if_accepted()
        self.assertTrue(intake_gate.gate('northstar')['passed'])
        result = self.native_audit()
        self.assertTrue(result['source_context_complete'])
        self.assertEqual(result['totals']['ready_minor'], 30000)
        self.assertEqual(result['totals']['possible_minor'], 15000)
        self.assertEqual(self.native_draft()['ready_minor'], 30000)

    def test_mapped_rejection_remains_accounted_and_certifiable(self):
        old = 'I approve the two additional landing pages at USD 300 each.'
        new = 'I do not approve the additional landing pages.'
        path = self.proj / 'approvals.csv'
        path.write_text(path.read_text().replace('A001,D002,APPROVED,2,', 'A001,D002,REJECTED,0,').replace(old, new))
        path = self.proj / 'sources/client_messages.txt'
        path.write_text(path.read_text().replace(old, new))
        result = self.native_audit()
        self.assertTrue(result['source_context_complete'])
        self.assertFalse(result['errors'])
        # The supplied partial invoice against this rejected work remains a
        # billing exception; its rejection itself is fully accounted for.
        item = next(item for item in result['findings'] if item['delivery_id'] == 'D002')
        self.assertEqual(item['status'], 'EVIDENCE_OR_BILLING_EXCEPTION')
        self.assertEqual(item['approved_extra_units'], 0)
        self.stage_originals()
        self._certify_if_accepted()
        self.assertTrue(intake_gate.gate('northstar')['passed'])
        self.assertEqual(self.native_draft()['ready_minor'], 0)

    def test_supported_administrative_prose_does_not_globally_block_invoices(self):
        self.insert('invoices.txt', 'Invoice questions may be discussed at the next team meeting.', 'after')
        self.insert('invoices.txt', 'This export includes a fictional demonstration for the owner.', 'after')
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 30000)
        self.stage_originals()
        self._certify_if_accepted()
        self.assertEqual(self.native_draft()['ready_minor'], 30000)
