> Historical verification notes for v0.3.2. Current repairs and verification limits: [v0.3.6](SECURITY_HARDENING_0.3.6.md).

# ScopeLedger 0.3.2 · Astra follow-up fixes (2026-11-11)

This is a limited, synthetic-test hardening patch. It does **not** add Google Drive OAuth, an automatic invoice mapper, OCR, billing-system reconciliation, or a live scheduled trigger.

## Defects addressed

1. Previously, keyword filters could skip a supplied numeric table row such as `D002 | Landing page | 1 | USD 300.00`. Now any non-marker digit-bearing line in supplied delivery, approval and invoice originals must match a structured-source quotation exactly or the intake mapping gate blocks. This deliberately favors false-positive review over a missed invoice.
2. A separate-line approval revocation or source agreement cancellation can no longer silently coexist with a READY amount. Recognized reversal vocabulary triggers fail-closed document intake and suppresses structured-only candidate totals. General contract understanding is **not** claimed.
3. Review receipts must identify the correct project, original file and role, contain matching hashes, and affirm both original-line review and warning resolution. A receipt whose approval fields are `false` cannot unlock the gate.
4. The auditor captures all input bytes once and uses those exact bytes for all calculations and the digest. A final snapshot comparison detects persistent edits; transient changes made and restored after the snapshot cannot contaminate computed amounts.
5. Tracked DOCX revisions are recognized by expanded namespace names rather than a hardcoded `w:` XML prefix.
6. The extraction writer and mapping verifier reject symlinked ancestors under the plugin-data root. They do not claim protection against an adversary with unrestricted write access to the same operating-system user account.

## Evidence and limits

- 66 core/document unit tests plus 35 multi-agency cases passed using fictional local fixtures. Nine new tests target the reported vulnerabilities and their combinations.
- Tests and documentation are provided for external review; native Hermes installation must be run locally before publishing a verified execution claim.
- Financial readiness is **candidate for owner review**, never collectible revenue or an invoice. Positive and negative semantic parsing recognize a bounded subset of English; novel contracts and billing adjustments should remain manually reviewed.
- Google Drive acquisition, one-click real-agency onboarding, OCR and scheduled execution remain unimplemented or unverified. No OAuth scopes or cron jobs are installed automatically.
