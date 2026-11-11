import csv
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# Load the native plugin exactly as a package with relative imports.
if "scopeledger" not in sys.modules:
    spec = importlib.util.spec_from_file_location("scopeledger", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = plugin
    spec.loader.exec_module(plugin)
from scopeledger import auditor, schemas, storage, tools


class FakeContext:
    def __init__(self):
        self.registered = {}
    def register_skill(self, name, path):
        self.skill = (name, path)
    def register_tool(self, *, name, toolset, schema, handler):
        if name in self.registered:
            raise AssertionError("Duplicate tool")
        self.registered[name] = (toolset, schema, handler)


class ScopeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="scopeledger_tests_")
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"SCOPELEDGER_DATA_HOME": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.proj = Path(self.temp.name) / "projects" / "northstar"
        shutil.copytree(ROOT / "examples" / "northstar", self.proj)

    def audit(self, slug="northstar"):
        return json.loads(tools.scopeledger_audit({"project": slug}))

    def test_registration_and_manifest_names(self):
        context = FakeContext()
        sys.modules["scopeledger"].register(context)
        self.assertEqual(set(context.registered), {"scopeledger_projects", "scopeledger_audit", "scopeledger_draft", "scopeledger_document"})
        self.assertTrue(all(name == schema["name"] for name, (_, schema, _) in context.registered.items()))
        manifest = (ROOT / "plugin.yaml").read_text()
        self.assertTrue(all(f"- {name}" in manifest for name in context.registered))
        self.assertEqual(context.skill[0], "scopeledger")

    def test_in_scope_extra_invoice_is_flagged(self):
        p = self.proj / "invoices.csv"
        p.write_text(p.read_text() + "I099,D001,1,invoices.txt,Invoice INV-203 billed one additional landing page at USD 300.\n")
        item = next(x for x in self.audit()["audit"]["findings"] if x["delivery_id"] == "D001")
        self.assertEqual(item["status"], "IN_SCOPE_INVOICE_EXCEPTION")

    def test_html_is_standalone_escaped_and_no_scripts(self):
        a = self.audit()["audit"]
        a["client"] = '<script>alert(1)</script>'
        from scopeledger.report_view import render
        page = render(a)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>', page)
        self.assertIn('<html lang="en">', page)

    def test_demo_amount_and_three_exceptions(self):
        outcome = self.audit()
        self.assertTrue(outcome["ok"])
        a = outcome["audit"]
        self.assertEqual(a["totals"]["ready_minor"], 30000)
        self.assertEqual(a["totals"]["possible_minor"], 15000)
        self.assertEqual(a["totals"]["already_invoiced_minor"], 30000)
        by_id = {f["delivery_id"]: f for f in a["findings"]}
        self.assertEqual(by_id["D002"]["status"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(by_id["D004"]["status"], "NEEDS_APPROVAL")
        self.assertEqual(by_id["D005"]["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertTrue(any("exceed" in i for i in by_id["D005"]["issues"]))

    def test_catalog_listing_and_demo(self):
        result = json.loads(tools.scopeledger_projects({}))
        self.assertTrue(result["ok"])
        self.assertIn("demo", [p["project"] for p in result["projects"]])
        self.assertIn("northstar", [p["project"] for p in result["projects"]])
        self.assertTrue(self.audit("demo")["ok"])

    def test_source_refs_have_line_and_sha(self):
        audit = self.audit()["audit"]
        ref = audit["findings"][0]["evidence"]["delivery"]
        self.assertTrue(ref["matched"])
        self.assertGreater(ref["line"], 0)
        self.assertEqual(len(ref["sha256"]), 64)

    def test_receipt_persists_but_is_idempotent(self):
        self.audit(); self.audit()
        from contextlib import closing
        with closing(sqlite3.connect(Path(self.temp.name) / "audit_receipts.sqlite3")) as conn:
            self.assertEqual(conn.execute("select count(*) from audit_receipts").fetchone()[0], 1)
            self.assertEqual(conn.execute("select count(*) from audit_receipts_v2").fetchone()[0], 1)

    def test_draft_writes_once_and_does_not_send(self):
        first = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        second = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        self.assertTrue(first["ok"])
        self.assertEqual(first["draft_path"], second["draft_path"])
        content = Path(first["draft_path"]).read_text()
        self.assertIn("Draft only", content)
        self.assertIn("No invoice has been sent", content)
        self.assertIn("USD 300.00", content)
        self.assertEqual(list((Path(self.temp.name) / "reports").glob("*.md")).__len__(), 1)

    def test_modified_draft_not_overwritten(self):
        first = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        Path(first["draft_path"]).write_text("User edited draft")
        attempt = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        self.assertFalse(attempt["ok"])
        self.assertEqual(Path(first["draft_path"]).read_text(), "User edited draft")

    def test_approval_quote_mismatch_never_ready(self):
        p = self.proj / "approvals.csv"
        p.write_text(p.read_text().replace("I approve the two additional landing pages at USD 300 each.", "I approve NOTHING that was requested."))
        result = self.audit()["audit"]
        item = next(x for x in result["findings"] if x["delivery_id"] == "D002")
        self.assertNotEqual(item["status"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(result["totals"]["ready_minor"], 0)

    def test_agreement_not_verified_fails_closed(self):
        p = self.proj / "project.json"
        config = json.loads(p.read_text())
        config["agreement_source"]["quote"] = "No signed scope exists in the proof files."
        p.write_text(json.dumps(config))
        result = self.audit()["audit"]
        self.assertEqual(result["totals"]["ready_minor"], 0)
        self.assertTrue(result["errors"])

    def test_invoice_unmatched_blocks_ready(self):
        p = self.proj / "invoices.csv"
        p.write_text(p.read_text().replace("Invoice INV-203 billed one additional landing page at USD 300.", "invoice unknown and not proven"))
        outcome = self.audit()["audit"]
        item = next(x for x in outcome["findings"] if x["delivery_id"] == "D002")
        self.assertEqual(item["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertEqual(outcome["totals"]["ready_minor"], 0)

    def test_unsupported_currency_rejected(self):
        p = self.proj / "project.json"
        v = json.loads(p.read_text())
        v["currency"] = "JPY"  # zero-decimal currency; this MVP assumes cents
        p.write_text(json.dumps(v))
        self.assertFalse(self.audit()["ok"])

    def test_invalid_slug_and_traversal(self):
        for slug in ("../../.ssh", "with space", "", "/root", "A"):
            self.assertFalse(self.audit(slug)["ok"])

    def test_source_symlink_refused(self):
        secret = Path(self.temp.name) / "secrets.txt"
        secret.write_text("sensitive")
        p = self.proj / "sources" / "client_messages.txt"
        p.unlink()
        p.symlink_to(secret)
        self.assertFalse(self.audit()["ok"])

    def test_project_symlink_refused(self):
        link = Path(self.temp.name) / "projects" / "evil"
        link.symlink_to(self.proj, target_is_directory=True)
        self.assertFalse(self.audit("evil")["ok"])

    def test_duplicate_delivery_refused(self):
        p = self.proj / "deliveries.csv"
        rows = p.read_text().splitlines()
        p.write_text("\n".join(rows + [rows[1]]) + "\n")
        self.assertFalse(self.audit()["ok"])

    def test_duplicate_invoice_refused(self):
        p = self.proj / "invoices.csv"
        rows = p.read_text().splitlines()
        p.write_text("\n".join(rows + [rows[1]]) + "\n")
        self.assertFalse(self.audit()["ok"])

    def test_duplicate_agreement_service_refused(self):
        p = self.proj / "project.json"
        v = json.loads(p.read_text())
        v["services"].append(v["services"][0])
        p.write_text(json.dumps(v))
        self.assertFalse(self.audit()["ok"])

    def test_negative_quantity_and_rate_refused(self):
        p = self.proj / "project.json"
        v = json.loads(p.read_text())
        v["services"][0]["extra_unit_price_minor"] = -1
        p.write_text(json.dumps(v))
        self.assertFalse(self.audit()["ok"])
        p2 = self.proj / "deliveries.csv"
        p2.write_text(p2.read_text().replace("D002,landing_page,2,", "D002,landing_page,-2,"))
        v["services"][0]["extra_unit_price_minor"] = 30000
        p.write_text(json.dumps(v))
        self.assertFalse(self.audit()["ok"])

    def test_csv_with_unexpected_column_refused(self):
        p = self.proj / "deliveries.csv"
        p.write_text(p.read_text().replace("delivery_id,service_code", "delivery_id,UNTRUSTED,service_code"))
        self.assertFalse(self.audit()["ok"])

    def test_oversize_source_fails_closed(self):
        p = self.proj / "sources" / "client_messages.txt"
        p.write_text("X" * (129 * 1024))
        result = self.audit()
        self.assertFalse(result["ok"])  # fail closed on oversized evidence

    def test_missing_project_returns_error(self):
        self.assertFalse(self.audit("notthere")["ok"])

    def test_input_change_changes_digest(self):
        before = self.audit()["audit"]["digest"]
        p = self.proj / "sources" / "work_log.txt"
        p.write_text(p.read_text() + "Additional comment.\n")
        after = self.audit()["audit"]["digest"]
        self.assertNotEqual(before, after)

    def test_consistent_result_independent_of_row_order(self):
        first = self.audit()["audit"]
        p = self.proj / "deliveries.csv"
        lines = p.read_text().splitlines()
        p.write_text(lines[0] + "\n" + "\n".join(reversed(lines[1:])) + "\n")
        second = self.audit()["audit"]
        self.assertEqual(first["totals"], second["totals"])
        self.assertEqual(first["findings"], second["findings"])

    def test_conflicting_decision_fails_closed(self):
        p = self.proj / "approvals.csv"
        with p.open("a") as f:
            f.write("A004,D002,REJECTED,0,client_messages.txt,Please send pricing for the extra revision round first.\n")
        item = next(x for x in self.audit()["audit"]["findings"] if x["delivery_id"] == "D002")
        self.assertNotEqual(item["status"], "READY_FOR_OWNER_REVIEW")

    def test_no_unverified_invoiced_counted_as_billable(self):
        p = self.proj / "invoices.csv"
        p.write_text(p.read_text().replace("I001,D002,1", "I001,D002,9"))
        result = self.audit()["audit"]
        item = next(x for x in result["findings"] if x["delivery_id"] == "D002")
        self.assertEqual(item["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertEqual(result["totals"]["ready_minor"], 0)


    def test_false_approval_status_does_not_generate_ready_money(self):
        p = self.proj / "approvals.csv"
        p.write_text(p.read_text().replace("A002,D004,PENDING,0,", "A002,D004,APPROVED,1,"))
        a = self.audit()["audit"]
        item = next(f for f in a["findings"] if f["delivery_id"] == "D004")
        self.assertEqual(item["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertEqual(item["review_ready_minor"], 0)
        self.assertFalse(item["evidence"]["approvals"][0]["proof"]["semantic_verified"])
        self.assertEqual(a["totals"]["ready_minor"], 30000)

    def test_rate_inflation_conflicts_with_sourced_contract(self):
        p = self.proj / "project.json"
        obj = json.loads(p.read_text())
        obj["services"][0]["extra_unit_price_minor"] = 3_000_000
        p.write_text(json.dumps(obj))
        a = self.audit()["audit"]
        d = next(f for f in a["findings"] if f["delivery_id"] == "D002")
        self.assertEqual(d["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertEqual(d["review_ready_minor"], 0)
        self.assertEqual(a["totals"]["ready_minor"], 0)
        self.assertFalse(d["evidence"]["agreement_terms"]["semantic_verified"])

    def test_included_quantity_tampering_blocks_ready(self):
        p = self.proj / "project.json"
        obj = json.loads(p.read_text())
        obj["services"][0]["included_units"] = 4
        p.write_text(json.dumps(obj))
        a = self.audit()["audit"]
        self.assertEqual(a["totals"]["ready_minor"], 0)

    def test_wrong_service_approval_quote_blocks_ready(self):
        p = self.proj / "approvals.csv"
        p.write_text(p.read_text().replace(
            "A002,D004,PENDING,0,client_messages.txt,Please send pricing for the extra revision round first.",
            "A002,D004,APPROVED,1,client_messages.txt,I approve the two additional landing pages at USD 300 each."))
        a = self.audit()["audit"]
        d = next(f for f in a["findings"] if f["delivery_id"] == "D004")
        self.assertEqual(d["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertEqual(d["review_ready_minor"], 0)

    def test_invoice_orphan_suppresses_global_ready(self):
        p = self.proj / "invoices.csv"
        p.write_text(p.read_text() +
                     "I999,UNKNOWN,1,invoices.txt,Invoice INV-203 billed one additional landing page at USD 300.\n")
        a = self.audit()["audit"]
        self.assertFalse(a["ledger_complete"])
        self.assertEqual(a["totals"]["ready_minor"], 0)
        self.assertEqual(next(f for f in a["findings"] if f["delivery_id"] == "D002")["status"],
                         "PROVISIONAL_INCOMPLETE_LEDGER")

    def test_unknown_approval_suppresses_global_ready(self):
        p = self.proj / "approvals.csv"
        p.write_text(p.read_text() +
                     "A999,UNKNOWN,1,0,client_messages.txt,I approve one extra banner at USD 90.\n")
        a = self.audit()["audit"]
        self.assertFalse(a["ledger_complete"])
        self.assertEqual(a["totals"]["ready_minor"], 0)

    def test_invoice_quantity_contradicts_quoted_text(self):
        p = self.proj / "invoices.csv"
        p.write_text(p.read_text().replace("I001,D002,1,", "I001,D002,2,"))
        a = self.audit()["audit"]
        self.assertEqual(a["totals"]["ready_minor"], 0)
        self.assertEqual(next(f for f in a["findings"] if f["delivery_id"] == "D002")["status"],
                         "EVIDENCE_OR_BILLING_EXCEPTION")

    def test_delivery_quantity_contradicts_quoted_text(self):
        p = self.proj / "deliveries.csv"
        p.write_text(p.read_text().replace("D002,landing_page,2,", "D002,landing_page,20,"))
        a = self.audit()["audit"]
        self.assertEqual(a["totals"]["ready_minor"], 0)
        self.assertNotEqual(next(f for f in a["findings"] if f["delivery_id"] == "D002")["status"],
                            "READY_FOR_OWNER_REVIEW")

    def test_unrecognized_approval_wording_is_not_verification(self):
        p = self.proj / "approvals.csv"
        p.write_text(p.read_text().replace("I approve the two additional landing pages at USD 300 each.",
                                           "Fine proceed with the proposed work."))
        source = self.proj / "sources" / "client_messages.txt"
        source.write_text(source.read_text() + "\nFine proceed with the proposed work.\n")
        a = self.audit()["audit"]
        self.assertEqual(a["totals"]["ready_minor"], 0)

    def test_duplicate_conflicting_contract_terms_fail_closed(self):
        p = self.proj / "sources" / "agreement.txt"
        p.write_text(p.read_text() + "\nAdditional landing pages: USD 1000 each.\n")
        a = self.audit()["audit"]
        self.assertEqual(a["totals"]["ready_minor"], 0)

    def test_markdown_escapes_remote_image_in_client_name(self):
        p = self.proj / "project.json"
        obj = json.loads(p.read_text())
        obj["client"] = "Northstar ![pixel](https://example.invalid/track)"
        p.write_text(json.dumps(obj))
        output = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        self.assertTrue(output["ok"], output)
        md = Path(output["draft_path"]).read_text()
        self.assertNotIn("![pixel](https://", md)
        self.assertIn(r"\!\[pixel\]\(https://", md)

    def test_concurrent_duplicate_drafts_are_complete_and_identical(self):
        from concurrent.futures import ThreadPoolExecutor
        def draft(_):
            return json.loads(tools.scopeledger_draft({"project": "northstar"}))
        with ThreadPoolExecutor(max_workers=16) as pool:
            outputs = list(pool.map(draft, range(64)))
        self.assertTrue(all(o["ok"] for o in outputs), outputs)
        self.assertEqual(len({o["html_preview_path"] for o in outputs}), 1)
        self.assertEqual(len({o["draft_path"] for o in outputs}), 1)
        self.assertEqual(len(list((Path(self.temp.name) / "reports").glob("*.md"))), 1)
        self.assertEqual(len(list((Path(self.temp.name) / "reports").glob("*.html"))), 1)
        html = Path(outputs[0]["html_preview_path"]).read_text()
        self.assertIn('</html>', html)
        self.assertIn('USD 300.00', html)

    def test_privacy_disclosure_matches_model_provider_behavior(self):
        README = (ROOT / "README.md").read_text()
        self.assertIn("model provider", README)
        self.assertIn("no network calls", README.lower())
        page = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        html = Path(page["html_preview_path"]).read_text()
        self.assertIn("model provider", html)

    def test_new_report_version_does_not_overwrite_old_report(self):
        folder = Path(self.temp.name) / "reports"
        folder.mkdir()
        old = folder / "northstar_396c2d7cf39de0a8_owner-review.md"
        old.write_text("Old v0.1 report must remain unchanged")
        result = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        self.assertTrue(result["ok"], result)
        self.assertIn("v0_3", result["draft_path"])
        self.assertEqual(old.read_text(), "Old v0.1 report must remain unchanged")

    def test_same_source_approval_reused_for_multiple_rows_fails_closed(self):
        p = self.proj / "approvals.csv"
        p.write_text(p.read_text() +
                     "A777,D002,APPROVED,2,client_messages.txt,I approve the two additional landing pages at USD 300 each.\n")
        a = self.audit()["audit"]
        d = next(f for f in a["findings"] if f["delivery_id"] == "D002")
        self.assertEqual(d["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertEqual(d["review_ready_minor"], 0)

    def test_unverified_prior_delivery_blocks_later_extra_classification(self):
        p = self.proj / "deliveries.csv"
        p.write_text(p.read_text().replace("D001,landing_page,5,", "D001,landing_page,4,"))
        a = self.audit()["audit"]
        d = next(f for f in a["findings"] if f["delivery_id"] == "D002")
        self.assertEqual(d["status"], "EVIDENCE_OR_BILLING_EXCEPTION")
        self.assertEqual(a["totals"]["ready_minor"], 0)

    def test_report_directory_symlink_rejected(self):
        reports = Path(self.temp.name) / "reports"
        other = Path(self.temp.name) / "hidden"
        other.mkdir()
        reports.symlink_to(other, target_is_directory=True)
        result = json.loads(tools.scopeledger_draft({"project": "northstar"}))
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
