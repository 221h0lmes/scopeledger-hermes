"""Conservative, deterministic checks for limited English-language business evidence.

A source-text substring is an anchor, not semantic verification. These checks only
recognize explicitly worded, single-service unit-price statements; anything else
is unverified and requires human review. This is NOT general contract NLP.
"""
from __future__ import annotations
import re

NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
                "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
N = r"(?:[0-9]{1,6}|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
M = r"(?:\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?)(?![.,]\d)"


def number(value):
    v = value.casefold()
    return NUMBER_WORDS.get(v, int(v) if v.isascii() and v.isdecimal() else None)


def price_minor(value):
    txt = value.replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", txt):
        return None
    whole, _, fraction = txt.partition(".")
    return int(whole) * 100 + int(fraction.ljust(2, "0") or "0")


def variants(label):
    label = " ".join(label.lower().split())
    labels = {label}
    # A narrow, non-generative alias for 'web banner' in the demo data.
    if label.startswith("web "):
        labels.add(label[4:])
    def plural(s):
        return s[:-1] + "ies" if s.endswith("y") and len(s) > 1 and s[-2] not in "aeiou" else s + ("s" if not s.endswith("s") else "es")
    return {t for s in labels for t in (s, plural(s))}


def _label_ok(candidate, label):
    return " ".join(candidate.lower().split()) in variants(label)


def _result(ok, reason):
    return {"semantic_verified": bool(ok), "semantic_reason": reason}


# If source material contains possible supersession or reversal, a positive
# price/approval excerpt cannot on its own establish current billing rights.
# Conservative by design: false positives request human reconciliation.
MATERIAL_REVERSAL = re.compile(
    r"\b(?:revok(?:e|ed|es|ing|ation)|rescind(?:ed|s|ing)?|"
    r"cancel(?:led|ed|lation|ation|s)?|void(?:ed)?|"
    r"terminat(?:e|ed|es|ion)|supersed(?:e|ed|es)|"
    r"withdraw(?:n|al)?|waiv(?:e|ed|er)|"
    r"credits?|refunds?|discounts?|tax(?:es)?|offsets?|"
    r"no\s+longer\s+approved|do\s+not\s+bill|"
    r"not\s+chargeable|cannot\s+(?:bill|invoice)|"
    r"no\s+additional\s+work\s+is\s+chargeable|"
    r"never\s+(?:been\s+)?(?:delivered|completed)|"
    r"(?:not|were\s+not|was\s+not)\s+(?:actually\s+)?(?:delivered|completed)|"
    r"\bforecast(?:ed)?\b)\b", re.I)

# A recognized, identity-bound REJECTED row can account for a denial. Other
# denials in source context must not be discarded just because they lack digits.
APPROVAL_DENIAL = re.compile(r'\b(?:(?:do\s+not|not)\s+approv(?:e|ed)|approval\s+denied|reject(?:ed|ion)?)\b', re.I)


def source_metadata(text, role):
    """Recognize only complete supported headings/administrative notes.

    Source membership, lack of digits and position before a record are NEVER
    evidence that a line is metadata. Unknown financial-role context blocks.
    """
    value = ' '.join(text.casefold().split())
    headings = {'approvals': {'fictional client correspondence'},
                'invoices': {'fictional invoice export'}, 'deliveries': set()}
    if value in headings.get(role, set()):
        return True
    if re.fullmatch(r'fictional agency [a-z0-9][a-z0-9_.-]*\.txt source notes', value):
        return True
    if role == 'deliveries' and re.fullmatch(r"[A-Za-z][A-Za-z0-9 &'_-]* work ledger", text.strip()):
        return True
    # Explicit, bounded administrative prose contains no financial assertion.
    # Additional text, arbitrary qualifiers or other prose do not inherit this
    # exemption. It applies at any source/document position.
    if role == 'invoices' and re.fullmatch(
            r'invoice questions may be discussed at (?:the|a) (?:next )?(?:team|owner|project) meeting\.', value):
        return True
    return bool(re.fullmatch(r'this export includes a fictional demonstration for the (?:owner|reviewer)\.', value))


# Supported prologue metadata is syntactic, limited to a SOW title/date or
# the bundled demonstration's title-case parties declaration. Arbitrary prose
# is never silently classified as a heading or a harmless contract clause.
_AGREEMENT_TITLE = re.compile(
    r'(?:Agency )?Statement of Work(?: \(fictional\))?'
    r'(?:, [A-Za-z]+ [0-9]{1,2}, [0-9]{4})?', re.I)
