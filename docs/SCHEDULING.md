# Operator-approved scheduling through Hermes

Schedules are **not** created by installing ScopeLedger. A normal Hermes agent-backed cron job consumes inference allowance when it actually executes. A paused schedule consumes no model tokens and permits a no-run configuration check. The Hermes gateway must be running for ordinary scheduled firing. A manual prompt does not set up a schedule.

Check the CLI options in your installed version first:

```bash
hermes cron create --help
hermes cron list
hermes cron status
hermes cron doctor
```

### Safe paused canary (does not run)

When the installed `create --help` supports `--paused`, intentionally create a dormant weekly job:

```bash
hermes cron create "0 9 * * 1"   "Use only ScopeLedger tools to audit project demo and explain any evidence blockers. Never issue invoices or contact clients."   --skill scopeledger --timezone Asia/Manila   --name "ScopeLedger paused demo"   --paused --paused-reason "Configuration check only; no execution authorized"
hermes cron list
```

**Do not resume, force-run, tick or remove a job without intending that action.** Paused creation confirms only storage/configuration. It does not prove scheduled tool execution. Job ID, not necessarily the display name, is needed for later resume/remove actions; check `hermes cron --help`.

### Production trigger options

- Manual: user asks Hermes to audit one named project.
- One-shot: when the owner supplies a real target date, create a one-time schedule at that timestamp.
- Recurring: a weekly/monthly schedule revisits an **already human-verified** project; changed originals invalidate the attestation and cause a BLOCKED result.

For a project start date + 28 days, explicitly compute the actual desired timestamp in the correct timezone, show the owner, and only then create the one-shot job. Do not use a generic project-management status because no ClickUp/Jira integration exists.

If the user wants guaranteed zero LLM consumption, they must choose a separately configured `--no-agent` script job and check its exact behavior; this release does not install one. No job may approve documents or invoice clients automatically. Do not connect a paid fallback provider without opt-in.
