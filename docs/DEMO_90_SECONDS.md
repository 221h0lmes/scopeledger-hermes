# 75–85 second live judging demo

**Use the actual Hermes UI, not fabricated tool output.** Show current `scopeledger` tool names and a real locally generated HTML report. The demo dataset is fictional. There is no tested Drive OAuth connector or live cron execution to claim.

| Seconds | Scene | Spoken line |
|---|---|---|
| 0–10 | Show fictional source agreement, deliveries, approvals and invoices | “Agencies don't only lose money when clients fail to pay. They also forget work they never invoiced.” |
| 10–25 | In Hermes, ask to audit `demo` using `scopeledger_audit` | “ScopeLedger is a native Hermes tool that reconciles scope, delivery, approval and invoice evidence.” |
| 25–40 | Display $300 D002 candidate, $150 D004 pending, D005 overbilling exception | “Three different decisions. Only the first is even a candidate for owner review. Nothing is automatically billable.” |
| 40–58 | Call `scopeledger_draft`, open rendered report in Firefox | “Here's the audit packet, including exceptions and exact source hashes.” |
| 58–73 | Show `scopeledger_document` on `northstar_invoices.pdf`, highlight pending manifest | “We also read original invoices and flag extraction uncertainty. No verified mapping, no release of financial claims.” |
| 73–83 | Return to report, show no invoice sent | “Four native tools. Deterministic financial rules. Human sign-off. No autonomous billing.” |

Suggested single Hermes prompt for recording:

> Use only ScopeLedger tools. Audit the fictional `demo` project, report approved-but-uninvoiced and pending-approval amounts, explain the overbilling exception, then create an owner-review draft. Do not create an invoice or contact clients. Show report paths.

For the PDF scene, stage the synthetic originals using `bash scripts/stage_synthetic_documents.sh`, then in a **fresh session** ask `scopeledger_document` to inspect `northstar_invoices.pdf` under project `northstar` with role `invoices`. Be careful: the `demo` project and the `northstar` staged document-intake project have different readiness requirements.

In Firefox on sandboxed Ubuntu, copy the output HTML into `~/Documents` instead of relaxing permissions on the hidden Hermes profile folder. Keep the final X upload below 90 seconds.
