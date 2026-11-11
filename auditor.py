"""Deterministic, evidence-linked reconciliation; Python stdlib only.

This is an operational *review assistant*, NOT a legal ruling or billing engine.
All amounts are integers in the currency's minor units, never floating point.
Proof matching confirms that user-provided text exists in a local source file;
it does NOT independently prove contractual authorization or legal entitlement.
"""
from __future__ import annotations

import csv
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from . import evidence_semantics

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
CODE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
MAX_SOURCE_BYTES = 128 * 1024
MAX_DATA_BYTES = 512 * 1024
MAX_ITEMS = 1000


class InvalidProject(ValueError):
    pass


def _safe_file(root: Path, name: str, max_bytes: int) -> Path:
    if not isinstance(name, str) or not name or name.startswith(".") or "\\" in name:
        raise InvalidProject("Unsafe or missing source filename")
    if name != Path(name).name:
        raise InvalidProject("Source filename must be a basename")
    candidate = root / name
    if candidate.is_symlink() or root.is_symlink():
        raise InvalidProject("Symlinks are not allowed")
    root_resolved = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    if resolved.parent != root_resolved or not resolved.is_file():
        raise InvalidProject("File escapes configured project directory")
    if resolved.stat().st_size > max_bytes:
        raise InvalidProject("File exceeds maximum supported size")
    return resolved


def _capture_project_inputs(directory: Path) -> dict[str, bytes]:
    """Capture immutable bytes once; analysis must never reopen inputs.

    A final comparison detects persistent edits, but the captured bytes are
    the sole calculation and digest source even during change-and-restore.
    """
    items = {}
    for name in ("project.json", "deliveries.csv", "approvals.csv", "invoices.csv"):
        items[name] = _safe_file(directory, name, MAX_DATA_BYTES).read_bytes()
    source_dir = directory / "sources"
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise InvalidProject('Unsafe or missing sources directory')
    for child in sorted(source_dir.iterdir()):
        if child.is_symlink():
            raise InvalidProject('Symlink in sources directory')
        if child.is_file():
            items['sources/' + child.name] = _safe_file(source_dir, child.name, MAX_SOURCE_BYTES).read_bytes()
    return items


def _frozen_text(frozen: dict[str, bytes], name: str) -> str:
    try:
        return frozen[name].decode('utf-8-sig')
    except KeyError as exc:
        raise InvalidProject('Required source missing from frozen snapshot: ' + name) from exc


def _read_file(root: Path, name: str, cap: int = MAX_DATA_BYTES) -> str:
    return _safe_file(root, name, cap).read_text(encoding="utf-8-sig")


def _source(proj_dir: Path, filename: str, quote: str, frozen=None) -> dict:
    if not isinstance(quote, str) or len(quote.strip()) < 10 or len(quote) > 500:
        return {"matched": False, "reason": "Evidence quote must be 10-500 characters"}
    try:
        content = (_frozen_text(frozen, 'sources/' + filename)
                   if frozen is not None else _read_file(proj_dir / "sources", filename, MAX_SOURCE_BYTES))
    except (OSError, UnicodeError, InvalidProject) as exc:
        return {"matched": False, "reason": f"Source unavailable or unsafe: {type(exc).__name__}"}
    at = content.find(quote.strip())
    if at < 0:
        return {"matched": False, "reason": "Quoted text not found verbatim in source"}
    # Multiple identical excerpts can belong to separate transactions; don't guess.
    if content.find(quote.strip(), at + len(quote.strip())) >= 0:
        return {"matched": False, "reason": "Evidence excerpt occurs more than once"}
    line_number = content.count("\n", 0, at) + 1
    line_text = content.splitlines()[line_number - 1].strip()
    return {"matched": True, "file": "sources/" + filename, "line": line_number,
            "sha256": sha256(content.encode("utf-8")).hexdigest(),
            "line_text": line_text}


