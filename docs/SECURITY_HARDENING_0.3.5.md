> Historical v0.3.5 verification. Additional approval/source-context defects were subsequently reproduced; see [v0.3.6 repairs](SECURITY_HARDENING_0.3.6.md).

# ScopeLedger 0.3.5 context and report-output repairs

The v0.3.4 baseline passed 113 core/document and 35 stress tests. Astra's subsequent findings were actual defects: independently constructed fictional cases reproduced hidden wrapped invoice evidence, discarded agreement qualifiers and report-directory output redirection. Existing green tests did not establish the necessary context or filesystem invariants.

## Reproductions and resulting behavior

| Finding | Reproduced v0.3.4 behavior | v0.3.5 behavior |
|---|---|---|
| `D002 \| Invoice INV-204` followed by a newline and `billed one additional landing page at USD 300.`, omitted from CSV | Audit and draft retained USD 300 with `ledger_complete=true`. An unlinked supplemental source could also be certified with original documents. | Whole-text recognition finds the invoice independently of line wrapping. The supplied ledger is incomplete, readiness is zero, diagnostics retain INV-204 and its location, and original-document certification/audit/draft refuse the unresolved mapping. Markdown and HTML both show zero ready for the structured workflow. |
| `Only if a later written agreement is signed:` followed by a newline and the affirmative quota | Semantic verification, synthetic certification, audit and both reports accepted USD 300. | The complete body retains the qualifier. Unsupported context makes agreement semantics false, structured reports show zero ready, and original-document certification and both native tools block. |
| `The following quota does not apply:` followed by a newline and the affirmative quota | Same incorrect verification and USD 300. | Same fail-closed result. Unsupported context in another sentence also blocks, without needing a special keyword for that sentence. |
| Reports directory renamed and replaced by an outside symlink before locking | Lock, Markdown and HTML appeared in the outside directory; draft returned success. | Directory traversal rejects the symlink before lock creation. No outside output appears. Tests also swap the directory after locking and between reports: publication stays relative to the pinned original directory and the changed path identity causes refusal. |

Every regression uses temporary fictional project storage; simulated review flags are not real human verification. No installed plugin, private data, external APIs, model calls, scheduled jobs or publication were involved.

## Root-cause corrections

Invoice recognition runs against the entire captured source text before source locations are assigned. Whitespace inside the recognized claim can span physical lines. A wrapped or ambiguous source statement without a verified unique structured anchor remains a blocker rather than disappearing from the supplied ledger.

Agreement parsing no longer treats newlines as independent affirmative clauses and then ignores other prose. It retains the complete body, normalizes whitespace, checks every clause against a closed supported grammar, and requires service labels to belong to the configured project. Only supported leading SOW title/date and fictional-party metadata, and standalone formatting markers, are excluded. A qualifier before or after a recognized sentence cannot be ignored just because it occupies another line or sentence. This intentionally rejects otherwise harmless unsupported contract prose as well; the engine does not understand general contracts.

Report locking and publication now share the same directory descriptor, opened by traversing ancestors with `O_NOFOLLOW`. The shared immutable writer performs existing-file checks, temporary creation, atomic linking and cleanup relative to that descriptor. Both report formats use it. A final directory identity check prevents success with a path that changed during the operation. These guarantees do not extend to arbitrary control of the operating-system account or changes made after a tool has returned.

## Executable evidence

```bash
python3 -m unittest discover -s tests -p test_context_integrity.py -q
python3 -m unittest discover -s tests -p test_financial_integrity.py -q
python3 -m unittest discover -s tests -p test_release_repairs.py -q
python3 -m unittest discover -s tests -q
python3 stress_suite/run_tests.py -q
python3 scripts/demo.py
```

The new context/security suite contains **18 test methods with 168 parameterized checks**. It covers invoice token wrapping with LF, CRLF, blank lines, tabs and Unicode line separators; conditions/negations before and after supported clauses; separate-sentence unsupported context; valid financial clause wrapping; unsupported service qualifiers; all three report-swap stages; regular-directory substitution; and lock-leaf symlinks.

Final local totals: **131 core/document tests plus 35 stress tests = 166 passing tests**, zero failures, errors or skips. The earlier 25 financial-integrity and 22 v0.3.3 adversarial tests remain passing. Northstar retains USD 300 ready, USD 150 pending and D005's exception. Astra's valid expanded-delivery control retains USD 600 in both workflows; the valid amount is not indiscriminately suppressed.

## Verification boundaries

This is a completed local repair with executable regression evidence, not a guarantee of zero undiscovered defects. A fresh v0.3.5 installed/gateway runtime, actual optional secondary parser packages and the CI Python-version matrix were not exercised here. Earlier operator-reported v0.3.4 runtime success does not qualify this changed source. Doctor/Validator remain unverified when their launcher cannot run without writes under `~/.hermes`.

ScopeLedger still cannot authenticate contract rights, approver authority, external ledger completeness or arbitrary accounting language. Credits, discounts, tax, OCR and general multi-line accounting reconciliation remain unsupported. In particular, recognizing a wrapped invoice as unresolved does not automatically create a verified CSV row. Human review cannot bypass unsupported agreement context or incomplete supplied invoice evidence.

The README now installs an explicit runtime/example/documentation file set, excluding repository metadata, tests and caches. No installation was performed during this repair. The source tree's empty `.git` directory still prevents verification of tracked membership or eventual publication contents.
