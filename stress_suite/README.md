# Multi-agency deterministic stress tests

The 35 tests operate on four fictional agency projects, 35 deliveries, USD and PHP. They exercise included quotas, partial billing, orphan invoices, false approvals, duplicate delivery anchors, reused approval evidence, wrong-service invoices, row-order stability, concurrent drafts and SHA-bound provenance. All data is synthetic; tests are not independent proof of external financial completeness.

| Project | Currency | Candidate owner review | Pending/unapproved | Reconciled extra work already invoiced |
|---|---|---:|---:|---:|
| stress_atlas | USD | 1,020.00 | 780.00 | 825.00 |
| stress_bridge | USD | 0.00 | 200.00 | 0.00 |
| stress_quartz | USD | 0.00 | 50.00 | 0.00 |
| stress_lotus | PHP | 1,550.00 | 350.00 | 350.00 |

Bridge has an orphan invoice reference, so approved candidate USD 450 is **withheld at project level**. Atlas has an overbilled D114 line. These are independently set *synthetic expectations*, not authenticated receivables.

Run from the repository root with: `python3 stress_suite/run_tests.py -q`. All tests create temporary copies and do not access Hermes, Google Drive, or real customer data.