def _record_binding(proof: dict, delivery_id: str, quote: str) -> dict:
    """Require source-line identity, not an excerpt borrowed from another record.

    Generated or exported source lines use 'D123 | evidence sentence'.
    Ambiguous free-form lines are not silently assigned to a delivery.
    """
    if not proof.get("matched"):
        return {"record_bound": False, "record_binding_reason": "Source not matched"}
    line = proof.get("line_text", "")
    match = re.match(r"^(D[0-9A-Za-z_-]+)\s*\|\s*(.*)$", line)
    if not match or match.group(1) != delivery_id:
        return {"record_bound": False, "record_binding_reason": "Source line does not identify this delivery"}
    if match.group(2).strip() != quote.strip():
        return {"record_bound": False, "record_binding_reason": "Quoted sentence omits source-line qualifiers or context"}
    return {"record_bound": True, "record_binding_reason": "Source line bound to delivery ID"}


def _reconcile_invoice_sources(frozen, invoice_map, services):
    """Reconcile recognized statements in ALL supplied text, not unseen ledgers.

    Ordinary prose is not an invoice record. A concrete 'Invoice <id> billed'
    claim, however, must have one supported, delivery-bound source occurrence
    and one verified structured mapping. Keep source locations in diagnostics.
    """
    mappings = {}
    for eid, items in invoice_map.items():
        for item in items:
            proof = item['proof']
            if proof.get('matched') and proof.get('record_bound') and proof.get('semantic_verified'):
                mappings.setdefault((proof['file'], proof['line']), []).append((eid, item))
    errors = []
    identities = {}
    for filename, contents in frozen.items():
        if not filename.startswith('sources/'):
            continue
        text = contents.decode('utf-8-sig')
        # Locate claims in the ENTIRE snapshot before assigning locations.
        # INVOICE_CLAIM permits whitespace/newlines between its tokens; a
        # physical line boundary must never hide an already supplied invoice.
        for claim in evidence_semantics.INVOICE_CLAIM.finditer(text):
            start = text.rfind('\n', 0, claim.start()) + 1
            end = text.find('\n', claim.end())
            if end < 0:
                end = len(text)
            number = text.count('\n', 0, start) + 1
            line = text[start:end]
            location = f'{filename}:{number}'
            identity = claim[1]
            # A wrapped/unbound statement without a supported unique CSV
            # anchor is unresolved evidence, never an absent invoice. Normal
            # single-line statements retain their precise source binding.
            bound = re.fullmatch(r'(D[0-9A-Za-z_-]+)\s*\|\s*(.*)', line.strip(), re.S)
            fields = evidence_semantics.invoice_statement(' '.join(bound[2].split())) if bound else None
            if fields is None:
                errors.append(f'Invoice source {location} ({identity}): unsupported or unbound supplied invoice statement')
                continue
            eid = bound[1]
            matched = mappings.get((filename, number), [])
            if (len(matched) != 1 or matched[0][0] != eid or matched[0][1]['units'] != fields['units']
                    or matched[0][1]['proof'].get('invoice_fields') != fields):
                errors.append(f'Invoice source {location} ({identity}, delivery {eid}): no unique verified structured mapping')
            # An external invoice may contain different services. Within one
            # invoice/service, repeated or conflicting claims cannot establish
            # independent lines without richer line-identity evidence.
            codes = [code for code, service in services.items()
                     if fields['service'] in evidence_semantics.variants(service['label'])]
            key = (fields['invoice_id'].casefold(), codes[0] if len(codes) == 1 else fields['service'])
            if key in identities:
                errors.append(f'Invoice source {location} ({identity}): duplicate or inconsistent invoice identity; also at {identities[key]}')
            else:
                identities[key] = location
    return errors


