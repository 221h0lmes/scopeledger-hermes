"""Cross-line context and report-directory race regressions; fictional data only."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import test_financial_integrity as fixtures
import test_release_repairs as docx_fixtures
from scopeledger import auditor, document_intake, evidence_semantics, intake_gate, tools

CONDITION = 'Only if a later written agreement is signed:\nFive landing pages are included.'
INAPPLICABLE = 'The following quota does not apply:\nFive landing pages are included.'
WRAPPED_INVOICE = 'D002 | Invoice INV-204\nbilled one additional landing page at USD 300.'
SERVICE = {'label': 'Landing page', 'included_units': 5, 'extra_unit_price_minor': 30000}


class ContextIntegrityTests(unittest.TestCase):
    setUp = fixtures.FinancialIntegrityTests.setUp
    append_source = fixtures.FinancialIntegrityTests.append_source
    native_audit = fixtures.FinancialIntegrityTests.native_audit
    native_draft = fixtures.FinancialIntegrityTests.native_draft
    change_quota = fixtures.FinancialIntegrityTests.change_quota
    _stage_reviewed_documents = fixtures.FinancialIntegrityTests._stage_reviewed_documents
    _certify_if_accepted = fixtures.FinancialIntegrityTests._certify_if_accepted
    assert_document_quota_blocked = fixtures.FinancialIntegrityTests.assert_document_quota_blocked
    assert_quota_blocked = fixtures.FinancialIntegrityTests.assert_quota_blocked

    def assert_zero_in_reports(self, draft):
        self.assertEqual(draft['ready_minor'], 0)
        markdown = Path(draft['draft_path']).read_text()
        amount_line = next(line for line in markdown.splitlines() if line.startswith('- Sourced, approved'))
        self.assertIn('**USD 0.00**', amount_line)
        html = Path(draft['html_preview_path']).read_text()
        self.assertEqual(re.search(r'<div class="value">(.*?)</div>', html)[1], 'USD 0.00')

    def assert_original_tools_blocked(self):
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        for handler in (tools.scopeledger_audit, tools.scopeledger_draft):
            result = json.loads(handler({'project': 'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])

    def test_wrapped_omitted_invoice_native_audit_and_both_reports(self):
        self.append_source(WRAPPED_INVOICE)
        audit = self.native_audit()
        self.assertEqual(audit['totals']['ready_minor'], 0)
        self.assertFalse(audit['ledger_complete'])
        self.assertIn('INV-204', '\n'.join(audit['errors']))
        self.assertIn('sources/invoices.txt:4', '\n'.join(audit['errors']))
        self.assert_zero_in_reports(self.native_draft())

    def test_wrapped_invoice_in_unlinked_supplement_blocks_originals(self):
        self.append_source(WRAPPED_INVOICE, 'supplement.txt')
        self._stage_reviewed_documents()
        with self.assertRaisesRegex(ValueError, '(?i)unreconciled.*invoice'):
            self._certify_if_accepted()
        self.assert_original_tools_blocked()

    def test_wrapped_invoice_also_in_original_blocks(self):
        self.append_source(WRAPPED_INVOICE)
        self._stage_reviewed_documents()
        # Replace the invoice original with a new fictional DOCX containing
        # exactly the supplied source text; discard only this test's old PDF.
        inbox = Path(self.temp.name) / 'inbox/northstar'
        (inbox / 'northstar_invoices.pdf').unlink()
        make_docx = docx_fixtures.ReleaseRepairTests._docx_bytes
        (inbox / 'wrapped.docx').write_bytes(make_docx(self, (self.proj / 'sources/invoices.txt').read_text()))
        result = document_intake.inspect('northstar', 'wrapped.docx', 'invoices')
        manifest = Path(result['manifest_path'])
        meta = json.loads(manifest.read_text())
        intake_gate.dump_exclusive(manifest.with_name(manifest.name.replace('.manifest.json', '.review.json')), {
            'schema': '1', 'project': 'northstar', 'original': 'wrapped.docx', 'role': 'invoices',
            'source_sha256': meta['source_sha256'], 'extraction_sha256': meta['extraction_sha256'],
            'reviewer_attested_original_and_every_financial_row': True, 'warnings_human_resolved': True})
        with self.assertRaises(ValueError):
            self._certify_if_accepted()
        self.assert_original_tools_blocked()

    def test_invoice_detection_independent_of_word_wrap_and_source_filename(self):
        statement = 'D002 | Invoice INV-204 billed one additional landing page at USD 300.'
        frozen = auditor._capture_project_inputs(self.proj)
        for whitespace in ('\n', '\r\n', '\n\n', '\t', '\u2028'):
            for position, char in enumerate(statement):
                if char != ' ':
                    continue
                wrapped = statement[:position] + whitespace + statement[position + 1:]
                with self.subTest(whitespace=repr(whitespace), position=position):
                    source = dict(frozen)
                    source['sources/unlinked.txt'] = (wrapped + '\n').encode()
                    errors = auditor._reconcile_invoice_sources(source, {}, {'landing_page': SERVICE})
                    self.assertTrue(any('INV-204' in error for error in errors), (wrapped, errors))

    def test_same_line_condition_control(self):
        self.assert_quota_blocked(CONDITION.replace('\n', ' '))

    def test_separate_line_condition_structured_audit_and_reports(self):
        self.assert_quota_blocked(CONDITION)
        self.assert_zero_in_reports(self.native_draft())

    def test_separate_line_negation_structured_audit_and_reports(self):
        self.assert_quota_blocked(INAPPLICABLE)
        self.assert_zero_in_reports(self.native_draft())

    def test_separate_line_condition_original_documents(self):
        self.assert_document_quota_blocked(CONDITION)

    def test_separate_line_negation_original_documents(self):
        self.assert_document_quota_blocked(INAPPLICABLE)

    def test_unknown_contract_context_is_never_silently_dropped(self):
        base = 'Five landing pages are included. Additional landing pages: USD 300 each.'
        for context in ('Only if a later written agreement is signed:',
                        'The following quota does not apply:',
                        'These terms need a separate countersignature.',
                        'Everything below is an unaccepted proposal.',
                        'The amounts above depend on a later settlement.',
                        'The prior decision is hereby countermanded.'):
            for whitespace in (' ', '\n', '\r\n', '\n\n', '\t'):
                for text in (context + whitespace + base, base + whitespace + context):
                    with self.subTest(text=text):
                        self.assertFalse(evidence_semantics.contract_terms(text, SERVICE, 'USD')['semantic_verified'])

    def test_valid_contract_financial_text_is_invariant_under_word_wrap(self):
        base = 'Five landing pages are included. Additional landing pages: USD 300 each.'
        for whitespace in ('\n', '\r\n', '\n\n', '\t', '\u2028'):
            for position, char in enumerate(base):
                if char == ' ':
                    text = base[:position] + whitespace + base[position + 1:]
                    with self.subTest(text=text):
                        self.assertTrue(evidence_semantics.contract_terms(text, SERVICE, 'USD')['semantic_verified'])

    def test_unsupported_qualified_service_is_not_ignored_as_another_service(self):
        base = 'Five landing pages are included. Additional landing pages: USD 300 each.'
        for extra in ('Zero of the previous landing pages are included.',
                      'One separate condition are included.',
                      'Additional conditional landing pages: USD 900 each.'):
            with self.subTest(extra=extra):
                self.assertFalse(evidence_semantics.contract_terms(base + '\n' + extra, SERVICE, 'USD')['semantic_verified'])

    def test_valid_expanded_delivery_remains_600_in_both_workflows(self):
        for filename in ('deliveries.csv', 'sources/work_log.txt'):
            path = self.proj / filename
            path.write_text(path.read_text().replace('D002,landing_page,2,', 'D002,landing_page,3,')
                            .replace('Delivered two additional', 'Delivered three additional'))
        for filename in ('approvals.csv', 'sources/client_messages.txt'):
            path = self.proj / filename
            path.write_text(path.read_text().replace('A001,D002,APPROVED,2,', 'A001,D002,APPROVED,3,')
                            .replace('approve the two', 'approve the three'))
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 60000)
        self.assertEqual(self.native_draft()['ready_minor'], 60000)
        # Build originals from updated fictional source text, including changed
        # delivery/approval quantities, using the same real intake and gate.
        inbox = Path(self.temp.name) / 'inbox/northstar'
        inbox.mkdir(parents=True)
        for role, source in (('agreement', 'agreement.txt'), ('deliveries', 'work_log.txt'),
                             ('approvals', 'client_messages.txt'), ('invoices', 'invoices.txt')):
            filename = role + '.docx'
            data = docx_fixtures.ReleaseRepairTests._docx_bytes(self, (self.proj / 'sources' / source).read_text())
            (inbox / filename).write_bytes(data)
            result = document_intake.inspect('northstar', filename, role)
            manifest = Path(result['manifest_path'])
            meta = json.loads(manifest.read_text())
            intake_gate.dump_exclusive(manifest.with_name(manifest.name.replace('.manifest.json', '.review.json')), {
                'schema': '1', 'project': 'northstar', 'original': filename, 'role': role,
                'source_sha256': meta['source_sha256'], 'extraction_sha256': meta['extraction_sha256'],
                'reviewer_attested_original_and_every_financial_row': True, 'warnings_human_resolved': True})
        self._certify_if_accepted()
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 60000)
        self.assertEqual(self.native_draft()['ready_minor'], 60000)

    def _swap_reports(self, stage):
        root = Path(self.temp.name)
        with tempfile.TemporaryDirectory() as outside:
            folder = root / 'reports'
            original_lock = tools._report_lock
            original_write = tools._write_snapshot_once
            calls = []
            def swap():
                folder.rename(root / 'secured-reports')
                folder.symlink_to(outside, target_is_directory=True)
            @contextmanager
            def lock(path):
                if stage == 'before_lock':
                    swap()
                with original_lock(path) as secured:
                    yield secured
            def write(target, text, *args, **kwargs):
                calls.append(target)
                if (stage == 'before_first_write' and len(calls) == 1) or (stage == 'between_reports' and len(calls) == 2):
                    swap()
                return original_write(target, text, *args, **kwargs)
            with patch.object(tools, '_report_lock', side_effect=lock), patch.object(tools, '_write_snapshot_once', side_effect=write):
                result = json.loads(tools.scopeledger_draft({'project': 'northstar'}))
            self.assertEqual(list(Path(outside).iterdir()), [], result)
            self.assertFalse(result['ok'], result)

    def test_report_directory_swap_before_lock_writes_nothing_outside(self):
        self._swap_reports('before_lock')

    def test_report_directory_swap_after_lock_writes_nothing_outside(self):
        self._swap_reports('before_first_write')

    def test_report_directory_swap_between_outputs_writes_nothing_outside(self):
        self._swap_reports('between_reports')

    def test_report_lock_leaf_symlink_is_rejected(self):
        folder = Path(self.temp.name) / 'reports'
        folder.mkdir()
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'lock'
            external.write_text('unchanged')
            (folder / '.scopeledger.lock').symlink_to(external)
            result = json.loads(tools.scopeledger_draft({'project': 'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertEqual(external.read_text(), 'unchanged')
            self.assertEqual(len(list(Path(outside).iterdir())), 1)

    def test_report_directory_replaced_with_regular_directory_is_detected(self):
        root = Path(self.temp.name)
        folder = root / 'reports'
        original = tools._write_snapshot_once
        calls = []
        def swapped(target, text, **kwargs):
            calls.append(target)
            if len(calls) == 1:
                folder.rename(root / 'secured-reports')
                folder.mkdir()
            return original(target, text, **kwargs)
        with patch.object(tools, '_write_snapshot_once', side_effect=swapped):
            result = json.loads(tools.scopeledger_draft({'project': 'northstar'}))
        self.assertFalse(result['ok'], result)
        self.assertEqual(list(folder.iterdir()), [])
        self.assertEqual(len(list((root / 'secured-reports').glob('*owner-review.*'))), 2)
