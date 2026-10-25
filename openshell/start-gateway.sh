#!/usr/bin/env bash
# Codespaces has no systemd; this mirrors nemoclaw-openshell-gateway.service.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
export STATE_DIRECTORY="$HOME/.local/state/openshell/gateway"
export OPENSHELL_LOCAL_TLS_DIR="$HOME/.local/state/openshell/tls"
mkdir -p "$STATE_DIRECTORY" "$OPENSHELL_LOCAL_TLS_DIR"
[ -f "$HOME/.config/openshell/gateway.env" ] && set -a && . "$HOME/.config/openshell/gateway.env" && set +a
pgrep -f "^openshell-gateway$" >/dev/null && { echo "gateway already running"; exit 0; }
umask 0077
openshell-gateway generate-certs --output-dir "$OPENSHELL_LOCAL_TLS_DIR" --server-san host.openshell.internal
cd "$STATE_DIRECTORY"
setsid nohup openshell-gateway > "$HOME/openshell-gateway.log" 2>&1 < /dev/null &
echo "gateway started pid $!"
