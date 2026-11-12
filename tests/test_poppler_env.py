"""Poppler child processes receive no provider credentials from Hermes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if 'scopeledger' not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        'scopeledger', ROOT / '__init__.py',
        submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
from scopeledger import document_intake


class PopplerEnvironmentTests(unittest.TestCase):
    def test_pdfinfo_and_pdftotext_do_not_inherit_provider_keys(self):
        captured = []
        def fake_run(args, **kwargs):
            captured.append((args, kwargs))
            out = (b'Pages: 1\n' if args[0] == 'pdfinfo'
                   else b'Delivered one approved sample document for verification.\n')
            return subprocess.CompletedProcess(args, 0, stdout=out)
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'synthetic-private-credential',
            'ANTHROPIC_API_KEY': 'synthetic-private-credential',
            'SCOPELEDGER_TEST_SECRET': 'synthetic-private-credential',
        }), patch.object(document_intake.subprocess, 'run', side_effect=fake_run):
            pages, issues = document_intake._pdf_snapshot(
                b'%PDF-1.4\nsynthetic content', Path('/nonexistent/test-snapshot.pdf'))
        self.assertEqual(1, len(pages))
        self.assertEqual(['pdfinfo', 'pdftotext'], [args[0] for args, _ in captured])
        self.assertEqual(2, len(captured))
        for args, kwargs in captured:
            child_env = kwargs['env']
            self.assertEqual('C.UTF-8', child_env['LANG'])
            self.assertTrue(set(child_env).issubset({'PATH', 'HOME', 'TMPDIR', 'LANG'}))
            for secret_name in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'SCOPELEDGER_TEST_SECRET'):
                self.assertNotIn(secret_name, child_env)
            self.assertTrue(kwargs.get('check'))
