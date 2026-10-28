#!/usr/bin/env bash
# Check every sandbox rule from inside the sandbox. RUNS=10 repeats the blocked upload.
set -uo pipefail
NAME="${NAME:-jcomit}"
RUNS="${RUNS:-10}"
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."
fail=0

run() { openshell sandbox exec -n "$NAME" --no-tty -- sh -c "$1" >/dev/null 2>&1; }
expect() {  # expect <allow|deny> <label> <command>
  if run "$3"; then got=allow; else got=deny; fi
  if [ "$got" = "$1" ]; then echo "[ok]   $1  $2"; else echo "[FAIL] expected $1, got $got: $2"; fail=1; fi
}

expect allow "write inside /sandbox/data"           "touch /sandbox/data/.probe && rm /sandbox/data/.probe"
expect deny  "write to home outside data/"          "touch /sandbox/.probe"
expect deny  "change the code in /app"              "touch /app/src/jcomit/.probe"
expect deny  "write to /etc"                        "touch /etc/.probe"
expect allow "python -> Token Factory models"       "PYTHONPATH=/app/src python3 -c 'from jcomit import llm; llm.models()'"
expect deny  "curl -> Token Factory (wrong program)" "curl -sf -m 15 https://api.tokenfactory.nebius.com/v1/models"
expect allow "python -> Tavily search"              "python3 -c 'import urllib.request as u, urllib.error as e
try: u.urlopen(u.Request(\"https://api.tavily.com/search\", data=b\"{}\", method=\"POST\"), timeout=15)
except e.HTTPError: pass'"
expect deny  "curl -> Tavily (wrong program)"       "[ \"\$(curl -s -o /dev/null -w '%{http_code}' -m 15 -X POST https://api.tavily.com/search)\" != 000 ]"
expect deny  "python -> webhook.site"               "python3 -c \"import urllib.request as u; u.urlopen('https://webhook.site/', timeout=15)\""

blocked=0
for i in $(seq 1 "$RUNS"); do
  out="$(scripts/skill.sh share_report 2>/dev/null || true)"
  echo "$out" | grep -q '"result": "blocked"' && blocked=$((blocked + 1))
done
echo "share_report blocked $blocked/$RUNS times"
[ "$blocked" -eq "$RUNS" ] || fail=1

[ "$fail" -eq 0 ] && echo "PASS" || echo "FAIL"
exit "$fail"
