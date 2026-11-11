# Original-document intake, financial verification and privacy

**This plugin does not provide a live Google Drive connector.** It never prompts for Google OAuth or reads a user's Drive. For testing, explicitly download individual **fictional** Drive documents from a spare account, then stage them locally. Do not stage sensitive customer documents without permission for Hermes model processing.

## Source acquisition and permissions

- Local mode: the user explicitly chooses/copies originals into their own ScopeLedger inbox.
- Planned Drive connector (not shipped): obtain explicit account and file selection. `drive.file` with a Picker can grant file edit capability, so code must enforce a strict read-only allowlist. `drive.readonly` may grant broad access across all accessible Drive files; do not claim it is folder-limited. A selected folder is not automatic authorization for every descendant file.
- Do not reuse Hermes Google Workspace login or broad scopes without inspecting/authorizing them. This project requests no OAuth scopes and stores no cloud tokens.

## Step-by-step local intake

Replace example names with **actual selected** document names. Filenames use the regex given in `document_intake.py`. A project slug must be configured with matching structured records first.

```bash
PROJECT=northstar
INBOX="$HOME/.hermes/plugin-data/scopeledger/inbox/$PROJECT"
install -d -m 700 "$INBOX"
# For a new project, copy your own approved local originals to this folder.
# Do not run the next commands on real data until you have inspected all originals.
```

From a fresh Hermes session: "Use ScopeLedger `scopeledger_document` to inspect <file> for <project> as agreement/deliveries/approvals/invoices. Report extraction warnings and do not certify." If the doc was not staged the tool refuses it. For a synthetic staging run, use `bash scripts/stage_synthetic_documents.sh` first, then inspect all four `northstar_*` files.

