> Historical release notes for v0.3.1. For current fixes see [v0.3.6](SECURITY_HARDENING_0.3.6.md).

# ScopeLedger 0.3.1: Final blocker repairs

This release addresses five counterexamples from an independent read-only Sol review of v0.3.0, without adding any network permissions or autonomous billing.

1. **Sticky original-document opt-in:** Inspection registers a requirement outside the inbox. Previously inspected projects are recognized via extractions/attestations. Local upgrade migrates existing projects into persistent markers. Deleting the inbox cannot restore the legacy audit path.
2. **Attested snapshot binding:** Each document-intake audit checks that the *actual* audited structured digest equals the human-attested snapshot; original-document identity is rechecked after auditing. This protects against straightforward mid-audit edits. No general guarantee against malicious actors with unrestricted filesystem control is claimed.
3. **No hidden same-line conditions:** Every financial-looking source line must be fully accounted for by a mapped evidence quote, except for a strict delivery-ID prefix. A trailing credit, cancellation, tax, or other qualifier blocks attestation until reviewed and modeled.
4. **No rate-prefix acceptance:** Contract rate clauses must terminate at a recognized sentence boundary. Wording such as `USD 300 total for two pages` or `USD 300 per ten pages` is not treated as a per-unit price.
5. **DOCX content controls:** Body-level Word content controls are traversed; embedded text is preserved and their presence produces an explicit visual-review warning. Unsupported blocks also warn instead of silently disappearing.

New tests reproduce each of the five defects, including a mutated ledger between verification and audit. The 57 core/document and 35 complex agency tests are local synthetic regression tests, not a substitute for a live Hermes integration test or independent accounting audit.

**Unchanged limitations:** No Google Drive OAuth/Picker, no general-purpose document-to-financial-ledger model, no scanned-document OCR, no installed scheduled job, no client contact, no invoice issuance. Manual review is required for financially material unknowns.