_PARTY_NAME = r"[A-Z][A-Za-z0-9&'-]*(?: [A-Z][A-Za-z0-9&'-]*){0,5}"
_DEMO_PARTIES = re.compile(rf'{_PARTY_NAME} and {_PARTY_NAME} \(fictional demonstration\)')
_GENERIC_QUOTA = re.compile(rf'{N}\s+(?P<service>[A-Za-z][A-Za-z -]*?)\s+(?:are\s+)?included\s*\.?', re.I)
_GENERIC_RATE = re.compile(
    rf'(?:additional|each\s+subsequent)\s+(?P<service>[A-Za-z][A-Za-z -]*?)\s*:\s*'
    rf'[A-Z]{{3}}\s+{M}(?:\s+each)?\s*\.?', re.I)
_APPROVAL_REQUIREMENT = re.compile(
    r'Written approvals? required before (?:additional work is invoiced|billing)\.?', re.I)


def _agreement_clauses(source_text, services):
    """Keep all body context; line wrapping is whitespace, not a clause boundary.

    This is a closed supported grammar, not legal-language understanding.
    Unrecognized body prose (including a condition in its own sentence) is a
    blocker. Only explicit standalone formatting and supported prologue
    metadata can be omitted before parsing the complete body.
    """
    body = []
    for line in source_text.splitlines():
        value = ' '.join(line.split())
        if not value or re.fullmatch(r'\[(?:PAGE (?:[0-9]+|DOCX BODY)|DOCX BODY)\]', value, re.I):
            continue
        if not body and (_AGREEMENT_TITLE.fullmatch(value) or _DEMO_PARTIES.fullmatch(value)):
            continue
        body.append(value)
    text = ' '.join(body)
    # Decimal points have no following whitespace and remain inside numbers.
    clauses = [part.strip() for part in re.split(r'(?<=[.!?])\s+', text) if part.strip()]
    known_labels = {label for service in services for label in variants(service['label'])}
    if not clauses:
        return None
    for clause in clauses:
        if _APPROVAL_REQUIREMENT.fullmatch(clause):
            continue
        match = _GENERIC_QUOTA.fullmatch(clause) or _GENERIC_RATE.fullmatch(clause)
        if not match or match['service'].casefold() not in known_labels:
            return None
    return clauses


def contract_terms(source_text, service, currency, *, services=None):
    """Require supported complete agreement context and unique same-service terms."""
    if MATERIAL_REVERSAL.search(source_text):
        return _result(False, "Possible cancellation, revocation or superseding terms require human review")
    clauses = _agreement_clauses(source_text, services if services is not None else [service])
    if clauses is None:
        return _result(False, 'Unsupported agreement context or qualified/negated/fractional terms require review')
    names = "|".join(re.escape(x) for x in sorted(variants(service['label']), key=len, reverse=True))
    included = []
    rates = []
    for clause in clauses:
        quota = re.fullmatch(rf'({N})\s+({names})\s+(?:are\s+)?included\s*\.?', clause, re.I)
        if quota:
            included.append(quota.groups())
        rate = re.fullmatch(
            rf'(?:additional\s+({names})|each\s+subsequent\s+({names}))'
            rf'\s*:\s*([A-Z]{{3}})\s+({M})(?:\s+each)?\s*\.?', clause, re.I)
        if rate:
            rates.append(rate.groups())
    if len(included) != 1 or len(rates) != 1:
        return _result(False, "Expected exactly one unambiguous included-quantity and extra-unit-price clause for this service")
    n = number(included[0][0]); rate = price_minor(rates[0][3]); cur = rates[0][2].upper()
    if n != service["included_units"] or rate != service["extra_unit_price_minor"] or cur != currency:
        return _result(False, "Included quantity, unit price or currency contradicts source agreement text")
    return _result(True, "Parsed included quantity and unit rate match supported agreement context; human contractual verification still required")


