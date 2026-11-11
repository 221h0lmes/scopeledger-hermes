# ScopeLedger · Pre-close billing evidence checkpoint

**Native Hermes Agent plugin · v0.3.7 · 4 tools · local-first · human-controlled**

A small creative or marketing agency delivers more work than its original contract covered. Some extra work is approved but missing from the invoice; some isn't approved; some invoices overstate delivered or approved quantities. **ScopeLedger helps surface these differences before an agency closes a project** and produces a source-linked **owner-review packet**, without issuing invoices or contacting clients.

> A review candidate is **not** legally collectible revenue. ScopeLedger does not authenticate clients, signatures, contract validity, or a complete external invoice ledger.

## What you can demonstrate today

- Four native Hermes tools, exercised through local registration and handler tests. A fresh live v0.3.7 Hermes runtime has not been verified here.
- Deterministic fixed-unit scope reconciliation: delivered quantities versus included, approved and invoiced extra units.
- Evidence excerpt matching, narrowly recognized quantity/rate/approval language, provenance hashes and exceptions. Known ambiguous patterns and material reversals withhold readiness; unsupported wording still requires human verification. No automated completeness guarantee.
- PDF and DOCX **original-document inspection**: text extraction, per-page diagnostics for PDFs, table rows for DOCX, source SHA-256 and extraction manifests. Optional second parsers issue warnings when unavailable.
- A mandatory explicit **human review + source-to-row mapping gate** for opted-in original-document projects, including invalidation on changed files.
- Local HTML and Markdown owner-review reports and idempotent SQLite receipts.
- Manual prompts, plus **optional Hermes-native one-shot or recurring schedules**. Scheduling is operator configured; no background job starts on installation.

**Not yet implemented:** Google Drive OAuth/Picker, direct cloud-folder syncing, generalized AI-generated financial ledger extraction, reliable text from scanned PDFs without OCR, or automated approval of source-to-ledger mappings. A user can download explicitly selected Drive files and stage them locally. Do not present this as a live Google Drive connector.

## Native tools

| Tool | Purpose |
|---|---|
| `scopeledger_projects` | Discover user-staged local projects and bundled fictional `demo` |
| `scopeledger_document` | Inspect a selected original PDF/DOCX in the plugin-owned inbox; create source-linked extraction manifest, pending human review |
| `scopeledger_audit` | Reconcile supplied structured records and recognized invoice statements; enforce original-document review/mapping attestations |
| `scopeledger_draft` | Write owner-review Markdown and standalone HTML; never send invoices or messages |

The extra Hermes `scopeledger` skill helps the agent choose tools. Financial calculations happen in Python, not by asking an LLM to invent amounts. Registered tools run locally. Hermes may send tool responses to the configured model provider for its normal inference.

## Install and verify

Requirements: Linux (uses `fcntl`), Python 3.11+, Hermes Agent with plugin support, Poppler utilities (`pdfinfo`, `pdftotext`) for PDF intake. `python-docx` and PyMuPDF are **optional** secondary parsers and their absence is surfaced as a verifier warning, not hidden.

```bash
# From this repository's root:
python3 -m unittest discover -s tests -q
python3 stress_suite/run_tests.py -q
python3 scripts/demo.py
hermes plugins doctor "$PWD" --ci
hermes plugins validate "$PWD" --install-deps
# From a freshly cloned, reviewed source checkout, without an existing install:
DEST="$HOME/.hermes/plugins/scopeledger"
if test -e "$DEST"; then
  echo "Existing plugin detected. Back it up before replacing it; do not overwrite." >&2
else
  mkdir -p "$HOME/.hermes/plugins"
  install -d -m 700 "$DEST" "$DEST/skills/scopeledger" "$DEST/examples/northstar/sources" "$DEST/docs"
  install -m 644 __init__.py auditor.py document_intake.py evidence_semantics.py intake_gate.py \
    report_view.py schemas.py storage.py tools.py plugin.yaml README.md LICENSE "$DEST/"
  install -m 644 skills/scopeledger/SKILL.md "$DEST/skills/scopeledger/"
  install -m 644 examples/northstar/project.json examples/northstar/*.csv "$DEST/examples/northstar/"
  install -m 644 examples/northstar/sources/*.txt "$DEST/examples/northstar/sources/"
  install -m 644 docs/*.md docs/*.html "$DEST/docs/"
  hermes plugins doctor "$DEST" --ci
  hermes plugins enable scopeledger
fi
# Restart any running Hermes CLI or gateway after activation.
```

For existing installations, back up the installed plugin first and use a verified replacement process. Existing user data lives separately in `~/.hermes/plugin-data/scopeledger/` and must never be overwritten by an upgrade. The public repository does not ship a self-updater. Hermes profiles may differ, so always verify the installed plugin path before activation.

In Hermes ask:

