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


def load(*paths: str | Path) -> list[Transaction]:
    txns = []
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                txns.append(Transaction(
                    date=date.fromisoformat(r["date"]),
                    description=r["description"].strip(),
                    amount=float(r["amount"]),
                    account_number=r["account_number"].strip(),
                    card_last4=r["card_last4"].strip(),
                    account_holder=r["account_holder"].strip(),
                ))
    return sorted(txns, key=lambda t: t.date)
