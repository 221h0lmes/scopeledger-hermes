# ScopeLedger 0.3.6 approval/source-context repairs

The reported v0.3.5 failures were reproduced independently with fictional projects in temporary storage. The original 131 core/document tests and 35 stress tests passed before modification; their green results did not cover these remaining context exemptions.

## Observed reproductions and repaired outcomes

| Reproduction | v0.3.5 observation | Repaired observation |
|---|---|---|
| `D002 \| I do not` followed by a newline and `approve any additional landing pages.` in an unlinked supplement | Both native tools and both reports retained USD 300; original certification passed. | Full-text denial matching identifies the unaccounted denial. Structured audit/draft and both reports show zero ready; certification and original-workflow tools block. |
| The same wrapped denial before the approval records and in the approvals DOCX | Certification passed and both tools retained USD 300. | Unknown document context is not classified as a heading. Certification refuses, and structured readiness is also zero. |
| `The following approvals apply only after a separate purchase order is signed.` before approval records and in the original | Certification passed and both tools retained USD 300. | Unsupported approval-source context withholds readiness. Certification and original-workflow tools block. Moving the text after the title or records cannot restore readiness. |
| `Invoice INV-EXTRA: one additional landing page, USD three hundred, paid.` before invoice records and in the original, without a CSV row | Certification passed, `ledger_complete=true`, USD 300 ready. | Unsupported invoice-source context sets `ledger_complete=false` and withholds readiness. Certification and original-workflow tools block. The amount is not interpreted or automatically mapped. |
| The same conditional approval or paid invoice after records | Original certification blocked, but structured audit/draft retained USD 300. | Both structured reports show zero ready and original certification remains blocked. The behavior no longer depends on position. |

The unwrapped denial control also withholds readiness and now refuses certification when the denial remains unaccounted. A properly sourced, mapped rejection remains accounted for and certifiable; the existing invoice against rejected work remains a billing exception.

## Root corrections

`auditor.py` matches `APPROVAL_DENIAL` over complete captured source text and then assigns source locations. A physical line cannot truncate a negative authorization phrase. Only a verified, identity-bound rejection on the entire matching source line can account for it. Financial-role source context is checked against mapped records and explicitly supported nonfinancial metadata. Linked approval/invoice files and supplements containing approval/invoice language use this check. Unsupported approval context withholds project readiness alongside unsupported invoice context.

`evidence_semantics.py` defines bounded complete headings and administrative notes. Neither lack of digits, equality to operator-created source text, nor placement before the first record proves that a line is metadata. Administrative sentences supported by existing valid fixtures remain accepted; extra qualifiers or arbitrary sentences do not inherit that acceptance.

`intake_gate.py` uses this same metadata predicate, removes the inferred preamble exemption, scans document reversals across complete text, and refuses certification when `source_context_complete=false`. A valid hash-bound human receipt cannot waive contradictory or unsupported supplied context.

`source_context_complete` describes these bounded checks; it does not authenticate rights, infer arbitrary language, or prove completeness of an unseen external ledger. Unknown prose inside a financial-role source remains blocked conservatively. No paid-invoice, credit, tax or discount accounting has been added.

## Executable validation

```bash
python3 -m unittest discover -s tests -p test_approval_context.py -q
python3 -m unittest discover -s tests -p test_context_integrity.py -q
python3 -m unittest discover -s tests -p test_financial_integrity.py -q
python3 -m unittest discover -s tests -p test_release_repairs.py -q
python3 -m unittest discover -s tests -q
python3 stress_suite/run_tests.py -q
python3 scripts/demo.py
```

The new suite has **15 tests and 75 parameterized subcases** covering both workflows, Markdown/HTML output, wrapped/unwrapped denials, linked and unlinked supplements, preamble/footer positions, text immediately after a real title, unknown context without narrow financial keywords, valid rejection mapping and supported administrative prose.

Final totals: **146 core/document + 35 stress = 181 passing tests**, zero failures, errors or skips. All previous 166 tests remain passing. Northstar retains USD 300 ready, USD 150 pending approval, D005's exception and successful drafting. Prior captured-byte extraction and report-directory race protections remain passing. The engine, manifest and report filenames identify v0.3.6.

No installed plugin, credentials, client data, gateway, external service or publication was changed. Fresh v0.3.6 Hermes execution remains unverified. Doctor/Validator remain unverified in this workspace because the known launcher restriction requires writes under `~/.hermes`; earlier versions' operator logs do not qualify this changed source. Optional secondary parsers and the CI Python-version matrix remain separate unverified runtime checks. The empty `.git` directory prevents verification of eventual tracked/publication contents.