def _rows(directory: Path, name: str, columns: set[str], frozen=None) -> list[dict]:
    data = _frozen_text(frozen, name) if frozen is not None else _read_file(directory, name)
    reader = csv.DictReader(data.splitlines())
    if not reader.fieldnames or set(reader.fieldnames) != columns:
        raise InvalidProject(f"{name}: expected columns {sorted(columns)}")
    records = list(reader)
    if len(records) > MAX_ITEMS:
        raise InvalidProject(f"{name}: exceeds {MAX_ITEMS} rows")
    if any(None in r for r in records):
        raise InvalidProject(f"{name}: malformed CSV row")
    return records


def _source_context_errors(frozen, approvals, invoices, agreement_file):
    """Account for all context in financial-role sources, independent of position.

    Linked source files have explicit roles. Unlinked text containing approval
    or invoice language is also reviewed, including unsupported paid invoices.
    Unrelated source files are not inferred to be financial ledgers.
    """
    roles, mapped = {}, {}
    for role, rows in (('approvals', approvals), ('invoices', invoices)):
        for row in rows:
            name = 'sources/' + row['source_file']
            roles.setdefault(name, set()).add(role)
            mapped.setdefault(name, set()).add(' '.join(
                (row['delivery_id'] + ' | ' + row['source_quote']).casefold().split()))
    errors = []
    for name, contents in frozen.items():
        if not name.startswith('sources/'):
            continue
        text = contents.decode('utf-8-sig')
        source_roles = roles.get(name, set()).copy()
        if re.search(r'\binvoices?\b', text, re.I):
            source_roles.add('invoices')
        if re.search(r'\bapprov(?:e|ed|ing|al|als)\b', text, re.I):
            source_roles.add('approvals')
        if not source_roles:
            continue
        # The agreement has its own whole-body parser. Incidental mentions of
        # invoices/approvals there must not turn its quota clauses into rows.
        if name == agreement_file and name not in roles:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            value = ' '.join(line.casefold().split())
            if not value or value in mapped.get(name, set()):
                continue
            if any(evidence_semantics.source_metadata(line, role) for role in source_roles):
                continue
            prefix = 'Invoice' if 'invoices' in source_roles else 'Approval'
            errors.append(f'{prefix} context {name}:{number}: unsupported/unmapped supplied context (source text withheld from reports)')
    return errors


def _num(value, label: str, allow_zero: bool = True) -> int:
    # Strict numeric parsing: reject decimals, bools, exponents, and negatives.
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,8}", value):
        result = int(value)
    else:
        raise InvalidProject(f"{label}: expected nonnegative integer")
    if result < (0 if allow_zero else 1) or result > 100_000_000:
        raise InvalidProject(f"{label}: out of range")
    return result


def _project_root(projects_root: Path, slug: str) -> Path:
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise InvalidProject("Invalid project slug")
    if projects_root.is_symlink():
        raise InvalidProject("Projects directory cannot be a symlink")
    projects_root.mkdir(parents=True, exist_ok=True)
    if (projects_root / slug).is_symlink():
        raise InvalidProject("Project folder cannot be a symlink")
    folder = (projects_root / slug).resolve(strict=True)
    if folder.parent != projects_root.resolve() or not folder.is_dir():
        raise InvalidProject("Project is outside the projects root")
    return folder


