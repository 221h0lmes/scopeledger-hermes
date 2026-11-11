#!/usr/bin/env python3
"""No Hermes or network required: use real plugin handlers and bundled fictional data."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parent = str(ROOT.parent)
sys.path.insert(0, parent)
spec = importlib.util.spec_from_file_location("scopeledger", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

with tempfile.TemporaryDirectory(prefix="scopeledger_demo_") as tmp:
    os.environ["SCOPELEDGER_DATA_HOME"] = tmp
    from scopeledger import tools
    outcome = json.loads(tools.scopeledger_audit({"project": "demo"}))
    if not outcome["ok"]:
        raise SystemExit(outcome)
    audit = outcome["audit"]
    print("ScopeLedger (fictional agency demo)")
    print("Agreement evidence matched:", audit["agreement_proof"]["matched"])
    print("Project:", audit["client"])
    print("Owner review amount (USD):", f"{audit['totals']['ready_minor']/100:,.2f}")
    print("Unapproved possible work (USD):", f"{audit['totals']['possible_minor']/100:,.2f}")
    for x in audit["findings"]:
        print(f"  {x['delivery_id']} {x['status']}: {x['service']} extra={x['extra_units']} review_minor={x['review_ready_minor']}")
    draft = json.loads(tools.scopeledger_draft({"project": "demo"}))
    print("Draft created:", draft["ok"])
    if not draft["ok"]:
        raise SystemExit(draft)