> Use only ScopeLedger. Audit `demo`, explain approved-but-uninvoiced and pending-approval work, flag any overbilled invoice line, then create a local owner-review report. Do not issue invoices or contact clients.

Bundled **fictional** Northstar expectations: USD **300.00** approved-but-uninvoiced candidate (D002), USD **150.00** not approved (D004), and D005 billing-quantity exception. These are test-fixture values, not real recovered money. `scripts/demo.py` uses disposable local storage and no model calls.

### More difficult reproducible case

```bash
python3 stress_suite/run_tests.py -q
```

Four fictional projects and 35 deliveries check partial invoicing, conflicting approvals, duplicate evidence, unknown invoice references, overbilled lines, two currencies (USD and PHP), concurrency, record order and source changes. The external Hermes chat test is distinct from these offline tests.

## Original PDF/DOCX intake

Use one folder in Hermes plugin data per project; identify the roles `agreement`, `deliveries`, `approvals`, `invoices` explicitly. Documents **must be independently checked**, not just read by an LLM. The tool creates an immutable extraction text + manifest with file and content hashes, numeric-token summaries, parser issues and `PENDING_HUMAN_REVIEW` / `NOT_MAPPED` states. It does not create a verified invoice CSV automatically.

**Safety gate:** Opting into document intake creates a sticky local requirement outside the original-document inbox; deleting that inbox never bypasses verification. An opted-in project cannot be audited or drafted while mandatory original documents, human verification or source-to-structured-row mapping are missing/changed. The user must compare every original page, invoice row, discount, credit, tax and total to the structured records, then explicitly attest in the local CLI. Unmatched text blocks mapping even without digits; only standalone page markers are ignored. Credits, taxes, discounts and cancellations are conservative blockers, not implemented accounting adjustments. The mapping gate is strict but cannot prove completeness of an unseen external ledger. Scanned/ambiguous documents remain blocked until adequately reviewed.

See [Document intake and permissions](docs/INTAKE_AND_PERMISSIONS.md) for the exact opt-in commands and restrictions.

## Manual and scheduled use

- **Manual:** User explicitly asks Hermes to audit a project. For original-document projects, inspect documents and finish the human gate first.
- **Scheduled:** User explicitly configures one-shot or recurring Hermes cron, including a `--paused` canary for safe configuration tests. These are normal agent jobs and **consume model allowance when executed**, unless a separately configured `--no-agent` job is used. We do not silently create or activate any schedule.

See [Safe scheduling](docs/SCHEDULING.md) for commands and run/charge boundaries.

## Data and permissions disclosure (catalog rule 13)

| Surface | Behavior |
|---|---|
| Network & telemetry | **No network calls by ScopeLedger itself, and no plugin-originated telemetry**. Hermes itself can use its configured model provider; model usage and any subscription charges follow that provider configuration. |
| Google Drive | No connector or OAuth code in this release. No Drive scopes requested. Downloading a selected file manually is not an OAuth integration. |
| Local reads | Bundled synthetic example; user-selected files staged under ScopeLedger-owned `inbox/<project>`; structured project records under ScopeLedger-owned `projects/<project>`. PDF intake invokes system-installed `pdfinfo`/`pdftotext` on these files. |
| Local writes | Source-hash-bound extracted texts/manifests, human review attestations, SQLite receipts, HTML and Markdown owner reports under ScopeLedger's Hermes-owned plugin-data directory. Originals are not modified by the plugin. |
| Shell / processes | The PDF tool starts bounded Poppler subprocesses on selected local PDFs. No long-running background processes from the plugin. Optional local developer scripts operate only when invoked. |
| Credentials | The plugin does not read credentials, tokens, Google accounts, Hermes auth storage or unrelated paths. |
| Unattended runs | None are created by installation. Cron schedules, if the owner separately creates them, require running Hermes gateway and a configured provider; they cannot approve human verification. |
| Retention | User-owned local reports, attestations, extracted data and audit receipts persist until the user removes them. No automatic remote upload or deletion. |
| Limits | Structured fixed-unit work and narrowly supported English wording; two-decimal currencies only; no tax/legal/accounting system certification or OCR guarantee. The plugin is not financial/legal advice. |

### ScopeLedger project structure

```text
~/.hermes/plugin-data/scopeledger/
  projects/<slug>/project.json, deliveries.csv, approvals.csv, invoices.csv, sources/*.txt
  inbox/<slug>/*.pdf, *.docx              # opt-in originals
  extractions/<slug>/<sha-prefix>/...     # immutable text + manifests
  attestations/<slug>/...                 # explicit human review/mapping receipts
  reports/*.html, *.md                    # owner review only
  audit_receipts.sqlite3
```

Project-data directory is obtained from `scopeledger_projects` because Hermes profiles may differ. Slugs and filenames are restricted to safe characters. Inputs are treated as untrusted; reports escape user text and source paths are checked. The first four original roles must be present for document-intake project attestation.

