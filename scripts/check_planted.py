"""Check a fake statement against docs/planted_items.md.

Usage: python scripts/check_planted.py data/statement.csv

Checks that every planted item is present, and that the data has no
accidental extra subscriptions or large card charges.
"""

import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

EXPECTED = Path(__file__).resolve().parent.parent / "tests" / "expected_findings.json"
COLUMNS = ["date", "description", "amount", "account_number", "card_last4", "account_holder"]


def load(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f"FAIL: missing columns {missing}")
        rows = list(reader)
    for r in rows:
        r["date"] = date.fromisoformat(r["date"].strip())
        r["amount"] = round(float(r["amount"]), 2)
        r["description"] = r["description"].strip()
        r["is_card"] = bool(r["card_last4"].strip())
    return rows


def has(rows, desc, amount, day):
    return sum(1 for r in rows if r["description"] == desc and r["amount"] == amount and r["date"] == day)


def main(path):
    rows = load(path)
    exp = json.loads(EXPECTED.read_text())
    problems = []

    if not 120 <= len(rows) <= 180:
        problems.append(f"{len(rows)} rows (aim for about 150)")
    if min(r["date"] for r in rows) < date(2026, 7, 1) or max(r["date"] for r in rows) > date(2026, 9, 30):
        problems.append("dates outside 2026-07-01..2026-09-30")

    for s in exp["subscriptions"]:
        for d in s["dates"]:
            if has(rows, s["description"], s["amount"], date.fromisoformat(d)) != 1:
                problems.append(f"{s['id']} missing or duplicated on {d}")
    for a in exp["alerts"]:
        n = has(rows, a["description"], a["amount"], date.fromisoformat(a["date"]))
        if n != a.get("count", 1):
            problems.append(f"{a['id']} found {n} times, expected {a.get('count', 1)}")
    sep26 = [r for r in rows if r["date"] == date(2026, 9, 26)]
    if not any(r["description"] == "FOREIGN TRANSACTION FEE" and not r["is_card"] for r in sep26):
        problems.append("FOREIGN TRANSACTION FEE row (no card) missing on 2026-09-26")
    if not any(r["description"].startswith("STARBUCKS") for r in sep26):
        problems.append("Starbucks row missing on 2026-09-26 (shows she was in Austin)")
    for must in ("ZELLE TO OMAR KHAN", "ZELLE FROM HINA RAZA", "TRANSFER TO SAVINGS ACCT 4421 9987 0012", "SQ *BLUE DOOR LLC"):
        if not any(r["description"] == must for r in rows):
            problems.append(f"missing row: {must}")

    # Rule F1: no unplanned fixed monthly card charges.
    planted = {(s["description"], s["amount"]) for s in exp["subscriptions"]}
    groups = defaultdict(list)
    for r in rows:
        if r["is_card"] and r["amount"] < 0:
            groups[(r["description"], r["amount"])].append(r["date"])
    for key, days in groups.items():
        months = {(d.year, d.month) for d in days}
        if len(months) >= 3 and key not in planted:
            problems.append(f"looks like an extra subscription: {key[0]} {key[1]}")

    # Rule F2: no other card purchase over $400.
    large = {a["description"] for a in exp["alerts"] if a["type"] in ("large", "new_abroad")}
    for r in rows:
        if r["is_card"] and r["amount"] < -400 and r["description"] not in large:
            problems.append(f"unplanned large card charge: {r['description']} {r['amount']}")

    # Decoys that the demo depends on.
    sbux = [r["amount"] for r in rows if r["description"].startswith("STARBUCKS")]
    if not 9 <= len(sbux) <= 12:
        problems.append(f"{len(sbux)} Starbucks rows (need 9 to 12)")
    if len(set(sbux)) != len(sbux):
        problems.append("Starbucks amounts repeat (every amount must differ)")
    if any(r["is_card"] for r in rows if r["description"].startswith(("ONLINE TRANSFER", "PAYROLL", "ZELLE"))):
        problems.append("transfers/salary/Zelle rows must have an empty card_last4")

    card = [-r["amount"] for r in rows if r["is_card"] and r["amount"] < 0]
    print(f"{len(rows)} rows, {len(card)} card purchases, median card purchase ${statistics.median(card):.2f}")
    if problems:
        print("FAIL:")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS: all planted items present, no accidental extras.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
