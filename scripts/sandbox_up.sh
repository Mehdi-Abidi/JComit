#!/usr/bin/env bash
# (Re)build the JComit OpenShell sandbox:
#   code baked in read-only at /app, policy generated from the skills,
#   model key attached as a provider, fake data uploaded to /sandbox/data.
# Rebuilding wipes the sandbox's data/ (including memory.db). To restart
# without losing memory, use: openshell sandbox stop jcomit && openshell sandbox start jcomit
set -euo pipefail
NAME="${NAME:-jcomit}"
PROVIDERS="${PROVIDERS:-nebius}"
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."

bash openshell/start-gateway.sh

ctx="$(mktemp -d)"
cp -r src "$ctx/src"
find "$ctx" -name __pycache__ -prune -exec rm -rf {} +
cp openshell/sandbox.Dockerfile "$ctx/Dockerfile"
PYTHONPATH=src python3 -m jcomit.policy -o "$ctx/policy.yaml"

openshell sandbox delete "$NAME" >/dev/null 2>&1 || true
provider_flags=()
for p in $PROVIDERS; do provider_flags+=(--provider "$p"); done
openshell sandbox create --name "$NAME" --from "$ctx" --policy "$ctx/policy.yaml" "${provider_flags[@]}" --detach

for _ in $(seq 1 60); do
  openshell sandbox list 2>/dev/null | grep -qE "^$NAME .*Ready" && break
  sleep 5
done

# Statements and receipts only; never upload a local memory.db.
seed="$(mktemp -d)/data"
mkdir -p "$seed"
cp data/*.csv "$seed/"
cp -r data/receipts "$seed/" 2>/dev/null || true
openshell sandbox upload "$NAME" "$seed" /sandbox
echo "Sandbox $NAME ready."
