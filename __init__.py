"""ScopeLedger native Hermes plugin registration. No side effects at import/registration."""
from pathlib import Path
from . import schemas, tools


def register(ctx):
    ctx.register_tool(name="scopeledger_projects", toolset="scopeledger", schema=schemas.PROJECTS, handler=tools.scopeledger_projects)
    ctx.register_tool(name="scopeledger_audit", toolset="scopeledger", schema=schemas.AUDIT, handler=tools.scopeledger_audit)
    ctx.register_tool(name="scopeledger_draft", toolset="scopeledger", schema=schemas.DRAFT, handler=tools.scopeledger_draft)

    ctx.register_tool(name="scopeledger_document", toolset="scopeledger", schema=schemas.DOCUMENT, handler=tools.scopeledger_document)

    # Optional workflow guide; core reconciliation never depends on a prompt.
    ctx.register_skill("scopeledger", Path(__file__).parent / "skills" / "scopeledger" / "SKILL.md")

    if hasattr(ctx, "register_automation_blueprint"):
        ctx.register_automation_blueprint(
            "scope-check", title="ScopeLedger weekly financial checkpoint",
            description="Run a sourced, human-reviewed project reconciliation each week.",
            category="work", schedule_template="{minute} {hour} * * 1",
            prompt_template="Use ScopeLedger tools to list the configured project and audit {project}. Check document evidence status. Do not call undocumented tools, issue invoices or contact clients. If source intake is incomplete, report BLOCKED rather than a billable total.",
            slots=[{"name":"project","type":"text","label":"Project slug","default":"demo"},
                   {"name":"time","type":"time","label":"Local time","default":"09:00"}],
            skills=["scopeledger"], tags=["billing","review"])
