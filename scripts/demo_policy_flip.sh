#!/usr/bin/env bash
# Demo: the same upload flips from blocked to allowed and back with one policy change.
set -euo pipefail
NAME="${NAME:-jcomit}"
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."

base="$(mktemp)"; open="$(mktemp)"
PYTHONPATH=src python3 -m jcomit.policy -o "$base"
PYTHONPATH=src python3 -m jcomit.policy --allow share_report -o "$open"

step() { printf '\n=== %s\n' "$1"; }
share() { scripts/skill.sh share_report | grep -E '"result"|"detail"' || true; }

step "1. Default policy: share_report is not approved"
openshell policy set "$NAME" --policy "$base" --wait >/dev/null
share

step "2. Approve share_report. The policy change:"
diff "$base" "$open" | grep '^>' | sed 's/^> /  + /' || true
openshell policy set "$NAME" --policy "$open" --wait >/dev/null
share

step "3. Remove the approval again"
openshell policy set "$NAME" --policy "$base" --wait >/dev/null
share