def approval_quote(quote, status, units, service, currency, expected_rate):
    text = quote.strip()
    m = re.fullmatch(rf"I approve (?:the )?({N})\s+(?:additional|extra)\s+(.+?)\s+at\s+([A-Z]{{3}})\s+({M})(?:\s+each)?\s*\. ?", text, flags=re.I)
    if status == "APPROVED":
        if not m:
            return _result(False, "Approval status is not supported by a recognized affirmative authorization sentence")
        if not _label_ok(m[2], service["label"]) or number(m[1]) != units or m[3].upper() != currency or price_minor(m[4]) != expected_rate:
            return _result(False, "Approval service, quantity, rate or currency conflicts with the source quotation")
        return _result(True, "Explicit source quotation matches this service, authorized units and unit rate; approver authority unverified")
    if status == "PENDING":
        # Do not infer a pending decision from a keyword buried in a longer
        # statement. The complete source sentence must concern THIS service.
        pending = re.fullmatch(
            r"(?:Please\s+send\s+pricing|Send\s+a\s+quote)\s+for\s+"
            r"(?:the\s+)?(?:extra|additional)\s+(?P<request>[A-Za-z][A-Za-z -]*?)"
            r"(?:\s+first)?\."
            r"|(?:Awaiting\s+approval|Approval\s+pending)\s+for\s+"
            r"(?:the\s+)?(?:extra|additional)\s+(?P<awaiting>[A-Za-z][A-Za-z -]*?)\.",
            text, flags=re.I)
        if not pending or not _label_ok(pending['request'] or pending['awaiting'], service['label']):
            return _result(False, "Pending approval requires one complete supported sentence for this service")
        return _result(True, "Source indicates approval pending for this service; authority remains unverified")
    if status == "REJECTED":
        # A rejected row can discharge exactly ONE explicit denial of THIS
        # service, never every denial on the same source line. Validate the
        # complete utterance, not a pair of unrelated substrings.
        rejection = re.fullmatch(
            r"(?:I\s+(?:do\s+not\s+approve|reject)|Approval\s+denied\s+for)"
            r"\s+(?:(?:the|any)\s+)?(?:(?:additional|extra)\s+)?"
            r"(?P<service>[A-Za-z][A-Za-z -]*?)\s*\.",
            text, flags=re.I)
        if rejection is not None and _label_ok(rejection['service'], service['label']):
            return _result(True, "One complete source rejection matches this service; identity and authority still require review")
        return _result(False, "Rejection must be a single complete, service-specific supported statement")
    return _result(False, "Unknown approval status")


INVOICE_CLAIM = re.compile(r'\bInvoice\s+(\S+)\s+billed\b', re.I)


def invoice_statement(quote):
    """Parse supplied statement fields, retaining the external invoice identity."""
    m = re.fullmatch(rf"Invoice\s+(\S+)\s+billed\s+({N})\s+(?:additional|extra)\s+(.+?)\s+at\s+([A-Z]{{3}})\s+({M})(?:\s+each)?\s*\.", quote.strip(), flags=re.I)
    if not m:
        return None
    return {'invoice_id': m[1], 'units': number(m[2]), 'service': ' '.join(m[3].casefold().split()),
            'currency': m[4].upper(), 'rate_minor': price_minor(m[5])}


def invoice_quote(quote, qty, service, currency, expected_rate):
    m = invoice_statement(quote)
    if not m:
        return _result(False, "Invoice quote uses an unsupported or ambiguous format")
    if m['units'] != qty or not _label_ok(m['service'], service["label"]) or m['currency'] != currency or m['rate_minor'] != expected_rate:
        return _result(False, "Invoice quantity, service, currency or price contradicts sourced invoice text")
    return {**_result(True, "Invoice quote matches supplied line fields; completeness of external ledger unverified"),
            'invoice_fields': m}


def delivery_quote(quote, qty, service, delivered_on=None):
    """Recognize one COMPLETE delivered/completed claim with a concrete date.

    The date is deliberately bounded to an ISO date or full English month and
    day. A quote containing a correction, forecast, contingency or second
    sentence is not verified. Never treat an arbitrary trailing phrase as a
    delivery date. CSV dates are cross-checked when provided by the auditor.
    """
    from calendar import month_name
    from datetime import date

    months = '|'.join(month_name[1:])
    text = quote.strip()
    m = re.fullmatch(
        rf"(?:Delivered|Completed)\s+({N})\s+"
        rf"(?:original\s+|additional\s+|included\s+|third\s+|second\s+|first\s+)*"
        rf"(.+?)\s+on\s+(?:(\d{{4}}-\d{{2}}-\d{{2}})|({months})\s+([1-9]|[12][0-9]|3[01]))\.",
        text, flags=re.I)
    if not m or number(m[1]) != qty or not _label_ok(m[2], service['label']):
        return _result(False, "Delivery must be one supported, complete quantity/service/date statement")
    try:
        if m[3]:
            statement_date = date.fromisoformat(m[3])
        else:
            month = next(n for n, label in enumerate(month_name) if label.casefold() == m[4].casefold())
            # The original English statements omit the year, so the
            # structured ledger supplies it. Without one, check date shape.
            year = date.fromisoformat(delivered_on).year if delivered_on else 2000
            statement_date = date(year, month, int(m[5]))
        if delivered_on and statement_date != date.fromisoformat(delivered_on):
            return _result(False, "Delivery date contradicts the structured delivery date")
    except (ValueError, StopIteration, TypeError):
        return _result(False, "Delivery date is invalid or unsupported")
    return _result(True, "Complete delivery statement matches supported service, quantity and date; independent delivery proof not established")
