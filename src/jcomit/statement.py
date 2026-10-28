"""Load bank statement CSVs into transactions.

Columns: date, description, amount, account_number, card_last4, account_holder
"""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Transaction:
    date: date
    description: str
    amount: float
    account_number: str
    card_last4: str
    account_holder: str


COLUMNS = ("date", "description", "amount", "account_number", "card_last4", "account_holder")


def _rows(lines) -> list[Transaction]:
    reader = csv.DictReader(lines)
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    return [
        Transaction(
            date=date.fromisoformat(r["date"].strip()),
            description=r["description"].strip(),
            amount=float(r["amount"]),
            account_number=(r["account_number"] or "").strip(),
            card_last4=(r["card_last4"] or "").strip(),
            account_holder=(r["account_holder"] or "").strip(),
        )
        for r in reader
    ]


def load(*paths: str | Path) -> list[Transaction]:
    txns = []
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            txns.extend(_rows(f))
    return sorted(txns, key=lambda t: t.date)


def parse(text: str) -> list[Transaction]:
    return sorted(_rows(text.splitlines()), key=lambda t: t.date)
