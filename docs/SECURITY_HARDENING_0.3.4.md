> Historical v0.3.4 verification. Later probes exposed additional defects; see [v0.3.6 repairs and limits](SECURITY_HARDENING_0.3.6.md).

# ScopeLedger 0.3.4 bounded financial-integrity repairs

The baseline v0.3.3 workspace passed 88 core/document and 35 stress tests. Both new blocker classes were nevertheless independently reproduced using fictional Northstar projects, isolated temporary storage and simulated human review receipts. No installed Hermes plugin, credentials, client data, external service or scheduled job was changed.

## Original failures and repaired behavior

| Reproduction | Observed v0.3.3 result | Repaired result |
|---|---|---|
| Append `D002 | Invoice INV-204 billed one additional landing page at USD 300.` to `sources/invoices.txt`, leaving `invoices.csv` unchanged | Structured and original-document workflows both returned USD 300 ready from audit and draft, with `ledger_complete=true`. The synthetic mapping attestation passed. | Structured audit and draft return zero ready, `ledger_complete=false`, and an explicit INV-204 diagnostic at `sources/invoices.txt:4`. D002 becomes provisional; D005 retains its billing exception. The original-document mapping attestation refuses the unreconciled supplied ledger, so both native tools block. |
| Replace the quota with `Not five landing pages are included.` and update the matching structured anchor and fictional original consistently | Both workflows verified agreement semantics and returned USD 300 from audit and draft. Synthetic original-document review and mapping passed. | Agreement semantics are false and structured audit/draft return zero ready. Original-document extraction still succeeds, but affirmative review receipts cannot certify these service terms; gate, audit and draft block. |
| Replace the quota with `0.5 landing pages are included.` using the same consistent inputs | Both workflows verified agreement semantics and returned USD 300 from audit and draft. | Same safe refusal as the negated quota; the numeric suffix can no longer masquerade as an integer quota. |

## Implementation

- `evidence_semantics.py` parses whole included-quantity clauses and supported price sentences, preserves quantity-word/integer support, rejects unsupported contextual qualifiers, and exposes parsed invoice identity and financial fields for reconciliation. Negation spanning a line break also fails closed.
- `auditor.py` enumerates concrete billed-invoice claims across every captured supplied source file. A claim must have supported wording, a delivery identity, one source occurrence and one verified structured mapping matching its invoice fields. Duplicate or inconsistent external invoice/service identities remain unresolved. Errors retain source locations and identities; provisional per-delivery findings survive the project-level withholding.
- `intake_gate.py` refuses certification when the auditor detects an incomplete supplied ledger. A human checkbox cannot override contradictory terms or missing invoice mappings.
- Runtime version, manifest and report filename suffixes identify `0.3.4`. Versioned receipts and report paths remain separate from earlier engine outputs.

The existing Bridge stress test now checks both stages explicitly: deleting only an orphan's CSV mapping remains blocked; a separate synthetic fixture without that transaction in either input restores the expected USD 450. This corrects an obsolete expectation rather than permitting production evidence deletion.

## Executable verification

```bash
python3 -m unittest discover -s tests -p test_financial_integrity.py -q
python3 -m unittest discover -s tests -p test_release_repairs.py -q
python3 -m unittest discover -s tests -q
python3 stress_suite/run_tests.py -q
python3 scripts/demo.py
```

Expected totals: **25 new financial-integrity tests**, **22 retained v0.3.3 adversarial tests**, **113 total core/document tests**, and **35 stress tests**. The combined suite contains **148 tests, zero failures, zero skips**. New cases cover omitted and fully mapped INV-204, duplicate mappings, valid partial billing, incorrect delivery binding, unlinked sources, copied/conflicting invoice identities, unsupported fractional invoices, unrelated prose, quota negation/fractions/qualifiers/contradictions, valid word/digit quotas, and both native workflows with affirmative synthetic document reviews.

Northstar retains USD 300 approved-uninvoiced, USD 150 pending approval, D005's exception and successful draft generation. The four registered tools remain unchanged. The captured-byte extraction, revocation/credit checks and secure atomic-write regressions remain passing.

Doctor and Validator were attempted against the workspace. Their launcher failed before plugin inspection because it requires `.prepare.lock` and `.install.lock` writes under `~/.hermes`. Both checks are **UNVERIFIED**; sandbox permissions were not changed and no runtime installation was performed. A fresh live v0.3.4 Hermes session is also unverified.

## Scope and remaining limits

`ledger_complete=true` means no detected unreconciled recognized statements or structured references in the supplied snapshot. It does **not** prove completeness of invoices that were never supplied. Ordinary prose in structured source files is not an invoice claim. The original-document gate retains its separate stricter content-mapping checks.

The statement grammar and agreement language are deliberately bounded. Repeated claims for one invoice/service need richer external line identity and remain blocked; this is not general accounting reconciliation. Credits, tax, discounts, OCR, signatures, approver authority and general contract interpretation remain unsupported or require authoritative human/accounting review. Optional secondary parser packages remain absent in this environment; their captured-input contracts are exercised with local test doubles, and actual Poppler extraction is tested.

Existing v0.3.3 snapshot-provenance requirements and [older extraction migration](SECURITY_HARDENING_0.3.3.md#existing-extraction-migration) still apply. Hash-matching attestations never override the repaired semantic checks.