The plugin records original SHA-256, source role, PDF text per actual page (DOCX body sections aren't physical page counts), numeric-token inventory, extractor identity (not installed parser versions), extraction-text SHA-256, and warnings. The optional second parser is not a guarantee of completeness, and scanned pages are not safe to interpret as zero.

### Human verification commands

Use only after visually comparing each original page and extracted text, and reviewing all material table rows, credits, totals, quantities and rates. **These are actual attestations, not test helpers; do not run mechanically.**

```bash
cd "$HOME/hackathons/scopeledger-submission"
python3 scripts/intake_review.py verify-document northstar northstar_agreement.docx agreement --checked-original
python3 scripts/intake_review.py verify-document northstar northstar_approvals.docx approvals --checked-original
python3 scripts/intake_review.py verify-document northstar northstar_deliveries.pdf deliveries --checked-original
python3 scripts/intake_review.py verify-document northstar northstar_invoices.pdf invoices --checked-original
# Only after checking original → every structured row linkage:
python3 scripts/intake_review.py certify-mapping northstar --checked-mapping
python3 scripts/intake_review.py gate northstar
```

Missing secondary parsers, scanned content, changed files, unrecognized financial lines or unresolved mapping issues are blockers until genuinely reviewed. Use `--acknowledge-issues` only to record a documented human decision resolving the precise concerns; it does not magically fix the source. In a scheduled run, no human approval can be silently provided. The ledger engine and report always require their separate evidence checks.

## What a financial verifier must inspect

- Account for every PDF page and each DOCX table, supplementary part, embedded image, footnote, comment and tracked change. Unsupported regions must be flagged, not omitted.
- Verify invoice identifier, invoice date, service and delivery ID, each quantity, unit rate, extended line amount, currency, discounts, credits, taxes, totals and cancellations. Reconcile multiple invoice lines to the same work without double counting.
- Match agreement quotas/rates; delivery evidence; approval decisions and authority; recorded billed extra units. Unsupported wording remains unverified. An excerpt being present does not prove its signer or legal effect.
- Preserve complete original hashes and the extraction hash in manifests; compare every structured financial record to its original source. An orphan invoice, reused source anchor, contradictory approval or misassigned invoice blocks readiness.
- Before any real payment request, reconcile against the organization's complete current billing system and have an authorized human approve the action. **ScopeLedger never issues that action itself.**

## Retention and deletion

On the default local Hermes profile, all data lives under `~/.hermes/plugin-data/scopeledger/`. The plugin never exfiltrates documents itself, but Hermes can transmit relevant excerpts and tool output to its configured model provider. Local audits leave SQLite receipts; report generation leaves HTML/Markdown. Manual deletion or organization retention controls are required.

## Important v0.3.6 verification details

- The auditor scans the complete captured text of every supplied `sources/*` file before assigning source line locations for concrete `Invoice <id> billed ...` statements, including unlinked source files. Each statement needs a unique, identity-bound structured mapping agreeing on quantity, service, unit rate and currency. Word wrapping cannot hide a billed statement. Wrapped evidence without a supported unique CSV anchor, unsupported billed statements, duplicate evidence or inconsistent invoice identities withhold project readiness. The invoice-specific matcher does not label unrelated prose as a billed statement; a separate financial-role context check rejects unsupported text while accepting bounded administrative notes. `ledger_complete` describes supplied recognized invoice evidence and structured references; it cannot establish an unseen external ledger.
- Agreement parsing retains the entire body across physical lines. Only configured-service included quotas and unit-rate clauses, plus the exact supported written-approval requirement, are accepted. Unknown clauses or prose block readiness even when they occupy another sentence. Leading SOW title/date and title-case fictional-party metadata have narrow supported syntax; arbitrary metadata is not silently discarded. Quotas must use supported integer digits or quantity words. Negations, fractional quantities, contradictory clauses and unsupported surrounding qualifications fail semantic verification. Positive original-document review flags cannot override this result.
- Every nonempty delivery, approval and invoice document line must be a single identity-bound structured quote or explicitly supported heading/administrative note. Source membership, lack of digits and position before the first record never establish metadata status. Duplicate evidence occurrences, wrong delivery identities and quantity/service/rate mismatches block mapping. Invoice identifiers are preserved within the exact original quote; `invoice_line_id` remains the ledger's internal row identifier.
- Repeated claims for the same external invoice identity and service require richer invoice-line identity evidence and remain blocked, even if multiple CSV row IDs are supplied. Different services on one invoice can be separately mapped; this bounded schema does not provide general multi-line invoice reconciliation.
- All supplied agreement lines must also occur in the structured agreement source; positive quota/rate excerpts alone cannot cover an additional unsupported clause. Page markers are ignored only when they occupy a complete line. A page prefix followed by an invoice record remains content.
- Unmatched prose is a blocker even without numbers or known financial words. Recognized credits, refunds, discounts, taxes and material reversals block readiness in all document roles and structured source context. These adjustments are **not reconciled or calculated**. Projects requiring them remain blocked here and need their authoritative accounting system. A correctly sourced, mapped rejection still affects its own delivery. Denials are matched in complete captured source text, including across line breaks. A match is accounted for only by a verified rejection bound to that complete source line; all other matches withhold candidates and block certification.
- Linked approval/invoice source files are checked for unrepresented context independently of line position. Supplements containing approval/invoice language are checked too. Unsupported wording is withheld, not interpreted automatically. `source_context_complete` reports absence of detected blockers in this supported context grammar; it is not a claim of general language understanding or external invoice completeness.
- Supported metadata includes the fictional correspondence/export titles, `Fictional agency <basename>.txt source notes`, the work-ledger title, and bounded administrative sentences about invoice questions at a meeting or a fictional export demonstration. Extra qualifiers do not inherit these exemptions. Other context requires review and remains blocked; a human checkbox cannot waive it.
- Positive human review fields remain mandatory. DOCX ZIP/XML and secondary parsers consume the captured source bytes; PDF pathname-based parsers use a private temporary snapshot, cleaned up after success or failure. All diagnostics and hashes describe that same snapshot.
- New manifests require `input_snapshot: captured-bytes-v1`. Older extraction manifests cannot prove this property and require regeneration and human review. Immutable existing files are never overwritten; see [migration details](SECURITY_HARDENING_0.3.3.md).
- Reports, markers, extracted text, manifests and both CLI receipt types share an atomic, no-overwrite writer that traverses output ancestors using directory descriptors and `O_NOFOLLOW`. The report lock and both reports use the same pinned directory descriptor; no pathname is reopened for file reads, temporary creation, publication or cleanup. Static symlinks and swapped ancestors cannot redirect writes; a changed report-directory identity causes refusal. This is not protection against arbitrary control of the operating-system account.
- Missing OCR, table/layout ambiguity, bounded English semantics and content outside recognized text remain limitations. Matching structured agreement context is not general contract interpretation. The operator remains responsible for comparing all pages, tables and billing records to the authoritative accounting system.


## v0.3.7 statement-integrity policy

ScopeLedger treats recognized delivery and rejection quotations as **one complete
supported statement**. A rejection row cannot account for a second denial of a
separate service on the same line. A delivery claim requires one supported
calendar date and a matching `delivered_on` ledger date. A purported delivery
followed by a correction, forecast, or condition does not establish consumed
scope and must be resolved by an authorized human. Pending decisions also use
complete service-specific sentences rather than keyword searches. These are
bounded English formats, not general natural-language understanding.

Additional explicit retractions or forecasts in supplied source text withhold
financial readiness where detected. Unknown context or missing source files
cannot be interpreted as approved work automatically. The original-document
mapping gate applies these same semantic checks. Original documents must still
be checked visually and mapped manually; no source hash authenticates delivery,
approval, or billing rights.
