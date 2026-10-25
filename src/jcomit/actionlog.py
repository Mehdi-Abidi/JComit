"""One timeline of what the agent did and what the sandbox allowed or denied.

Two sources: the skills' own log (data/actions.jsonl, written inside the
sandbox) and OpenShell's network decisions (`openshell logs`). Runs on the
host, next to the openshell CLI.

  python -m jcomit.actionlog --sandbox jcomit -o data/action_log.json
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
DECISION = re.compile(
    r"^\[(?P<ts>\d+(?:\.\d+)?)\] \[sandbox\] \[OCSF\s*\] \[ocsf\] "
    r"(?P<kind>NET:OPEN|HTTP:[A-Z]+) \[\w+\] (?P<decision>ALLOWED|DENIED) (?P<rest>.*)$"
)
NET_TARGET = re.compile(r"^(?P<binary>\S+?)(?:\(\d+\))? -> (?P<target>\S+)")
HTTP_TARGET = re.compile(r"^(?P<method>[A-Z]+) (?P<url>\S+)")
BRACKETS = re.compile(r"\[(\w+:[^\]]*)\]")


def _tags(text: str) -> dict[str, str]:
    """'[policy:x engine:opa] [reason:not allowed by any policy]' -> {policy, engine, reason}."""
    tags = {}
    for body in BRACKETS.findall(text):
        if body.startswith("reason:"):
            tags["reason"] = body[len("reason:"):]
        else:
            tags.update(part.split(":", 1) for part in body.split() if ":" in part)
    return tags


def parse_openshell(lines) -> list[dict]:
    events = []
    for raw in lines:
        m = DECISION.match(ANSI.sub("", raw).strip())
        if not m:
            continue
        rest = m["rest"]
        tags = _tags(rest)
        event = {
            "time": datetime.fromtimestamp(float(m["ts"]), timezone.utc).isoformat(timespec="seconds"),
            "source": "sandbox",
            "result": m["decision"].lower(),
            "policy": None if tags.get("policy") in (None, "-") else tags["policy"],
        }
        if m["kind"] == "NET:OPEN" and (t := NET_TARGET.match(rest)):
            event.update(kind="connect", program=Path(t["binary"]).name, target=t["target"])
        elif t := HTTP_TARGET.match(rest):
            url = re.sub(r"^https?://", "", t["url"]).replace(":443", "")
            event.update(kind="request", target=f"{t['method']} {url}")
        else:
            event.update(kind=m["kind"].lower(), target=rest.split(" [")[0])
        if "reason" in tags:
            event["reason"] = tags["reason"]
        events.append(event)
    return events


def parse_skills(lines) -> list[dict]:
    return [json.loads(line) for line in lines if line.strip()]


def timeline(*sources: list[dict]) -> list[dict]:
    return sorted((e for s in sources for e in s), key=lambda e: e["time"])


def fetch(sandbox: str, since: str) -> list[dict]:
    logs = subprocess.run(
        ["openshell", "logs", sandbox, "--since", since, "-n", "5000"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["openshell", "sandbox", "download", sandbox, "/sandbox/data/actions.jsonl", tmp],
            capture_output=True, text=True,
        )
        path = Path(tmp) / "actions.jsonl"
        skills = parse_skills(path.read_text(encoding="utf-8").splitlines()) if path.exists() else []
    return timeline(parse_openshell(logs), skills)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jcomit.actionlog")
    p.add_argument("--sandbox", default="jcomit")
    p.add_argument("--since", default="2h")
    p.add_argument("-o", "--output")
    args = p.parse_args(argv)

    events = fetch(args.sandbox, args.since)
    for e in events:
        who = e.get("skill") or e.get("program") or ""
        what = e.get("action") or e.get("target") or ""
        why = e.get("reason") or e.get("detail") or e.get("policy") or ""
        print(f"{e['time']}  {e['result'].upper():<8} {e['source']:<8} {who:<15} {what}  {why}")
    if args.output:
        Path(args.output).write_text(json.dumps(events, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
