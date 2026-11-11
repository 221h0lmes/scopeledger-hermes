# ScopeLedger 0.3.7: Complete-statement integrity repair

## Source and adversarial evidence

The supplied v0.3.6 source passed 146 core/document and 35 stress tests, but
Astra reported and this independent repair process reproduced two critical
misclassifications in synthetic Northstar fixtures:

1. A single `REJECTED` revision-round row contained **two** rejections, one
   additionally denying the landing pages. An earlier `re.search` + service
   substring check validated the whole line as if it contained only a
   revision-round rejection. The auditor then exempted all denial matches on
   that source line, leaving USD 300 READY. This is a *real bug*.
2. A delivery quote beginning `Delivered five original landing pages on ...`
   could include later text saying those pages **were never delivered**, were a
   **forecast**, or were **conditional**. An unrestricted `.+` after `on`
   accepted it and consumed included quota. This is a *real bug*.

## Repairs

- `approval_quote()` rejects any multi-sentence or qualified rejected quotation.
  Exactly one complete supported denial for the mapped service may be marked
  semantically verified. The existing source-line identity binding and
  project-wide unaccounted-denial scan remain in place.
- `delivery_quote()` requires one complete supported delivery/completion
  sentence ending in an ISO date or an English month/day. The auditor and
  original-document mapping gate both compare that date with `delivered_on`.
  Retracted, conditional, forecast, invalid-date and multi-sentence deliveries
  fail closed. A separate source retraction/forecast detected by the bounded
  material-context scan withholds candidate amounts.
- `PENDING` approvals also require one complete, service-specific supported
  sentence. Unsupported mixed clauses do not inherit approval from keywords.
- Unsupported approval/invoice source-context diagnostics identify the source
  and line without reproducing raw untrusted text in an owner-facing report.
  The existing stress test protecting against instruction replay continues to
  pass.
- Historical v0.3.6 security fixes for wrapped evidence, original-file
  snapshot provenance, atomic report files and receipt certification remain
  tested. No Google Drive, OCR, automated invoice issuing or payment accounting
  is added.

## Executed offline tests

```
python3 -m unittest discover -s tests -p test_statement_integrity.py -q
python3 -m unittest discover -s tests -q
python3 stress_suite/run_tests.py -q
python3 scripts/demo.py
```

- **15 newly authored complete-statement regression methods passed**, including
  the two Astra cases, alternative denial language, forecast/conditional claims,
  document certification refusal, incorrect dates, valid rejection and ISO-date
  controls, and a separate-line delivery retraction.
- **161 core/document tests passed**, including all 146 earlier tests.
- **35 multi-agency stress tests passed**. Total **196 tests**, no failures.
- Bundled fictional Northstar remains USD 300 approved-uninvoiced review,
  USD 150 pending approval and D005 billing exception; report draft succeeds.

These are *offline* results from the patched uploaded source. The actual
operator's Hermes Doctor, Validator, installed runtime and live v0.3.7 smoke
must be checked locally and must not be claimed as already passed.

## Scope and remaining limitations

This release is a conservative structured-ledger reconciliation assistant,
not a general English contract interpreter. It cannot prove a complete
external invoice ledger, independent source authenticity, full contract
validity or payment rights. Date-only statements without a year are checked
against the year entered in the structured ledger; this does not authenticate
the year. Unsupported or ambiguous clauses require human review. The receipt
mechanism records operator attestations but cannot independently establish
that human review actually happened. Real-client end-to-end onboarding and
recurring cron execution have not been demonstrated in this build.
