"""Adversarial contract/approval/delivery statements, using fictional isolated ledgers."""
import json
import csv
from pathlib import Path
import unittest

import test_financial_integrity as fixtures
import test_approval_context as context_fixtures
from scopeledger import auditor, evidence_semantics, tools


class CompleteStatementTests(unittest.TestCase):
    setUp = fixtures.FinancialIntegrityTests.setUp
    native_audit = fixtures.FinancialIntegrityTests.native_audit
    native_draft = fixtures.FinancialIntegrityTests.native_draft
    stage_originals = context_fixtures.ApprovalContextTests.stage_originals
    _certify_if_accepted = fixtures.FinancialIntegrityTests._certify_if_accepted

    def _replace(self, filename, old, new):
        path = self.proj / filename
        before = path.read_text()
        self.assertIn(old, before)
        if filename.endswith('.csv') and ',' in new and ',' not in old:
            # Preserve CSV structure when a quoted evidence field has commas.
            import io
            reader = csv.DictReader(io.StringIO(before))
            records = list(reader)
            self.assertEqual(sum(old in str(value) for row in records for value in row.values()), 1)
            for row in records:
                for key, value in row.items():
                    if value and old in value:
                        row[key] = value.replace(old, new, 1)
            with path.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
                writer.writeheader()
                writer.writerows(records)
        else:
            path.write_text(before.replace(old, new, 1))

    def _rejected_revision(self, text):
        old = 'Please send pricing for the extra revision round first.'
        self._replace('approvals.csv', 'A002,D004,PENDING,0,', 'A002,D004,REJECTED,0,')
        self._replace('approvals.csv', old, text)
        self._replace('sources/client_messages.txt', old, text)

    def _delivery(self, text):
        old = 'Delivered five original landing pages on October 20.'
        self._replace('deliveries.csv', old, text)
        self._replace('sources/work_log.txt', old, text)

    def assert_no_ready(self, audit):
        self.assertEqual(audit['totals']['ready_minor'], 0, audit)
        self.assertFalse(any(f['status'] == 'READY_FOR_OWNER_REVIEW' for f in audit['findings']), audit)
        self.assertEqual(self.native_draft()['ready_minor'], 0)

    def test_mapped_rejection_must_not_account_for_other_service_denial(self):
        self._rejected_revision('I do not approve the extra revision round. I do not approve any additional landing pages.')
        self.assert_no_ready(self.native_audit())

    def test_two_denials_with_alternative_wording_are_not_a_single_rejection(self):
        self._rejected_revision('I reject the extra revision round. Approval denied for the additional landing pages.')
        self.assert_no_ready(self.native_audit())

    def test_valid_single_rejection_remains_accepted(self):
        self._rejected_revision('I do not approve the extra revision round.')
        audit = self.native_audit()
        self.assertEqual(audit['totals']['ready_minor'], 30000, audit)
        self.assertTrue(audit['source_context_complete'], audit)

    def test_retracted_delivery_does_not_consume_quota(self):
        self._delivery('Delivered five original landing pages on October 20. Correction: these five pages were never delivered.')
        self.assert_no_ready(self.native_audit())

    def test_forecast_delivery_does_not_consume_quota(self):
        self._delivery('Delivered five original landing pages on October 20. This entry is a forecast, not completed work.')
        self.assert_no_ready(self.native_audit())

    def test_conditional_delivery_does_not_consume_quota(self):
        self._delivery('Delivered five original landing pages on condition that the deposit is received.')
        self.assert_no_ready(self.native_audit())

    def test_unsupported_delivery_date_is_rejected(self):
        self._delivery('Delivered five original landing pages on someday.')
        self.assert_no_ready(self.native_audit())

    def test_wrong_delivery_date_is_rejected(self):
        self._delivery('Delivered five original landing pages on October 21.')
        self.assert_no_ready(self.native_audit())

    def test_valid_iso_delivery_date_still_works(self):
        self._delivery('Delivered five original landing pages on 2026-10-20.')
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 30000)

    def test_existing_valid_northstar_still_works(self):
        audit = self.native_audit()
        self.assertEqual(audit['totals']['ready_minor'], 30000)
        self.assertEqual(audit['totals']['possible_minor'], 15000)
        self.assertEqual(self.native_draft()['ready_minor'], 30000)

    def test_two_service_denials_block_original_document_attestation(self):
        self._rejected_revision('I do not approve the extra revision round. I do not approve any additional landing pages.')
        self.stage_originals()
        with self.assertRaises(ValueError):
            self._certify_if_accepted()
        from scopeledger import intake_gate
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        for handler in (tools.scopeledger_audit, tools.scopeledger_draft):
            result = json.loads(handler({'project':'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])

    def test_retracted_delivery_blocks_original_document_attestation(self):
        self._delivery('Delivered five original landing pages on October 20. Correction: these five pages were never delivered.')
        self.stage_originals()
        with self.assertRaises(ValueError):
            self._certify_if_accepted()
        from scopeledger import intake_gate
        self.assertFalse(intake_gate.gate('northstar')['passed'])
        for handler in (tools.scopeledger_audit, tools.scopeledger_draft):
            result = json.loads(handler({'project':'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])

    def test_valid_rejection_and_original_documents_certify(self):
        self._rejected_revision('I do not approve the extra revision round.')
        self.stage_originals()
        self._certify_if_accepted()
        from scopeledger import intake_gate
        self.assertTrue(intake_gate.gate('northstar')['passed'])
        self.assertEqual(self.native_audit()['totals']['ready_minor'], 30000)
        self.assertEqual(self.native_draft()['ready_minor'], 30000)

    def test_unmapped_delivery_retraction_in_work_log_blocks_without_affecting_unrelated_prose(self):
        path = self.proj / 'sources/work_log.txt'
        path.write_text(path.read_text() + '\nD001 correction: these five pages were never delivered.\n')
        self.assert_no_ready(self.native_audit())

    def test_semantic_complete_statement_helpers(self):
        rev={'label':'Revision round'}
        landing={'label':'Landing page'}
        for text in ('I do not approve the extra revision round. I do not approve any additional landing pages.',
                     'I reject the extra revision round. Approval denied for the additional landing pages.',
                     'I do not approve the extra revision round, subject to later authorization.'):
            with self.subTest(text=text):
                self.assertFalse(evidence_semantics.approval_quote(text, 'REJECTED', 0, rev, 'USD', 15000)['semantic_verified'])
        for text in ('Delivered five original landing pages on October 20. Correction: these five pages were never delivered.',
                     'Delivered five original landing pages on condition that the deposit is received.',
                     'Delivered five original landing pages on October 20. This entry is a forecast, not completed work.'):
            with self.subTest(text=text):
                self.assertFalse(evidence_semantics.delivery_quote(text, 5, landing)['semantic_verified'])


if __name__ == '__main__':
    unittest.main()
