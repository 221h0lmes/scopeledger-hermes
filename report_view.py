"""Script-free HTML report generator. Escape every value read from business files."""
from html import escape

CSS = """
:root{--ink:#152b37;--muted:#667984;--border:#dce5e6;--bg:#f4f8f6;--teal:#127968}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:system-ui,Arial,sans-serif;color:var(--ink)}
.wrap{max-width:1080px;margin:40px auto;padding:0 24px 60px}.head{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap}
.eyebrow{text-transform:uppercase;letter-spacing:.13em;font-size:11px;font-weight:800;color:var(--teal)}
h1{font-size:clamp(36px,6vw,61px);letter-spacing:-.05em;line-height:1.05;margin:8px 0}h2{font-size:21px;letter-spacing:-.03em;margin:26px 0 12px}
p{color:var(--muted);line-height:1.5}.chip{background:#e5f6eb;border:1px solid #b0dbca;color:#176a54;padding:9px 12px;border-radius:100px;font-size:12px;font-weight:800}
.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:27px 0}.metric,.panel{background:#fff;border:1px solid var(--border);border-radius:15px;padding:22px}
.value{font-size:clamp(24px,3vw,35px);letter-spacing:-.04em;font-weight:850;margin:10px 0}.sub{font-size:13px;color:var(--muted);line-height:1.4}
.panel{overflow:auto;margin-bottom:14px}table{min-width:610px;width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em}
th,td{padding:15px 10px;border-bottom:1px solid var(--border);vertical-align:middle}td span{display:block;font-size:12px;color:var(--muted);margin-top:5px}
.money{font-weight:800;white-space:nowrap}.status{border-radius:6px;font-size:10px;white-space:nowrap;padding:7px 9px}.green{background:#d7f5e5;color:#076642}.gold{background:#fff0c8;color:#8e6108}.red{background:#ffe5de;color:#923c25}
.alert{background:#fff4d9;border-left:4px solid #d3a43e;border-radius:7px;padding:14px 17px;margin-top:22px;font-size:13px;line-height:1.5;color:#6a4e22}
.proof{color:#355b73;font:12px ui-monospace,monospace}.proof small{color:#7e9098}.unverified{color:#b33227;font-weight:750}.nested{margin:5px 0 3px 23px;color:var(--muted)}
li{margin:10px 0;overflow-wrap:anywhere}.foot{color:var(--muted);font-size:11px;word-break:break-all;margin-top:30px}
@media(max-width:700px){.metrics{grid-template-columns:1fr}.wrap{margin:20px auto}}@media print{body{background:white}.wrap{margin:0 auto}.metric,.panel{break-inside:avoid}}
"""


def render(audit):
    def h(x):
        return escape(str(x), quote=True)
    def money(n):
        return f"{h(audit['currency'])} {n//100:,}.{n%100:02d}"
    def proof(p):
        if not p.get("matched"):
            return '<strong class="unverified">SOURCE NOT FOUND</strong>'
        label = ' · TERMS MATCHED (LIMITED FORMAT)' if p.get('semantic_verified', True) else ' · TERMS NOT VERIFIED'
        return (f'<span class="proof">{h(p["file"])}:{p["line"]} '
                f'<small>sha256:{h(p["sha256"][:12])}…{h(label)}</small></span>')

    rows = []
    evidence = [f'<li>Agreement: {proof(audit["agreement_proof"])}</li>']
    for x in audit["findings"]:
        tone = "green" if x["status"] == "READY_FOR_OWNER_REVIEW" else ("gold" if x["status"] == "NEEDS_APPROVAL" else "red")
        rows.append(f'<tr><td><b>{h(x["delivery_id"])}</b><span>{h(x["service"])}</span></td><td>{x["extra_units"]}</td>'
                    f'<td>{x["approved_extra_units"]} / {x["invoiced_extra_units"]}</td>'
                    f'<td><b class="status {tone}">{h(x["status"].replace("_"," "))}</b></td>'
                    f'<td class="money">{money(x["review_ready_minor"])}</td></tr>')
        subproofs = []
        for kind in ("approvals", "invoices"):
            for item in x["evidence"][kind]:
                subproofs.append(f'<div class="nested">{h(kind[:-1])} {h(item["id"])}: {proof(item["proof"])}</div>')
        term = x["evidence"].get("agreement_terms", {})
        term_note = 'Recognized terms matched' if term.get('semantic_verified') else 'Terms not verified: ' + term.get('semantic_reason', 'unknown')
        evidence.append(f'<li>{h(x["delivery_id"])}: {proof(x["evidence"]["delivery"])}'
                        f'<div class="nested">Service agreement: {h(term_note)}</div>' + "".join(subproofs) + '</li>')
    checks = [*audit["errors"], *audit["warnings"]]
    if not audit.get("ledger_complete", True):
        checks.insert(0, "Unresolved approval or invoice reference: project-level ready total withheld")
    checks_html = "".join(f'<li>{h(c)}</li>' for c in checks) or '<li>No additional processing errors; business review is still required.</li>'
    t = audit["totals"]
    metrics = [
        ("Approved, not fully invoiced", money(t["ready_minor"]), "Ready for owner review, not automatic invoicing"),
        ("Approval unverified", money(t["possible_minor"]), "Potential scope change, not yet billable"),
        ("Reconciled invoiced extras", money(t["already_invoiced_minor"]), "Excludes disputed or unmatched invoice lines"),
    ]
    cards = "".join(f'<div class="metric"><div class="eyebrow">{h(title)}</div><div class="value">{value}</div><div class="sub">{h(note)}</div></div>' for title, value, note in metrics)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>ScopeLedger | {h(audit["client"])}</title><style>{CSS}</style></head><body><main class="wrap">'
            f'<header class="head"><div><div class="eyebrow">ScopeLedger / Owner review</div><h1>Found work.<br>Not guesswork.</h1>'
            f'<p>Project <b>{h(audit["project_id"])}</b> for {h(audit["client"])}.<br>One evidence-linked operational snapshot.</p></div>'
            f'<div class="chip">LOCAL DATA · NO AUTO-BILLING</div></header>'
            '<div class="alert"><b>Draft, not a claim for payment.</b> A matched quote confirms only that an excerpt occurs in a local file. '
            'The owner must verify contractual authority, invoices, and approval before billing. The active Hermes model provider may process these tool outputs.</div>'
            f'<section class="metrics">{cards}</section><h2>Exceptions and opportunities</h2><div class="panel"><table><thead>'
            '<tr><th>Delivery</th><th>Extra units</th><th>Approved / billed</th><th>Classification</th><th>Review amount</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<h2>Evidence anchors</h2><div class="panel"><ul>{"".join(evidence)}</ul></div>'
            f'<h2>Items requiring investigation</h2><div class="panel"><ul>{checks_html}</ul></div>'
            '<h2>Owner checklist</h2><div class="panel"><ul>'
            '<li>Confirm actual executed contract and prices.</li><li>Check all approvals came from authorized client representatives.</li>'
            '<li>Compare against the full invoice ledger.</li><li>Only then manually authorize a change request or invoice.</li></ul></div>'
            f'<footer class="foot">Input snapshot SHA-256: {h(audit["digest"])} · Locally stored report · No plugin-originated network calls. Model provider may receive tool outputs.</footer>'
            '</main></body></html>')
