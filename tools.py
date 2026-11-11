"""Hermes handlers. Never network, email, invoice, payment or modify client data."""
import json
import os
import re
import stat
import fcntl
from contextlib import contextmanager
from html import escape
from pathlib import Path

from . import auditor, storage, report_view, document_intake


SAMPLE = Path(__file__).resolve().parent / "examples" / "northstar"


def _projects_dir():
    root = storage.data_root() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _directory(slug):
    if slug == "demo":
        return SAMPLE
    return auditor._project_root(_projects_dir(), slug)


def _reply(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def scopeledger_projects(args: dict, **kwargs) -> str:
    try:
        result = [{"project": "demo", "client": "Northstar Studio (fictional)", "type": "bundled read-only synthetic demo"}]
        for folder in sorted(_projects_dir().iterdir()):
            if not folder.is_dir() or folder.is_symlink() or not auditor.SLUG.fullmatch(folder.name):
                continue
            try:
                meta = auditor.project_info(folder)
                result.append({"project": folder.name, "client": meta["client"], "type": "local project"})
            except auditor.InvalidProject:
                continue
        return _reply({"ok": True, "projects": result, "project_data_dir": str(_projects_dir()),
                       "notice": "Only folders inside ScopeLedger's Hermes-owned project-data directory are scanned."})
    except Exception as exc:
        return _reply({"ok": False, "error": type(exc).__name__, "message": str(exc)[:240]})


def _audit(slug):
    if not isinstance(slug, str):
        raise auditor.InvalidProject("Project must be a string")
    # This gate is enforced by native audit AND draft tools, not merely by prompts.
    if slug == "demo":
        return auditor.analyze(_directory(slug))
    from . import intake_gate
    required = intake_gate.intake_is_required(slug)
    approved_identity = None
    if required:
        status = intake_gate.gate(slug)
        if not status['passed']:
            raise auditor.InvalidProject("SOURCE_VERIFICATION_BLOCKED: " + status['reason'])
        approved_identity = intake_gate.snapshot_identity(slug)
    result = auditor.analyze(_directory(slug))
    if required:
        # The checked ledger and the audited ledger must be the *same* snapshot,
        # including user-selected originals. Catch edits between gate and audit.
        if result['digest'] != approved_identity['structured_digest']:
            raise auditor.InvalidProject('SOURCE_VERIFICATION_BLOCKED: audit digest differs from attested ledger')
        final_identity = intake_gate.snapshot_identity(slug)
        if final_identity != approved_identity or not intake_gate.gate(slug)['passed']:
            raise auditor.InvalidProject('SOURCE_VERIFICATION_BLOCKED: originals or structured records changed during audit')
    return result


def scopeledger_audit(args: dict, **kwargs) -> str:
    try:
        slug = args.get("project", "")
        result = _audit(slug)
        storage.receipt(result)
        return _reply({"ok": True, "audit": result})
    except (ValueError, OSError, UnicodeError) as exc:
        return _reply({"ok": False, "error": type(exc).__name__, "message": str(exc)[:240]})
    except Exception as exc:
        return _reply({"ok": False, "error": "InternalError", "message": type(exc).__name__})


def _clean(value):
    """Make arbitrary business text inert in Markdown (including image syntax)."""
    plain = escape(str(value), quote=True).replace("\n", " ").replace("\r", " ").strip()
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", plain)


@contextmanager
def _report_lock(folder):
    """Pin the report directory, then acquire its no-follow regular-file lock."""
    with document_intake.secure_output_directory(folder) as directory_fd:
        flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open('.scopeledger.lock', flags, 0o600, dir_fd=directory_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise auditor.InvalidProject('Unsafe report lock')
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield directory_fd
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _write_snapshot_once(target, text, *, directory_fd=None):
    """Use the shared atomic writer; never reopen a report directory pathname."""
    if directory_fd is None:
        document_intake.write_immutable(target, text)
    else:
        document_intake.write_immutable_at(directory_fd, target.name, text)


def _safe_anchor(value):
    """Use only inert filename characters inside Markdown code spans."""
    return re.sub(r"[^a-zA-Z0-9_./-]", "_", str(value))


def report_markdown(audit):
    # This is a draft only; no claim of legal entitlement or automatic issuance.
    summary = audit["totals"]
    cur = audit["currency"]
    def money(n):
        return f"{cur} {n // 100:,}.{n % 100:02d}"
    out = ["# ScopeLedger | Owner review draft", "",
           f"Client: **{_clean(audit['client'])}**  ",
           f"Project ID: `{_clean(audit['project_id'])}`  ",
           f"Evidence snapshot SHA-256: `{audit['digest']}`", "",
           "**Draft only. No invoice has been sent or authorized.**",
           "Recognized text patterns can corroborate quantities, rates and approvals; they cannot authenticate signers, contract validity or billing rights.",
           "Hermes may share tool outputs with its configured model provider during inference.", "",
           "## Reconciliation snapshot", "",
           f"- Sourced, approved but uninvoiced work for owner review: **{money(summary['ready_minor'])}**",
           f"- Additional work with approval not established: **{money(summary['possible_minor'])}** (not billable as stated)",
           f"- Verified extra work already invoiced in supplied records (disputed invoices excluded): {money(summary['already_invoiced_minor'])}",
           "", "## Findings", "",
           "| Delivery | Service | Extra units | Approved / invoiced | Status | Owner-review amount |",
           "|---|---|---:|---:|---|---:|"]
    for entry in audit["findings"]:
        out.append(f"| {_clean(entry['delivery_id'])} | {_clean(entry['service'])} | {entry['extra_units']} | "
                   f"{entry['approved_extra_units']} / {entry['invoiced_extra_units']} | {entry['status']} | "
                   f"{money(entry['review_ready_minor'])} |")
    out += ["", "## Source anchors (local only)", ""]
    agr = audit["agreement_proof"]
    if agr["matched"]:
        out.append(f"- Agreement: `{_safe_anchor(agr['file'])}:{agr['line']}` (SHA-256 `{agr['sha256'][:16]}…`)")
    else:
        out.append("- Agreement evidence UNVERIFIED")
    for e in audit["findings"]:
        ref = e["evidence"]["delivery"]
        desc = f"`{_safe_anchor(ref['file'])}:{ref['line']}` (SHA-256 `{ref['sha256'][:16]}…`)" if ref["matched"] else "UNVERIFIED"
        term = e["evidence"].get("agreement_terms", {})
        term_state = "terms matched (limited grammar)" if term.get("semantic_verified") else "terms UNVERIFIED"
        out.append(f"- Delivery {_clean(e['delivery_id'])}: {desc}; agreement {term_state}")
        for typ in ("approvals", "invoices"):
            for item in e["evidence"][typ]:
                proof = item["proof"]
                src = f"`{_safe_anchor(proof['file'])}:{proof['line']}` (SHA-256 `{proof['sha256'][:16]}…`)" if proof["matched"] else "UNVERIFIED"
                sem = "terms matched" if proof.get("semantic_verified") else "terms UNVERIFIED"
                out.append(f"  - {typ[:-1].capitalize()} {_clean(item['id'])}: {src}; {sem}")
    out += ["", "## Exceptions requiring human investigation", ""]
    out.extend([f"- {_clean(x)}" for x in audit["errors"] + audit["warnings"]] or ["- None identified by supplied-data checks."])
    out += ["", "## Owner checklist", "", "- [ ] Confirm the agreement and authorized rate with the client.",
            "- [ ] Confirm approval was given by an authorized person and not later rescinded.",
            "- [ ] Verify billability under the agreement and applicable law.",
            "- [ ] Compare against the complete invoicing ledger, not only supplied rows.",
            "- [ ] Only then manually prepare a change request or invoice in your normal system.", ""]
    return "\n".join(out)


def scopeledger_draft(args: dict, **kwargs) -> str:
    try:
        slug = args.get("project", "")
        audit = _audit(slug)
        content = report_markdown(audit)
        html_content = report_view.render(audit)
        reports = storage.data_root() / "reports"
        if reports.is_symlink():
            raise auditor.InvalidProject("Reports folder cannot be a symlink")
        with document_intake.secure_output_directory(reports):
            pass
        target = reports / f"{audit['project_id']}_{audit['digest'][:16]}_v0_3_7_owner-review.md"
        preview = reports / f"{audit['project_id']}_{audit['digest'][:16]}_v0_3_7_owner-review.html"
        with _report_lock(reports) as directory_fd:
            document_intake.check_output_directory(reports, directory_fd)
            _write_snapshot_once(target, content, directory_fd=directory_fd)
            _write_snapshot_once(preview, html_content, directory_fd=directory_fd)
            document_intake.check_output_directory(reports, directory_fd)
        storage.receipt(audit)
        return _reply({"ok": True, "draft_path": str(target), "html_preview_path": str(preview), "snapshot_sha256": audit["digest"],
                       "ready_minor": audit["totals"]["ready_minor"], "possible_minor": audit["totals"]["possible_minor"],
                       "currency": audit["currency"], "warning": "Owner-review draft only; no messages or invoices sent."})
    except (ValueError, OSError, UnicodeError) as exc:
        return _reply({"ok": False, "error": type(exc).__name__, "message": str(exc)[:240]})
    except Exception as exc:
        return _reply({"ok": False, "error": "InternalError", "message": type(exc).__name__})


def scopeledger_document(args: dict, **kwargs) -> str:
    from . import document_intake
    try:
        result = document_intake.inspect(
            args.get('project', ''), args.get('filename', ''), args.get('role', ''),
            source_origin=args.get('source_origin', 'local'),
            drive_file_id=args.get('drive_file_id'), drive_revision=args.get('drive_revision'))
        return _reply(result)
    except (ValueError, OSError, UnicodeError) as exc:
        return _reply({'ok':False,'error':type(exc).__name__,'message':str(exc)[:240]})
    except Exception as exc:
        return _reply({'ok':False,'error':'InternalError','message':type(exc).__name__})
