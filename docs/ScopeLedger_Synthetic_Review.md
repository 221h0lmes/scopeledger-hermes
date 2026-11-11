# ScopeLedger | Owner review draft

Client: **Northstar Studio \(fictional\)**  
Project ID: `northstar`  
Evidence snapshot SHA-256: `396c2d7cf39de0a89aa41d562d4237d1c5938dd3f5fdcea535e3b5d7410733f1`

**Draft only. No invoice has been sent or authorized.**
Recognized text patterns can corroborate quantities, rates and approvals; they cannot authenticate signers, contract validity or billing rights.
Hermes may share tool outputs with its configured model provider during inference.

## Reconciliation snapshot

- Sourced, approved but uninvoiced work for owner review: **USD 300.00**
- Additional work with approval not established: **USD 150.00** (not billable as stated)
- Already invoiced extra work in supplied records: USD 300.00

## Findings

| Delivery | Service | Extra units | Approved / invoiced | Status | Owner-review amount |
|---|---|---:|---:|---|---:|
| D002 | Landing page | 2 | 2 / 1 | READY_FOR_OWNER_REVIEW | USD 300.00 |
| D004 | Revision round | 1 | 0 / 0 | NEEDS_APPROVAL | USD 0.00 |
| D005 | Web banner | 1 | 1 / 2 | EVIDENCE_OR_BILLING_EXCEPTION | USD 0.00 |

## Source anchors (local only)

- Agreement: `sources/agreement.txt:3` (SHA-256 `766816e52f10e7e4…`)
- Delivery D002: `sources/work_log.txt:4` (SHA-256 `abd4011914965f82…`); agreement terms matched (limited grammar)
  - Approval A001: `sources/client_messages.txt:2` (SHA-256 `e4e62a145f18f8d7…`); terms matched
  - Invoice I001: `sources/invoices.txt:2` (SHA-256 `e7a088d761207a86…`); terms matched
- Delivery D004: `sources/work_log.txt:5` (SHA-256 `abd4011914965f82…`); agreement terms matched (limited grammar)
  - Approval A002: `sources/client_messages.txt:3` (SHA-256 `e4e62a145f18f8d7…`); terms matched
- Delivery D005: `sources/work_log.txt:6` (SHA-256 `abd4011914965f82…`); agreement terms matched (limited grammar)
  - Approval A003: `sources/client_messages.txt:4` (SHA-256 `e4e62a145f18f8d7…`); terms matched
  - Invoice I002: `sources/invoices.txt:3` (SHA-256 `e7a088d761207a86…`); terms matched

## Exceptions requiring human investigation

- D005: Invoiced units exceed measured extra units, Invoice quantity exceeds sourced approval quantity

## Owner checklist

- [ ] Confirm the agreement and authorized rate with the client.
- [ ] Confirm approval was given by an authorized person and not later rescinded.
- [ ] Verify billability under the agreement and applicable law.
- [ ] Compare against the complete invoicing ledger, not only supplied rows.
- [ ] Only then manually prepare a change request or invoice in your normal system.