def project_info(directory: Path, frozen=None) -> dict:
    try:
        raw = json.loads(_frozen_text(frozen, 'project.json') if frozen is not None else _read_file(directory, "project.json"))
    except (json.JSONDecodeError, UnicodeError, OSError, InvalidProject) as exc:
        raise InvalidProject("Cannot read project.json: " + str(exc)) from exc
    if not isinstance(raw, dict):
        raise InvalidProject("project.json must be an object")
    for key in ("project_id", "client", "currency", "agreement_source", "services"):
        if key not in raw:
            raise InvalidProject(f"Missing {key}")
    if not isinstance(raw["project_id"], str) or not SLUG.fullmatch(raw["project_id"]):
        raise InvalidProject("Invalid project_id")
    if not isinstance(raw["client"], str) or not raw["client"].strip() or len(raw["client"]) > 120:
        raise InvalidProject("Invalid client")
    if raw["currency"] not in ("USD", "PHP", "EUR", "GBP", "AUD", "CAD", "SGD"):
        raise InvalidProject("Supported two-decimal currencies: USD, PHP, EUR, GBP, AUD, CAD, SGD")
    if not isinstance(raw["agreement_source"], dict):
        raise InvalidProject("agreement_source must contain file and quote")
    services = raw["services"]
    if not isinstance(services, list) or not (1 <= len(services) <= 50):
        raise InvalidProject("services must contain 1-50 lines")
    seen = set()
    for line in services:
        if not isinstance(line, dict) or not CODE.fullmatch(str(line.get("code", ""))):
            raise InvalidProject("Invalid service code")
        if line["code"] in seen:
            raise InvalidProject("Duplicate service code")
        seen.add(line["code"])
        line["included_units"] = _num(line.get("included_units"), "included_units")
        line["extra_unit_price_minor"] = _num(line.get("extra_unit_price_minor"), "extra_unit_price_minor")
        if not isinstance(line.get("label"), str) or not line["label"].strip() or len(line["label"]) > 100:
            raise InvalidProject("Invalid service label")
    return raw


