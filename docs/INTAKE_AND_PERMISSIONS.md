# Original-document intake and evidence verification

ScopeLedger can examine local text-based PDF and DOCX files alongside structured project records. It supports a human-reviewed evidence workflow: extraction, inspection, record mapping, certification, audit, and owner-review report.

## Project files

Prepare the following inside the ScopeLedger project-data directory, normally `~/.hermes/plugin-data/scopeledger/projects/<project>/`:

```text
project.json
approvals.csv
deliveries.csv
invoices.csv
sources/
  agreement.txt
  client_messages.txt
  work_log.txt
  invoices.txt
```

The project's agreement, deliveries, approvals and invoices should agree with the source excerpts and structured data. Refer to the bundled `examples/northstar` and `stress_suite/projects` for fictional examples of the supported formats.

## Inspect originals

1. Copy explicitly selected originals into `~/.hermes/plugin-data/scopeledger/inbox/<project>/`. Use only files you are authorized to process.
2. In Hermes, call `scopeledger_document` for each file and its correct role: `agreement`, `deliveries`, `approvals`, or `invoices`.
3. Compare the extracted text with **every page and relevant table** of the original document. Review quantities, rates, invoice references, credits, taxes, conditions, cancellations, and extraction warnings.
4. Align each meaningful financial source statement with exactly the intended structured record. Unmatched, contradictory or unsupported evidence prevents a document-backed financial claim from being certified.

PDF intake relies on installed Poppler utilities. Scanned documents, image-only pages, embedded objects or complex document layouts can require additional manual processing. The tool does not treat missing extracted text as proof that a document contains no relevant information.

## Complete review and mapping certification

From a local checkout of this repository, the following is an example **for the bundled fictional `northstar` project only**, after staging its sample originals and checking the generated extracts:

```bash
bash scripts/stage_synthetic_documents.sh

python3 scripts/intake_review.py verify-document northstar northstar_agreement.docx agreement --checked-original
python3 scripts/intake_review.py verify-document northstar northstar_approvals.docx approvals --checked-original
python3 scripts/intake_review.py verify-document northstar northstar_deliveries.pdf deliveries --checked-original
python3 scripts/intake_review.py verify-document northstar northstar_invoices.pdf invoices --checked-original

python3 scripts/intake_review.py certify-mapping northstar --checked-mapping
python3 scripts/intake_review.py gate northstar
```

These commands record explicit human attestations. Run them only after the corresponding checks are actually complete. When extraction warnings exist, resolve them or document the review decision before acknowledging them. A certification receipt cannot validate a contradiction in the underlying source evidence.

For a real project, select the correct project slug and filenames. Never issue an invoice solely because the tool reports a possible uninvoiced amount.

## Data and consent

- ScopeLedger reads only the selected, locally staged project files and bundled examples. It does not access Google Drive or request OAuth scopes.
- Extraction artifacts, source hashes, review receipts, audit receipts, and Markdown/HTML reports remain in the configured local Hermes plugin-data directory until removed by the user.
- The plugin itself does not make network requests. Hermes may include tool outputs in messages sent to the configured model provider. Obtain appropriate authorization before processing confidential client data.
- A hash identifies local captured content; it does not authenticate a signer, establish contractual validity, or prove that external billing records are complete.
- Supported analysis focuses on fixed-unit scope, approved quantities and invoiced quantities. Tax, credits, payments, legal enforceability, and full accounting reconciliation must be verified outside the plugin.

## Decision boundaries

`READY_FOR_OWNER_REVIEW` means that the supplied structured records and supported evidence checks identify a candidate for owner review. It does **not** mean the amount is collectible or that a client has approved payment. `NEEDS_APPROVAL` is a separate pending item. Evidence exceptions or incomplete mappings are prompts for investigation, not instructions to invoice.

Final billing actions require an authorized person to consult the complete, current agreement, approval history, and billing system.