## Release verification status

The v0.3.7 source has been validated **offline in the build environment** with 161 core/document tests and 35 agency stress tests (196 total), including 15 new complete-statement and financial-output regressions. Native Hermes Doctor, Validator, and live v0.3.7 execution have **not** been run on the operator's machine. This is not a general natural-language contract verifier: unsupported rejection, pending-approval, or delivery wording is conservatively unverified. All figures are owner-review candidates from supplied data; human financial verification is required. Once installed, raw tool results must show engine `0.3.7` and `_v0_3_7_` report filenames. See [v0.3.7 statement-integrity verification](docs/SECURITY_HARDENING_0.3.7.md).

### Historical verification notes

The historical v0.3.6 source passed **146 core/document tests and 35 multi-agency stress tests** (181 synthetic offline cases). Its 15 new approval/source-context tests include 75 parameterized checks of wrapping and source position. The earlier context, extraction and atomic-output regressions remain passing. These local results do not authenticate financial rights or prove the absence of undiscovered defects. A fresh v0.3.6 Hermes runtime remains unverified here; earlier versions' operator-reported results do not qualify this changed source. The known launcher restriction requires lock-file writes outside this workspace, so Doctor/Validator remain unverified here. No installation, gateway restart, recurring execution or publication was performed. Fresh raw runtime results must identify engine `0.3.6` and `_v0_3_6_` reports.

Version 0.3.6 scans approval denials in the full captured text and validates unmatched context in linked approval/invoice sources and supplements containing approval/invoice language. A denial can be accounted for only by a verified, identity-bound rejection row. Document text no longer becomes an exempt heading merely because it matches the source, lacks digits or precedes a record. Only bounded, explicitly recognized headings and administrative notes are exempt, at any position. Unsupported context withholds financial readiness and prevents document certification. The `source_context_complete` flag describes these supported checks, not external financial completeness. See [v0.3.6 repair verification](docs/SECURITY_HARDENING_0.3.6.md).


Version 0.3.5 scans complete supplied source text before locating invoice claims, so physical line breaks cannot hide `Invoice <id> billed ...` evidence, including in unlinked supplements. Wrapped evidence without a supported unique structured anchor is a blocker. Agreement body text uses a closed supported grammar: only configured-service quotas, unit rates and the supported written-approval requirement are accepted. Unknown clauses, including separate-line or separate-sentence conditions/negations, withhold readiness. Only standalone formatting markers and narrowly supported leading SOW title/date or fictional-party metadata are excluded. Arbitrary agreement prose remains unsupported; a matching human receipt cannot override this check. Report locks, temporary files, collision checks and both final reports use one pinned directory descriptor and atomic no-overwrite publication. A changed report-directory identity causes refusal. See [v0.3.5 repair verification](docs/SECURITY_HARDENING_0.3.5.md).


Version 0.3.4 enumerates recognized `Invoice <id> billed ...` statements across every supplied structured source file, including files unreferenced by CSV rows. Missing, duplicate or inconsistent mappings withhold project readiness and set `ledger_complete=false`; the invoice matcher itself does not classify unrelated prose as a billed statement. Separate source-context checks reject unsupported financial-role body text while allowing the supported administrative notes. This flag describes recognized supplied evidence and structured references, **not completeness of an unknown external billing system**. Agreement quotas require affirmative integer clauses and supported surrounding context; negation, fractions, contradictory quotas and unsupported qualifiers fail semantic verification even with human attestation. See [historical v0.3.4 repairs](docs/SECURITY_HARDENING_0.3.4.md).

The retained v0.3.3 controls bind original evidence to delivery identity and a single occurrence, check every nonempty document content line against mapped rows or explicitly supported metadata, and withhold project readiness for invoices assigned to included-scope work. DOCX parsers consume captured bytes; PDF subprocesses consume a private temporary snapshot of those same bytes. Extraction manifests declare this provenance policy. Marker, extraction and attestation writes reject symlinked ancestors and publish complete files atomically without overwriting. **Older extractions must be regenerated and reviewed; existing review receipts cannot establish the new extraction guarantee.** See [repair verification and migration](docs/SECURITY_HARDENING_0.3.3.md).

## Demo & support

- [80-second real Hermes demo storyboard](docs/DEMO_90_SECONDS.md)
- [Security, limitations and data permissions](docs/INTAKE_AND_PERMISSIONS.md)
- [Hermes scheduling with a paused canary](docs/SCHEDULING.md)
- [Synthetic owner-review HTML preview](docs/ScopeLedger_Synthetic_Preview.html) (offline illustration, not proof of a live Hermes run)

Hermes catalog validation: `hermes plugins validate "$PWD" --install-deps`. Catalog listings are human-reviewed and pin one full commit SHA. This repository is **not affiliated with Nous Research**.
