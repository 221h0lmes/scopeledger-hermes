> Historical verification notes for v0.3.3. Current repairs and verification limits: [v0.3.6](SECURITY_HARDENING_0.3.6.md).

# ScopeLedger 0.3.3 repair verification

All probes use fictional Northstar documents, simulated review attestations and disposable local storage. No installed plugin, credentials, private data, external service or gateway was changed. These results establish local implementation behavior, not a live Hermes release qualification.

## Reproductions and repairs

| Finding | Original observed reproduction | Repair and observed result |
|---|---|---|
| P1: invoice reassignment | Reassign I001 from D002 to D001 and rewrite only the structured text prefix, leaving the original invoice unchanged. Synthetic mapping passed; native audit and draft both returned USD 600 ready. | Original lines retain delivery identity and invoice identifier, must occur exactly once, and must agree with quantity, service, rate and currency. Reassignment now refuses mapping and both native tools return `SOURCE_VERIFICATION_BLOCKED`. The raw auditor independently returns zero ready and preserves D001's `IN_SCOPE_INVOICE_EXCEPTION` and D002's provisional finding. |
| P2A: denial without digits | A separate approval paragraph, `I do not approve any additional landing pages.`, passed mapping and both native tools retained USD 300. | Unmatched content is no longer filtered by digits or selected keywords. Mapping, audit and draft block. Structured unaccounted denials also withhold readiness; mapped rejections retain their existing per-delivery behavior. |
| P2B: page prefix | An additional invoice paragraph beginning `[PAGE 1] D002 | Invoice INV-999 billed one additional landing page at USD 300.` passed mapping and both native tools retained USD 300. | Only complete standalone markers are ignored. The invoice-bearing paragraph blocks mapping, audit and draft. |
| P2C: agreement credit | `Credit USD 300.00 applies against additional landing pages.` in an additional agreement paragraph passed mapping; audit and draft retained USD 300. | Every agreement content line is checked, and unsupported credits/adjustments are blockers across all roles. Audit and draft block; a credit in structured-only source context yields zero ready. No credit, tax or full accounting reconciliation is implemented. |
| P3: extraction provenance | A deterministic hook replaced the live DOCX only during parsing and restored it before the final hash check. Its manifest recorded the original hash while the extraction contained replacement text. The PDF parser also received the live original pathname. | ZIP/XML and secondary DOCX parsing use separate in-memory streams over the same captured bytes. Poppler receives a private, read-only temporary snapshot; the secondary PDF parser receives the captured bytes. Change-and-restore tests retain the original invoice text, source/extraction hashes and page diagnostics. Snapshots are removed after success and injected failure. |
| P4: marker output ancestor | A symlink at `document_intake_required` redirected the marker outside the isolated data root. | The shared writer opens ancestors relative to pinned directory descriptors with `O_NOFOLLOW`, writes a private complete temporary file, then links atomically without replacing evidence. Marker, extraction, manifest and review/mapping receipt writes use it. Static and deterministic swapped-ancestor tests reject the operation; external destinations remain empty. |

Additional regressions cover reassignment without rewriting source text, duplicated invoice identity under a different internal line ID, quantity contradictions, unsupported prose with no financial keywords, unmatched agreement clauses, leaf symlinks, interrupted atomic publication, the review CLI writer, and versioned report identities.

## Executable validation

The unchanged baseline passed 66 core/document tests and 35 stress tests. The repaired workspace passes 88 core/document tests (22 new regressions) and the same 35 stress tests: **123 tests, zero failures, zero skips**.

```bash
python3 -m unittest discover -s tests -p test_release_repairs.py -q
python3 -m unittest discover -s tests -q
python3 stress_suite/run_tests.py -q
python3 scripts/demo.py
```

The demo retains USD 300 ready, USD 150 awaiting approval, D005's billing exception and successful local draft generation. Registration tests preserve all four native tools. Reports and versioned SQLite receipts identify engine `0.3.3`; draft paths contain `_v0_3_3_`, avoiding reuse of v0.3.2 outputs for changed calculations.

Hermes Doctor and validator were attempted against this workspace with model/network work disabled by the task. Both launch attempts failed before plugin inspection because the launcher needs writes to `.prepare.lock` and `.install.lock` under `~/.hermes`. They remain **unverified**, as does a fresh live gateway smoke. The installed plugin was not updated or restarted. An operator must separately run permitted Doctor/validator checks and verify raw audit/draft results from a restarted runtime.

## Existing extraction migration

New manifests declare `input_snapshot: captured-bytes-v1`. The gate refuses manifests without this declaration: the old parser cannot retroactively establish snapshot provenance. Simply relabeling an old manifest does not re-extract its source.

After preserving old evidence under the operator's retention policy, move the old extraction directory out of the active `extractions/<project>/<source-hash-prefix>` location, re-inspect the unchanged originals with the repaired version, visually review every original and extraction, then issue fresh document and mapping attestations. ScopeLedger never overwrites the old evidence automatically. Unsupported adjustments remain blockers even with an affirmative review checkbox.

## Remaining limits

The gate matches supported text and reviewed source context; it does not authenticate signers, prove external ledger completeness, perform OCR, implement general contract understanding or calculate credits, tax and discounts. Optional secondary parser packages were absent in this environment; their captured-byte input contracts are tested with local test doubles, while actual Poppler extraction is exercised. Human review remains mandatory for original documents.

The workspace's `.git` directory is empty, so tracked-file membership cannot be independently verified here. The available source/fixture tree was inspected for credential files, private receipts, runtime reports and release hazards. Existing Markdown/HTML previews are explicitly fictional documentation; no test runtime evidence is written into the source tree.
