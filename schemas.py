"""Native Hermes tool schemas: specific descriptions encourage safe, useful selection."""
PROJECTS = {
    "name": "scopeledger_projects",
    "description": "List projects available to ScopeLedger. Read-only. Use before auditing a client project. The synthetic 'demo' project is always available.",
    "parameters": {"type": "object", "properties": {}},
}
AUDIT = {
    "name": "scopeledger_audit",
    "description": (
        "Audit agency project scope versus deliveries, approvals and invoices, with "
        "source-file evidence. Returns verified record matches, ambiguous work, amounts, "
        "and exceptions. No invoices or messages are sent. Use project='demo' first. "
        "Do not describe unapproved or unmatched work as legally billable."
    ),
    "parameters": {"type": "object", "properties": {
        "project": {"type": "string", "description": "Project slug returned by scopeledger_projects; use demo for the built-in fictional example."}
    }, "required": ["project"]},
}
DRAFT = {
    "name": "scopeledger_draft",
    "description": (
        "Create a local owner-review Markdown change-request draft from a read-only "
        "scope audit. No emails, payments, invoices, or external communications occur. "
        "Includes links to on-disk source filenames and cautions about unverifiable evidence."
    ),
    "parameters": {"type": "object", "properties": {
        "project": {"type": "string", "description": "Project slug; 'demo' is synthetic."}
    }, "required": ["project"]},
}

DOCUMENT = {
    "name": "scopeledger_document",
    "description": "Inspect one user-staged PDF/DOCX under ScopeLedger's bounded project inbox. Checks page coverage and numeric tokens; saves immutable extracted text and provenance. Does NOT auto-approve source or invoice lines. Use only after explicit Drive/file access consent.",
    "parameters": {"type":"object", "properties": {
        "project":{"type":"string"},
        "filename":{"type":"string"},
        "role":{"type":"string","enum":["agreement","deliveries","approvals","invoices"]},
        "source_origin":{"type":"string","enum":["local","drive-selected-export"]},
        "drive_file_id":{"type":"string"},
        "drive_revision":{"type":"string"}
    },"required":["project","filename","role"]}
}
