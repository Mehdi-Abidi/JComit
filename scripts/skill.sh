#!/usr/bin/env bash
# Run a JComit skill inside the sandbox, e.g.
#   scripts/skill.sh list
#   scripts/skill.sh categorize
#   scripts/skill.sh monthly_review --month 2026-09
#   scripts/skill.sh share_report
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
exec openshell sandbox exec -n "${NAME:-jcomit}" --no-tty -- \
  env PYTHONPATH=/app/src python3 -m jcomit.skills "$@"
