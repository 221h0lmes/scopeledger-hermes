"""Deterministic adversarial regressions; all evidence and receipts are fictional."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
from xml.sax.saxutils import escape

import test_documents as fixtures
from scopeledger import auditor, document_intake as intake, intake_gate, tools


class ReleaseRepairTests(unittest.TestCase):
    setUp = fixtures.DocumentTests.setUp
    stage = fixtures.DocumentTests.stage
    _attest_four_fictional_documents = fixtures.DocumentTests._attest_four_fictional_documents
    def _stage_extra_docx(self, filename, role, paragraph):
        (self.inbox / filename).write_bytes(self._docx_bytes(paragraph))
        result = intake.inspect('northstar', filename, role)
        manifest = Path(result['manifest_path'])
        meta = json.loads(manifest.read_text())
        intake_gate.dump_exclusive(manifest.with_name(manifest.name.replace('.manifest.json', '.review.json')), {
            'schema': '1', 'project': 'northstar', 'original': filename, 'role': role,
            'source_sha256': meta['source_sha256'], 'extraction_sha256': meta['extraction_sha256'],
            'reviewer_attested_original_and_every_financial_row': True, 'warnings_human_resolved': True})

    def attempt_synthetic_mapping(self):
        try:
            identity = intake_gate.snapshot_identity('northstar')
        except ValueError:
            return
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        intake_gate.dump_exclusive(Path(self.tmp.name) / 'attestations/northstar' / (key + '.json'), identity)

    def assert_financial_tools_blocked(self):
        self.attempt_synthetic_mapping()
        for handler in (tools.scopeledger_audit, tools.scopeledger_draft):
            result = json.loads(handler({'project': 'northstar'}))
            self.assertFalse(result['ok'], result)
            self.assertIn('SOURCE_VERIFICATION_BLOCKED', result['message'])
        self.assertFalse((Path(self.tmp.name) / 'reports').exists())

    def test_invoice_reassigned_with_rewritten_structured_source(self):
        self._attest_four_fictional_documents()
        csv = self.project / 'invoices.csv'
        csv.write_text(csv.read_text().replace('I001,D002,', 'I001,D001,'))
        source = self.project / 'sources/invoices.txt'
        source.write_text(source.read_text().replace('D002 |', 'D001 |'))
        # Even a synthetic affirmative mapping cannot certify this mismatch.
        with self.assertRaisesRegex(ValueError, 'invoices:.*delivery'):
            intake_gate.snapshot_identity('northstar')
        self.assert_financial_tools_blocked()
        raw = auditor.analyze(self.project)
        self.assertEqual(raw['totals']['ready_minor'], 0, raw)
        self.assertFalse(raw['ledger_complete'])
        self.assertEqual(next(f for f in raw['findings'] if f['delivery_id'] == 'D001')['status'],
                         'IN_SCOPE_INVOICE_EXCEPTION')

    def test_invoice_reassigned_without_rewriting_source(self):
        self._attest_four_fictional_documents()
        csv = self.project / 'invoices.csv'
        csv.write_text(csv.read_text().replace('I001,D002,', 'I001,D001,'))
        with self.assertRaisesRegex(ValueError, 'invoices:.*delivery'):
            intake_gate.snapshot_identity('northstar')
        self.assert_financial_tools_blocked()

    def test_duplicate_invoice_identity_cannot_map_twice(self):
        self._attest_four_fictional_documents()
        csv = self.project / 'invoices.csv'
        row = csv.read_text().splitlines()[1].replace('I001,', 'I099,')
        csv.write_text(csv.read_text() + row + '\n')
        with self.assertRaisesRegex(ValueError, 'invoices:.*(?:occurrence|reused|duplicate)'):
            intake_gate.snapshot_identity('northstar')
        self.assert_financial_tools_blocked()

    def test_invoice_quantity_must_match_original(self):
        self._attest_four_fictional_documents()
        csv = self.project / 'invoices.csv'
        csv.write_text(csv.read_text().replace('I001,D002,1,', 'I001,D002,2,'))
        with self.assertRaisesRegex(ValueError, 'invoices:.*(?:quantity|fields)'):
            intake_gate.snapshot_identity('northstar')
        self.assert_financial_tools_blocked()

    def test_approval_denial_without_digits(self):
        self._attest_four_fictional_documents()
        self._stage_extra_docx('denial.docx', 'approvals',
                               'I do not approve any additional landing pages.')
        self.assert_financial_tools_blocked()
        with self.assertRaisesRegex(ValueError, 'revocation|reconciliation'):
            intake_gate.snapshot_identity('northstar')

    def test_page_prefix_does_not_hide_invoice(self):
        self._attest_four_fictional_documents()
        self._stage_extra_docx('page_prefix.docx', 'invoices',
                               '[PAGE 1] D002 | Invoice INV-999 billed one additional landing page at USD 300.')
        with self.assertRaisesRegex(ValueError, 'extra/unmapped'):
            intake_gate.snapshot_identity('northstar')
        self.assert_financial_tools_blocked()

    def test_agreement_credit(self):
        self._attest_four_fictional_documents()
        self._stage_extra_docx('credit.docx', 'agreement',
                               'Credit USD 300.00 applies against additional landing pages.')
        self.assert_financial_tools_blocked()
        with self.assertRaisesRegex(ValueError, 'credit|adjustment|reconciliation'):
            intake_gate.snapshot_identity('northstar')

    def test_unrecognized_text_without_financial_keywords_is_not_dropped(self):
        self._attest_four_fictional_documents()
        self._stage_extra_docx('unsupported.docx', 'approvals',
                               'The prior decision is hereby countermanded.')
        self.assert_financial_tools_blocked()

    def test_unmapped_agreement_clause(self):
        self._attest_four_fictional_documents()
        self._stage_extra_docx('amendment.docx', 'agreement',
                               'Everything above is subject to a separate settlement.')
        self.assert_financial_tools_blocked()

    def test_structured_credit_withholds_ready_and_draft_amount(self):
        self.inbox.rmdir()
        source = self.project / 'sources/agreement.txt'
        source.write_text(source.read_text() + '\nCredit USD 300.00 applies against additional landing pages.\n')
        result = json.loads(tools.scopeledger_audit({'project': 'northstar'}))
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['audit']['totals']['ready_minor'], 0)
        draft = json.loads(tools.scopeledger_draft({'project': 'northstar'}))
        self.assertTrue(draft['ok'], draft)
        self.assertEqual(draft['ready_minor'], 0)

    def _docx_bytes(self, paragraph):
        output = io.BytesIO()
        with zipfile.ZipFile(fixtures.ROOT / 'tests/fixtures/northstar_agreement.docx') as src:
            with zipfile.ZipFile(output, 'w') as dst:
                for entry in src.infolist():
                    data = src.read(entry.filename)
                    if entry.filename == 'word/document.xml':
                        prefix = data[:data.index(b'<w:body>')]
                        data = prefix + ('<w:body><w:p><w:r><w:t>' + escape(paragraph) +
                                         '</w:t></w:r></w:p></w:body></w:document>').encode()
                    dst.writestr(entry, data)
        return output.getvalue()

    def test_docx_change_and_restore_parses_hashed_snapshot(self):
        path = self.inbox / 'snapshot.docx'
        text = 'D002 | Invoice INV-999 billed one additional landing page at USD 300.'
        original = self._docx_bytes(text)
        replacement = self._docx_bytes('Invoice notes')
        path.write_bytes(original)
        parse = intake._docx
        def swap(data, live_path):
            path.write_bytes(replacement)
            try:
                return parse(data, live_path)
            finally:
                path.write_bytes(original)
        with patch.object(intake, '_docx', side_effect=swap):
            result = intake.inspect('northstar', path.name, 'invoices')
        extracted = Path(result['extracted_path']).read_bytes()
        manifest = json.loads(Path(result['manifest_path']).read_text())
        self.assertIn(text, extracted.decode())
        self.assertNotIn('Invoice notes', extracted.decode())
        self.assertEqual(manifest['source_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(manifest['extraction_sha256'], hashlib.sha256(extracted).hexdigest())
        self.assertEqual(manifest['page_coverage'][0]['characters'], len(text))
        self.assertEqual(manifest['page_coverage'][0]['numeric_tokens'], sorted(intake.DIGIT.findall(text)))

    def test_docx_secondary_parser_uses_bytes(self):
        path = self.inbox / 'secondary.docx'
        original = self._docx_bytes('Original snapshot contents')
        path.write_bytes(original)
        captured = []
        def check(input_file):
            if not hasattr(input_file, 'read'):
                raise AssertionError('Secondary parser reopened source pathname')
            captured.append(input_file.getvalue())
            return types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text='Original snapshot contents')])
        # Exercise the optional parser contract even when python-docx is absent.
        with patch.dict('sys.modules', {'docx': types.SimpleNamespace(Document=check)}):
            result = intake.inspect('northstar', path.name, 'invoices')
        self.assertEqual(captured, [original], result['issues'])

    def test_pdf_snapshot_is_removed_on_parser_failure(self):
        self.stage('northstar_invoices.pdf')
        paths = []
        def fail(args, **kwargs):
            paths.append(Path(args[1]))
            raise intake.subprocess.CalledProcessError(1, args)
        with patch.object(intake.subprocess, 'run', side_effect=fail):
            with self.assertRaisesRegex(ValueError, 'Poppler'):
                intake.inspect('northstar', 'northstar_invoices.pdf', 'invoices')
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() and not path.parent.exists() for path in paths))

    def test_pdf_change_and_restore_all_parsers_share_snapshot(self):
        self.stage('northstar_invoices.pdf')
        path = self.inbox / 'northstar_invoices.pdf'
        original = path.read_bytes()
        self.stage('northstar_deliveries.pdf')
        replacement = (self.inbox / 'northstar_deliveries.pdf').read_bytes()
        parse = intake._pdf
        run = intake.subprocess.run
        snapshot_paths = []
        secondary_inputs = []
        class SecondaryPDF:
            page_count = 1
            def __iter__(self):
                return iter([types.SimpleNamespace(get_text=lambda _: 'Invoice INV-203 USD 300')])
            def close(self):
                pass
        def secondary(*, stream, filetype):
            secondary_inputs.append(stream)
            self.assertEqual(filetype, 'pdf')
            return SecondaryPDF()
        def check(args, **kwargs):
            snapshot = Path(args[1] if args[0] == 'pdfinfo' else args[-2])
            self.assertNotEqual(snapshot, path)
            self.assertEqual(snapshot.read_bytes(), original)
            snapshot_paths.append(snapshot)
            return run(args, **kwargs)
        def swap(data, live_path):
            path.write_bytes(replacement)
            try:
                with patch.object(intake.subprocess, 'run', side_effect=check):
                    return parse(data, live_path)
            finally:
                path.write_bytes(original)
        with patch.object(intake, '_pdf', side_effect=swap), patch.dict(
                'sys.modules', {'fitz': types.SimpleNamespace(open=secondary)}):
            result = intake.inspect('northstar', path.name, 'invoices')
        self.assertIn('INV-203', Path(result['extracted_path']).read_text())
        self.assertTrue(snapshot_paths)
        self.assertTrue(all(not p.exists() for p in snapshot_paths))
        self.assertEqual(result['source_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(secondary_inputs, [original])

    def test_legacy_extraction_requires_new_snapshot_provenance(self):
        self._attest_four_fictional_documents()
        for manifest in (Path(self.tmp.name) / 'extractions').rglob('*.manifest.json'):
            meta = json.loads(manifest.read_text())
            meta.pop('input_snapshot')
            manifest.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, 'predates captured-byte provenance'):
            intake_gate.snapshot_identity('northstar')
        self.assert_financial_tools_blocked()

    def test_marker_symlink_ancestor_writes_nothing_outside(self):
        self.stage('northstar_agreement.docx')
        with tempfile.TemporaryDirectory() as outside:
            (Path(self.tmp.name) / 'document_intake_required').symlink_to(outside, target_is_directory=True)
            result = json.loads(tools.scopeledger_document({
                'project': 'northstar', 'filename': 'northstar_agreement.docx', 'role': 'agreement'}))
            self.assertFalse(result['ok'], result)
            self.assertEqual(list(Path(outside).iterdir()), [])
            self.assertFalse((Path(self.tmp.name) / 'extractions').exists())

    def test_attestation_symlink_ancestor_writes_nothing_outside(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(self.tmp.name) / 'attestations').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                intake_gate.dump_exclusive(Path(self.tmp.name) / 'attestations/northstar/receipt.json', {'fictional': True})
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_attestation_write_is_immutable_and_atomic(self):
        target = Path(self.tmp.name) / 'attestations/northstar/receipt.json'
        intake_gate.dump_exclusive(target, {'fictional': True})
        before = target.read_bytes()
        intake_gate.dump_exclusive(target, {'fictional': True})
        with self.assertRaises(ValueError):
            intake_gate.dump_exclusive(target, {'fictional': False})
        self.assertEqual(target.read_bytes(), before)
        target.unlink()
        # Interrupted publication must never leave a partial final receipt.
        with patch('os.link', side_effect=OSError('injected publication failure')):
            with self.assertRaises(OSError):
                intake_gate.dump_exclusive(target, {'fictional': True})
        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.iterdir()), [])

    def test_receipt_leaf_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'receipt.json'
            external.write_text('unchanged')
            target = Path(self.tmp.name) / 'receipt.json'
            target.symlink_to(external)
            with self.assertRaises(ValueError):
                intake_gate.dump_exclusive(target, {'fictional': True})
            self.assertEqual(external.read_text(), 'unchanged')

    def test_writer_rejects_ancestor_swap_after_precheck(self):
        target = Path(self.tmp.name) / 'attestations/northstar/receipt.json'
        original_guard = intake.guard_path_ancestry
        with tempfile.TemporaryDirectory() as outside:
            def swap(base, destination):
                original_guard(base, destination)
                (base / 'attestations').symlink_to(outside, target_is_directory=True)
            with patch.object(intake, 'guard_path_ancestry', side_effect=swap):
                with self.assertRaises(ValueError):
                    intake_gate.dump_exclusive(target, {'fictional': True})
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_review_cli_uses_secure_receipt_writer(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('scopeledger_test_review', fixtures.ROOT / 'scripts/intake_review.py')
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.assertIs(cli.dump_exclusive, intake_gate.dump_exclusive)
        with tempfile.TemporaryDirectory() as outside:
            (Path(self.tmp.name) / 'extractions').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                cli.dump_exclusive(Path(self.tmp.name) / 'extractions/northstar/doc.review.json', {'fictional': True})
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_new_version_has_separate_report_and_receipt_identity(self):
        self.inbox.rmdir()
        audit = json.loads(tools.scopeledger_audit({'project': 'northstar'}))['audit']
        self.assertEqual(audit['engine_version'], '0.3.7')
        draft = json.loads(tools.scopeledger_draft({'project': 'northstar'}))
        self.assertTrue(draft['ok'], draft)
        self.assertIn('_v0_3_7_', draft['draft_path'])
        self.assertIn('_v0_3_7_', draft['html_preview_path'])
