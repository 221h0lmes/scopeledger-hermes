# ScopeLedger

**An evidence-linked billing review plugin for Hermes Agent.**  
**v0.3.7 | Linux | 4 native tools | Local-first | MIT License**

Service teams can finish work, receive approval for extra requests, and still miss an invoice line. They can also invoice work that was never approved or delivered. ScopeLedger compares the scope, delivery, approval, and invoice records you provide, then prepares a review packet showing what needs attention before billing closes.

**ScopeLedger recommends review, not collection.** It does not issue invoices, collect payment, message clients, or establish legal entitlement to payment.

## What ScopeLedger does

- **Finds potentially uninvoiced approved work.** Matches delivered extra units against approvals and invoiced quantities.
- **Separates pending work.** Work without a supported approval is shown separately from owner-review candidates.
- **Highlights billing exceptions.** Detects inconsistent quantities, source identities, missing evidence, and contradictory records.
- **Links evidence.** Uses original source references, captured-file hashes, and reproducible deterministic calculations in integer currency minor units.
- **Reviews local documents.** Inspects text-based PDF and DOCX evidence, surfaces extraction warnings, and requires human verification and mapping before document-backed financial findings are released.
- **Creates local reports.** Generates Markdown and standalone HTML owner-review packets, plus local audit receipts.

### A sample project

The included **Northstar Studio** project is fictional and demonstrates three distinct outcomes:

| Evidence finding | Example result | Next action |
|---|---:|---|
| D002: Approved extra landing page not fully invoiced | **USD 300.00** | Owner checks the authoritative invoice ledger |
| D004: Extra revision round without approval | **USD 150.00** | Seek a valid approval before billing |
| D005: Banner invoice quantity exceeds measured/approved work | **Billing exception** | Reconcile source and invoice quantities |

These amounts are sample data, not recovered revenue or a claim that payment is owed.

[View the fictional HTML report preview](docs/ScopeLedger_Synthetic_Preview.html)

## Native Hermes tools

| Tool | Function |
|---|---|
| `scopeledger_projects` | List locally available projects and the fictional `demo` project |
| `scopeledger_document` | Inspect a staged PDF or DOCX, record extraction diagnostics and source provenance |
| `scopeledger_audit` | Check scope, delivery, approvals, invoices, and source consistency |
| `scopeledger_draft` | Create local Markdown and HTML owner-review reports |

All financial reconciliation is performed by deterministic Python code. Hermes can use its configured model provider to interpret the tool results conversationally; the plugin does not delegate the arithmetic to a language model.

## Install

**Requirements:** Hermes Agent with plugin support (manifest requires `>=0.23.1`), Linux, and Python 3.11+. For PDF extraction, install Poppler utilities (`pdfinfo` and `pdftotext`). `python-docx` and PyMuPDF are optional secondary parsers.

Install from the public GitHub repository:

```bash
hermes plugins install 221h0lmes/scopeledger-hermes --enable
```

Start a fresh Hermes session after enabling the plugin:

```bash
hermes
```

Then try:

> Use ScopeLedger to audit the fictional `demo` project. Show approved but uninvoiced work, work awaiting approval, and invoice exceptions. Create an owner-review draft. Do not send invoices or contact clients.

For local development and validation:

```bash
git clone https://github.com/221h0lmes/scopeledger-hermes.git
cd scopeledger-hermes
python3 -m unittest discover -s tests -q
python3 stress_suite/run_tests.py -q
python3 scripts/demo.py
hermes plugins doctor "$PWD" --ci
hermes plugins validate "$PWD" --install-deps
```

## Working with your own project

1. **Prepare local records.** Create a project folder with `project.json`, `deliveries.csv`, `approvals.csv`, `invoices.csv`, and relevant `sources/*.txt` excerpts. See the [intake and verification guide](docs/INTAKE_AND_PERMISSIONS.md).
2. **Add originals when needed.** Place selected PDF/DOCX documents in the ScopeLedger inbox and inspect extraction warnings. Original documents require a separately completed, hash-bound human review and source-to-record mapping certification.
3. **Request an audit.** Hermes calls `scopeledger_audit`. Missing, inconsistent, or unsupported supplied financial evidence blocks affected readiness claims.
4. **Generate an owner-review packet.** `scopeledger_draft` writes local HTML and Markdown reports. An authorized human verifies current billing records and decides what to do next.

Data is kept in the Hermes profile's ScopeLedger plugin-data directory, typically `~/.hermes/plugin-data/scopeledger/`. The plugin does not alter the original documents or automatically send the reports.

## Privacy and permissions

| Surface | Behavior |
|---|---|
| Local files | Reads selected project records and originals staged within its configured plugin-data directory |
| Local outputs | Writes extracted text, provenance manifests, review attestations, SQLite audit receipts, and HTML/Markdown reports |
| Local commands | Can invoke installed Poppler utilities for PDF text extraction |
| Network | No network requests or telemetry initiated by the ScopeLedger plugin |
| Model provider | Tool results may be included in Hermes messages sent to the model provider selected by the user |
| Authentication | No Google account, OAuth token, or external billing-system credentials required |
| Automation | Does not create background schedules or send financial communications; Hermes scheduling can be configured separately by the user |
| Retention | Data remains on the user's machine until the user removes it |

**Financial verification boundaries:** ScopeLedger supports a defined set of structured fields and English evidence statements. It does not authenticate signers, prove that a billing ledger contains every invoice, determine contractual enforceability, calculate tax/credit accounting, or guarantee OCR of scanned documents. Unsupported or contradictory evidence is held for human review. It is not a substitute for an accounting system or professional financial/legal review.

## Verification

Release v0.3.7 passed **161 core/document tests and 35 agency stress tests (196 total)**. Hermes Doctor and Validator passed for the staged and installed plugin, and a live Hermes session successfully exercised the fictional audit and report workflow on Linux with version `0.3.7` and no tool errors. The test fixtures include alternative approval wording, source discrepancies, document provenance and output-path protection.

## Documentation

- [Original-document intake and permissions](docs/INTAKE_AND_PERMISSIONS.md)
- [Scheduling](docs/SCHEDULING.md)
- [Demo walkthrough](docs/DEMO_90_SECONDS.md)
- [Synthetic report preview](docs/ScopeLedger_Synthetic_Preview.html)

**License:** [MIT](LICENSE). ScopeLedger is an independent community plugin and is not affiliated with Nous Research.
