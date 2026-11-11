#!/usr/bin/env bash
# Explicitly stage ONLY the four checked-in synthetic originals for a local test.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/.hermes/plugin-data/scopeledger"
PROJECT="$DEST/projects/northstar"
INBOX="$DEST/inbox/northstar"
mkdir -p "$PROJECT" "$INBOX"
copy_only_if_unmodified(){
  from="$1"; to="$2"
  if [[ -e "$to" ]] && ! cmp -s "$from" "$to"; then
    echo "BLOCKED: existing source differs, no overwrite: $to" >&2;return 1
  fi
  if [[ ! -e "$to" ]]; then cp "$from" "$to";fi
}
while IFS= read -r -d '' file; do
  rel="${file#"$ROOT/examples/northstar/"}"
  mkdir -p "$PROJECT/$(dirname "$rel")"
  copy_only_if_unmodified "$file" "$PROJECT/$rel"
done < <(find "$ROOT/examples/northstar" -type f -print0)
for name in northstar_agreement.docx northstar_approvals.docx northstar_deliveries.pdf northstar_invoices.pdf; do
  copy_only_if_unmodified "$ROOT/tests/fixtures/$name" "$INBOX/$name"
done
echo 'PASS: synthetic Northstar source docs and structured project staged without overwriting existing files.'
echo 'Hermes: Inspect northstar_agreement.docx (agreement), northstar_approvals.docx (approvals),'
echo 'northstar_deliveries.pdf (deliveries), and northstar_invoices.pdf (invoices)'
echo 'with scopeledger_document for project northstar. Do not approve automatically.'
