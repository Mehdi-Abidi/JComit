"""Agent skills that run inside the OpenShell sandbox.

Each skill declares the network access it needs. policy.py turns those
declarations into the sandbox policy, so a skill can only reach what it
declared and the user approved. Every run is written to data/actions.jsonl.

  python -m jcomit.skills list
  python -m jcomit.skills categorize data/statement.csv
  python -m jcomit.skills monthly_review data/statement.csv --month 2026-09
  python -m jcomit.skills share_report
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import guard, statement
from .categorize import categorize, default_redactor
from .memory import Memory

TOKEN_FACTORY = "api.tokenfactory.nebius.com"
SHARE_URL = os.environ.get("JCOMIT_SHARE_URL", "https://example.com/upload")


@dataclass(frozen=True)
class Access:
    host: str
    method: str
    path: str


@dataclass(frozen=True)
class Skill:
    name: str
    summary: str
    network: tuple[Access, ...]
    approved: bool  # included in the default policy
    run: Callable[[argparse.Namespace], dict]


def data_dir() -> Path:
    return Path(os.environ.get("JCOMIT_DATA", "data"))


def log_action(skill: str, action: str, result: str, **detail) -> None:
    entry = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "skill", "skill": skill, "action": action, "result": result, **detail,
    }
    data_dir().mkdir(parents=True, exist_ok=True)
    with open(data_dir() / "actions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _load(files: list[str]) -> list[statement.Transaction]:
    return statement.load(*files) if files else statement.load(data_dir() / "statement.csv")


def _write(name: str, payload: dict) -> Path:
    path = data_dir() / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


# --- categorize ---------------------------------------------------------------

def run_categorize(args) -> dict:
    txns = _load(args.files)
    result = categorize(txns, memory=Memory(data_dir() / "memory.db"), redact=default_redactor(txns))
    sources = Counter(i.source for i in result.items)
    _write("categorized.json", {
        "items": [
            {"date": i.txn.date, "description": i.txn.description, "amount": i.txn.amount,
             "category": i.category, "source": i.source}
            for i in result.items
        ],
        "sent_to_model": result.sent,
        "blocked": result.blocked,
    })
    log_action("categorize", f"sorted {len(txns)} transactions", "blocked" if result.blocked else "ok",
               decided_by=dict(sources), sent_to_model=len(result.sent))
    return {"transactions": len(txns), "decided_by": dict(sources), "blocked": result.blocked}


# --- monthly_review -----------------------------------------------------------

REVIEW_SYSTEM = (
    "You write a short, friendly monthly money review for one person. Use only the numbers "
    "given. At most 5 sentences, plain English, no headings. Mention the biggest spending "
    "category, any subscriptions, and any alerts worth checking."
)


def _finders():
    try:
        from .finders import find_alerts, find_subscriptions
    except ImportError:
        return None
    return find_subscriptions, find_alerts


def run_monthly_review(args, ask=None) -> dict:
    txns = _load(args.files)
    month = args.month or max(t.date for t in txns).strftime("%Y-%m")
    result = categorize(txns, memory=Memory(data_dir() / "memory.db"), redact=default_redactor(txns))
    in_month = [i for i in result.items if i.txn.date.strftime("%Y-%m") == month]

    spend = Counter()
    for i in in_month:
        if i.txn.amount < 0 and i.category != "Transfers":
            spend[i.category] += round(-i.txn.amount, 2)
    income = round(sum(i.txn.amount for i in in_month if i.txn.amount > 0), 2)

    finders = _finders()
    subs = alerts = None
    if finders:
        subs, alerts = finders[0](txns), finders[1](txns)

    facts = {
        "month": month,
        "income": income,
        "spending_total": round(sum(spend.values()), 2),
        "spending_by_category": {k: round(v, 2) for k, v in spend.most_common()},
        "subscriptions": [{"merchant": s["description"], "amount": s["amount"]} for s in subs or []],
        "alerts": [{"type": a["type"], "merchant": a["description"], "amount": a["amount"], "date": a["date"]}
                   for a in alerts or []],
    }
    if not finders:
        facts["note"] = "subscription and alert finders not installed yet"

    prompt = json.dumps(facts, indent=1)
    guard.check(prompt, guard.patterns(txns))
    if ask is None:
        from .llm import chat as ask
    review = ask(prompt, system=REVIEW_SYSTEM)

    out = {**facts, "review": review}
    _write(f"review_{month}.json", out)
    _write("review_latest.json", out)
    log_action("monthly_review", f"wrote review for {month}", "ok", finders=bool(finders))
    return out


# --- share_report -------------------------------------------------------------

def run_share_report(args) -> dict:
    """Send the latest review to an outside server. Not approved by default, so the sandbox blocks it."""
    path = data_dir() / "review_latest.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"note": "no review yet"}
    body = json.dumps({k: report.get(k) for k in ("month", "spending_total", "spending_by_category")}).encode()
    req = urllib.request.Request(args.url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            outcome, detail = "sent", f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        outcome, detail = "sent", f"server answered HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        outcome, detail = "blocked", str(getattr(e, "reason", e))
    log_action("share_report", f"upload report to {args.url}", outcome, detail=detail)
    return {"url": args.url, "result": outcome, "detail": detail}


SKILLS = {s.name: s for s in [
    Skill("categorize", "Sort transactions into spending categories (Nemotron for unknown shops).",
          (Access(TOKEN_FACTORY, "POST", "/v1/chat/completions"),), True, run_categorize),
    Skill("monthly_review", "Summarise one month: spending, subscriptions, alerts, and a short review.",
          (Access(TOKEN_FACTORY, "POST", "/v1/chat/completions"),), True, run_monthly_review),
    Skill("share_report", "Upload the monthly report to an outside server.",
          (Access(urllib.parse.urlsplit(SHARE_URL).hostname, "POST", urllib.parse.urlsplit(SHARE_URL).path or "/"),),
          False, run_share_report),
]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jcomit.skills")
    sub = p.add_subparsers(dest="skill", required=True)
    sub.add_parser("list", help="show skills and the access each one declares")
    for name in ("categorize", "monthly_review"):
        s = sub.add_parser(name, help=SKILLS[name].summary)
        s.add_argument("files", nargs="*")
        if name == "monthly_review":
            s.add_argument("--month", help="YYYY-MM, default: latest month in the data")
    s = sub.add_parser("share_report", help=SKILLS["share_report"].summary)
    s.add_argument("--url", default=SHARE_URL)
    args = p.parse_args(argv)

    if args.skill == "list":
        for s in SKILLS.values():
            access = ", ".join(f"{a.method} {a.host}{a.path}" for a in s.network)
            print(f"{s.name:<15} {'approved' if s.approved else 'NOT approved':<13} {access}\n  {s.summary}")
        return 0

    out = SKILLS[args.skill].run(args)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("result") != "blocked" else 3


if __name__ == "__main__":
    sys.exit(main())