def analyze(directory: Path, *, frozen=None) -> dict:
    """Read a single project and return an auditable, JSON-ready summary."""
    frozen = _capture_project_inputs(directory) if frozen is None else frozen
    project = project_info(directory, frozen=frozen)
    if project["project_id"] != directory.name and directory.name != "northstar":
        raise InvalidProject("project_id and directory name must match")
    agreement = project["agreement_source"]
    agr_proof = _source(directory, agreement.get("file"), agreement.get("quote"), frozen=frozen)
    services = {line["code"]: line for line in project["services"]}
    try:
        agreement_text = _frozen_text(frozen, 'sources/' + agreement.get("file"))
    except (OSError, UnicodeError, InvalidProject):
        agreement_text = ""
    term_proofs = {code: evidence_semantics.contract_terms(agreement_text, line, project["currency"], services=project['services'])
                   if agr_proof["matched"] else {"semantic_verified": False, "semantic_reason": "Agreement anchor unavailable"}
                   for code, line in services.items()}
    agr_proof["semantic_verified"] = all(x["semantic_verified"] for x in term_proofs.values())
    agr_proof["semantic_reason"] = ("All supplied services have parsable rate and included-quantity clauses"
                                    if agr_proof["semantic_verified"] else "One or more service clauses cannot be reconciled")
    delivered = _rows(directory, "deliveries.csv", {"delivery_id", "service_code", "units", "delivered_on", "source_file", "source_quote"}, frozen=frozen)
    approvals = _rows(directory, "approvals.csv", {"approval_id", "delivery_id", "status", "approved_units", "source_file", "source_quote"}, frozen=frozen)
    invoices = _rows(directory, "invoices.csv", {"invoice_line_id", "delivery_id", "invoiced_units", "source_file", "source_quote"}, frozen=frozen)
    errors, warnings, findings = [], [], []
    # Free-form source files can contain revocations that are not represented
    # by one of the narrow CSV schemas. Never ignore such source context just
    # because the positive quote still matches its own line.
    material_reversal_files = []
    for source_name, source_bytes in frozen.items():
        if not source_name.startswith('sources/'):
            continue
        if evidence_semantics.MATERIAL_REVERSAL.search(source_bytes.decode('utf-8-sig')):
            material_reversal_files.append(source_name)
    if not agr_proof["matched"]:
        errors.append("Agreement quote not verified; no amounts can be marked READY_FOR_REVIEW")

    seen_deliveries, parsed_deliveries = set(), []
    for index, row in enumerate(delivered, start=2):
        eid = row["delivery_id"]
        if not eid or eid in seen_deliveries:
            raise InvalidProject(f"deliveries.csv:{index} duplicate/missing delivery_id")
        seen_deliveries.add(eid)
        code = row["service_code"]
        if code not in services:
            raise InvalidProject(f"deliveries.csv:{index} unknown service_code {code}")
        units = _num(row["units"], f"deliveries.csv:{index} units", allow_zero=False)
        try:
            delivered_on = date.fromisoformat(row["delivered_on"])
        except ValueError as exc:
            raise InvalidProject(f"deliveries.csv:{index} invalid date") from exc
        proof = _source(directory, row["source_file"], row["source_quote"], frozen=frozen)
        proof.update(_record_binding(proof, eid, row["source_quote"]))
        proof.update(evidence_semantics.delivery_quote(row["source_quote"], units, services[code], row["delivered_on"]) if proof["matched"] else
                     {"semantic_verified": False, "semantic_reason": "Delivery source not matched"})
        if not proof["matched"] or not proof["semantic_verified"] or not proof["record_bound"]:
            errors.append(f"Delivery {eid}: source evidence or service/quantity verification failed")
        parsed_deliveries.append({"delivery_id": eid, "service_code": code, "units": units,
                                 "delivered_on": delivered_on.isoformat(), "proof": proof})

    approval_map = {i["delivery_id"]: [] for i in parsed_deliveries}
    seen_approvals = set()
    for idx, row in enumerate(approvals, start=2):
        aid, eid = row["approval_id"], row["delivery_id"]
        if not aid or aid in seen_approvals:
            raise InvalidProject(f"approvals.csv:{idx} duplicate/missing approval_id")
        seen_approvals.add(aid)
        if eid not in approval_map:
            errors.append(f"Approval {aid}: unknown delivery reference {eid}")
            continue
        status = row["status"]
        if status not in ("APPROVED", "PENDING", "REJECTED"):
            raise InvalidProject(f"approvals.csv:{idx} unknown status")
        qty = _num(row["approved_units"], f"approvals.csv:{idx} approved_units")
        if status != "APPROVED" and qty:
            raise InvalidProject(f"approvals.csv:{idx} unapproved record has approved_units")
        proof = _source(directory, row["source_file"], row["source_quote"], frozen=frozen)
        proof.update(_record_binding(proof, eid, row["source_quote"]))
        service = services[next(d["service_code"] for d in parsed_deliveries if d["delivery_id"] == eid)]
        proof.update(evidence_semantics.approval_quote(row["source_quote"], status, qty, service, project["currency"],
                                                        service["extra_unit_price_minor"]) if proof["matched"] else
                     {"semantic_verified": False, "semantic_reason": "Approval source not matched"})
        if not proof["matched"] or not proof["semantic_verified"] or not proof["record_bound"]:
            errors.append(f"Approval {aid}: source evidence or authorization terms not verified")
        approval_map[eid].append({"id": aid, "status": status, "units": qty, "proof": proof})

    accounted_denials = {(item['proof'].get('file'), item['proof'].get('line'))
                        for items in approval_map.values() for item in items
                        if item['status'] == 'REJECTED' and item['proof'].get('semantic_verified')
                        and item['proof'].get('record_bound')}
    for name, contents in frozen.items():
        if not name.startswith('sources/'):
            continue
        text = contents.decode('utf-8-sig')
        # Match the captured full text first. A physical newline cannot erase
        # an explicit denial. Only a verified rejection on that entire source
        # line may account for the match; a spanning denial is never exempted.
        for denial in evidence_semantics.APPROVAL_DENIAL.finditer(text):
            number = text.count('\n', 0, denial.start()) + 1
            end = text.find('\n', denial.start())
            if end < 0:
                end = len(text)
            if (name, number) in accounted_denials and denial.end() <= end:
                continue
            if name not in material_reversal_files:
                material_reversal_files.append(name)
    if material_reversal_files:
        errors.append('Possible credit/adjustment/cancellation/revocation or unaccounted denial in: ' + ', '.join(material_reversal_files))

    invoice_map = {i["delivery_id"]: [] for i in parsed_deliveries}
    seen_invoice = set()
    for idx, row in enumerate(invoices, start=2):
        iid, eid = row["invoice_line_id"], row["delivery_id"]
        if not iid or iid in seen_invoice:
            raise InvalidProject(f"invoices.csv:{idx} duplicate/missing invoice_line_id")
        seen_invoice.add(iid)
        if eid not in invoice_map:
            errors.append(f"Invoice {iid}: unknown delivery reference {eid}")
            continue
        qty = _num(row["invoiced_units"], f"invoices.csv:{idx} invoiced_units", allow_zero=False)
        proof = _source(directory, row["source_file"], row["source_quote"], frozen=frozen)
        proof.update(_record_binding(proof, eid, row["source_quote"]))
        service = services[next(d["service_code"] for d in parsed_deliveries if d["delivery_id"] == eid)]
        proof.update(evidence_semantics.invoice_quote(row["source_quote"], qty, service, project["currency"],
                                                       service["extra_unit_price_minor"]) if proof["matched"] else
                     {"semantic_verified": False, "semantic_reason": "Invoice source not matched"})
        if not proof["matched"] or not proof["semantic_verified"] or not proof["record_bound"]:
            errors.append(f"Invoice line {iid}: source evidence or invoice fields not verified")
        invoice_map[eid].append({"id": iid, "units": qty, "proof": proof})

    errors.extend(_reconcile_invoice_sources(frozen, invoice_map, services))
    source_context_errors = _source_context_errors(frozen, approvals, invoices, 'sources/' + agreement['file'])
    errors.extend(source_context_errors)

    # A delivery excerpt reused across delivery IDs is not two independent events.
    anchored_deliveries = {}
    for item in parsed_deliveries:
        proof = item["proof"]
        if not proof["matched"]:
            continue
        key = (proof["file"], proof["line"], proof["sha256"])
        if key in anchored_deliveries:
            proof["semantic_verified"] = False
            anchored_deliveries[key]["semantic_verified"] = False
            errors.append("Delivery evidence anchor reused across records")
        else:
            anchored_deliveries[key] = proof

    # Multiple approvals of the same delivery may just be repeated confirmations.
    # Never add their quantities together without explicit amendment semantics.
    for eid, items in approval_map.items():
        if sum(item["status"] == "APPROVED" for item in items) > 1:
            for item in items:
                item["proof"]["semantic_verified"] = False
            errors.append(f"Delivery {eid}: multiple approvals require owner reconciliation")

    # A single approval/invoice excerpt must not be counted as independent proof
    # for multiple records. Shared approval intent across deliveries requires
    # an explicit owner review rather than duplicate credits.
    for kind, mapping in (("Approval", approval_map), ("Invoice", invoice_map)):
        anchored = {}
        for eid, items in mapping.items():
            for item in items:
                proof = item["proof"]
                if not proof.get("matched"):
                    continue
                key = (proof["file"], proof["line"], proof["sha256"])
                if key in anchored:
                    proof["semantic_verified"] = False
                    anchored[key]["semantic_verified"] = False
                    proof["semantic_reason"] = "Reused source anchor across records"
                    anchored[key]["semantic_reason"] = "Reused source anchor across records"
                    errors.append(f"{kind} {item['id']}: duplicate evidence anchor reused")
                else:
                    anchored[key] = proof

    consumed = {code: 0 for code in services}
    prior_delivery_unverified = {code: False for code in services}
    parsed_deliveries.sort(key=lambda x: (x["delivered_on"], x["delivery_id"]))
    totals = {"ready_minor": 0, "possible_minor": 0, "already_invoiced_minor": 0, "currency": project["currency"]}
    for d in parsed_deliveries:
        eid, code, units = d["delivery_id"], d["service_code"], d["units"]
        line = services[code]
        term_verified = term_proofs[code]["semantic_verified"]
        prior = consumed[code]
        earlier_unverified = prior_delivery_unverified[code]
        if not (d["proof"].get("semantic_verified", False) and d["proof"].get("record_bound", False)):
            prior_delivery_unverified[code] = True
        consumed[code] += units
        extra = max(0, consumed[code] - line["included_units"]) - max(0, prior - line["included_units"])
        if extra == 0:
            if invoice_map[eid]:
                for invoice in invoice_map[eid]:
                    errors.append(f"Invoice {invoice['id']}: extra-work invoice points to included-scope delivery {eid}")
                warnings.append(f"{eid}: invoice marked extra work against included-scope delivery")
                findings.append({
                    "delivery_id": eid, "service": line["label"], "service_code": code,
                    "delivered_units": units, "extra_units": 0, "approved_extra_units": 0,
                    "invoiced_extra_units": sum(x["units"] for x in invoice_map[eid] if x["proof"].get("semantic_verified", False)),
                    "unbilled_approved_units": 0, "unit_rate_minor": line["extra_unit_price_minor"],
                    "potential_minor": 0, "review_ready_minor": 0,
                    "status": "IN_SCOPE_INVOICE_EXCEPTION",
                    "issues": ["Invoice for extra units points to a delivery entirely within contracted scope"],
                    "evidence": {"agreement_terms": term_proofs[code], "delivery": d["proof"], "approvals": approval_map[eid], "invoices": invoice_map[eid]},
                })
            continue
        entries = approval_map[eid]
        valid_approved = sum(a["units"] for a in entries if a["status"] == "APPROVED" and a["proof"].get("semantic_verified", False) and a["proof"].get("record_bound", False))
        unmatched_approval = any(not a["proof"].get("semantic_verified", False) or not a['proof'].get('record_bound', False) for a in entries)
        rejected = any(a["status"] == "REJECTED" for a in entries)
        pending = any(a["status"] == "PENDING" and a["proof"].get("semantic_verified", False) for a in entries)
        verified_billed = sum(b["units"] for b in invoice_map[eid] if b["proof"].get("semantic_verified", False) and b["proof"].get("record_bound", False))
        unmatched_invoice = any(not b["proof"].get("semantic_verified", False) or not b['proof'].get('record_bound', False) for b in invoice_map[eid])
        errors_for_item = []
        if not agr_proof["matched"] or not term_verified:
            errors_for_item.append("Agreement source or service rate/quantity terms not verified")
        if valid_approved > extra:
            errors_for_item.append("Approved units exceed measured extra units")
        if verified_billed > extra:
            errors_for_item.append("Invoiced units exceed measured extra units")
        if verified_billed > valid_approved:
            errors_for_item.append("Invoice quantity exceeds sourced approval quantity")
        if unmatched_approval or unmatched_invoice:
            errors_for_item.append("Approval/invoice evidence could not be matched")
        if not (d["proof"].get("semantic_verified", False) and d["proof"].get("record_bound", False)):
            errors_for_item.append("Delivery service or quantity evidence not verified")
        if earlier_unverified:
            errors_for_item.append("Earlier delivered quantity for this service is not verified")
        # Contracts may require other conditions, such as written authorization,
        # that cannot be proved merely by quote matching.
        can_ready = agr_proof["matched"] and term_verified and not errors_for_item and not rejected
        eligible_unbilled = max(0, min(extra, valid_approved) - verified_billed)
        not_approved = max(0, extra - max(verified_billed, valid_approved))
        if errors_for_item:
            status = "EVIDENCE_OR_BILLING_EXCEPTION"
            warnings.append(f"{eid}: {', '.join(errors_for_item)}")
        elif rejected:
            status = "CLIENT_REJECTED_REVIEW"
        elif eligible_unbilled > 0 and can_ready:
            status = "READY_FOR_OWNER_REVIEW"
            totals["ready_minor"] += eligible_unbilled * line["extra_unit_price_minor"]
        elif verified_billed == extra and extra > 0:
            status = "ALREADY_INVOICED"
        else:
            status = "NEEDS_APPROVAL" if (pending or not_approved > 0) else "REVIEW_REQUIRED"
        if not errors_for_item and not rejected and d["proof"].get("semantic_verified", False) and d["proof"].get("record_bound", False) and agr_proof["matched"] and term_verified:
            totals["possible_minor"] += not_approved * line["extra_unit_price_minor"]
        if not errors_for_item and agr_proof["matched"] and term_verified and not rejected:
            totals["already_invoiced_minor"] += min(extra, verified_billed) * line["extra_unit_price_minor"]
        findings.append({
            "delivery_id": eid, "service": line["label"], "service_code": code,
            "delivered_units": units, "extra_units": extra, "approved_extra_units": valid_approved,
            "invoiced_extra_units": verified_billed,
            "unbilled_approved_units": eligible_unbilled if can_ready else 0,
            "unit_rate_minor": line["extra_unit_price_minor"],
            "potential_minor": extra * line["extra_unit_price_minor"],
            "review_ready_minor": eligible_unbilled * line["extra_unit_price_minor"] if can_ready and status == "READY_FOR_OWNER_REVIEW" else 0,
            "status": status, "issues": errors_for_item,
            "evidence": {"agreement_terms": term_proofs[code], "delivery": d["proof"], "approvals": entries, "invoices": invoice_map[eid]},
        })
    # Supplied but unmapped invoice statements and unresolved references mean
    # this supplied ledger cannot be reconciled. This says nothing about
    # external billing records that were never supplied to ScopeLedger.
    ledger_blockers = [error for error in errors if error.startswith("Invoice ") or
                       error.startswith('Approval context ') or
                       (error.startswith("Approval ") and "unknown delivery reference" in error)]
    ledger_complete = not ledger_blockers
    if not ledger_complete:
        for item in findings:
            if item["status"] == "READY_FOR_OWNER_REVIEW":
                item["status"] = "PROVISIONAL_INCOMPLETE_LEDGER"
                item["issues"].append("Unreconciled supplied invoice evidence or approval/invoice reference")
                item["unbilled_approved_units"] = 0
                item["review_ready_minor"] = 0
        totals["ready_minor"] = 0
        warnings.append("Project-level owner-review total withheld: unreconciled supplied invoice evidence or approval/invoice references")
    if material_reversal_files:
        # This is a potential contradiction, not an automated legal ruling.
        # Retain evidence for review but withhold every project-level candidate.
        for item in findings:
            if item['status'] == 'READY_FOR_OWNER_REVIEW':
                item['status'] = 'MATERIAL_CONTEXT_REVIEW_REQUIRED'
                item['issues'].append('Possible reversal of underlying billing authorization')
                item['unbilled_approved_units'] = 0
                item['review_ready_minor'] = 0
        totals['ready_minor'] = 0
        totals['possible_minor'] = 0
        warnings.append('Candidate amounts withheld pending cancellation/revocation review')
    if not findings:
        warnings.append("No out-of-scope deliveries found in supplied records")
    # Digest the very bytes used to compute this financial result, not a
    # second read that could differ after a transient file replacement.
    if _capture_project_inputs(directory) != frozen:
        raise InvalidProject('Input files changed during audit; retry with a stable snapshot')
    content_parts = [name.encode() + b"\0" + body for name, body in frozen.items()]
    digest = sha256(b"\x1f".join(content_parts)).hexdigest()
    return {"project_id": project["project_id"], "client": project["client"],
            "engine_version": "0.3.7", "digest": digest, "currency": project["currency"], "agreement_proof": agr_proof,
            "findings": findings, "totals": totals, "ledger_complete": ledger_complete,
            "source_context_complete": not source_context_errors and not material_reversal_files,
            "errors": errors, "warnings": warnings,
            "disclaimer": "Recognized text patterns and hashes corroborate supplied fields but cannot authenticate signers, contract validity, full ledger completeness or billing rights; human review required."}
