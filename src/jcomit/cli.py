"""JComit command line.

  python -m jcomit.cli categorize data/statement.csv [--no-ai] [--show-sent]
  python -m jcomit.cli correct "STARBUCKS #1234 AUSTIN TX" "Dining"
  python -m jcomit.cli forget "STARBUCKS #1234 AUSTIN TX"
  python -m jcomit.cli memory
"""

import argparse
import sys
from collections import Counter

from . import statement
from .categorize import CATEGORIES, categorize, default_redactor
from .memory import DEFAULT_PATH, Memory


def cmd_categorize(args, memory: Memory) -> int:
    txns = statement.load(*args.files)
    redact = None if args.no_ai else default_redactor()
    if not args.no_ai and redact is None:
        print("Note: redact.py is not available, so nothing is sent to Nemotron (fail closed).\n")
    result = categorize(txns, memory=memory, redact=redact, use_ai=not args.no_ai)

    width = max(len(it.txn.description) for it in result.items)
    for it in result.items:
        print(f"{it.txn.date}  {it.txn.description:<{width}}  {it.txn.amount:>9.2f}  {it.category:<13} {it.source}")

    spend = Counter()
    for it in result.items:
        if it.txn.amount < 0:
            spend[it.category] += -it.txn.amount
    print("\nSpending by category:")
    for cat, total in spend.most_common():
        print(f"  {cat:<13} {total:>10.2f}")
    print("\nDecided by:", dict(Counter(it.source for it in result.items)))

    if args.show_sent and result.sent:
        print("\nSent to Nemotron (after redaction):")
        for s in result.sent:
            print(f"  {s['original']:<{width}}  ->  {s['redacted']}")
    if result.blocked:
        print(f"\nBLOCKED: {result.blocked}")
        return 2
    return 0


def cmd_correct(args, memory: Memory) -> int:
    if args.category not in CATEGORIES:
        print(f"Unknown category. Pick one of: {', '.join(CATEGORIES)}")
        return 1
    key = memory.correct(args.description, args.category)
    print(f"Remembered: {key} -> {args.category}")
    return 0


def cmd_forget(args, memory: Memory) -> int:
    print("Forgotten." if memory.forget(args.description) else "Nothing saved for that merchant.")
    return 0


def cmd_memory(args, memory: Memory) -> int:
    rows = memory.all()
    if not rows:
        print("No corrections saved yet.")
    for merchant, category, example, updated in rows:
        print(f"{merchant:<25} {category:<13} (e.g. {example}, saved {updated})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jcomit")
    p.add_argument("--memory", default=str(DEFAULT_PATH), help="path to memory.db")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("categorize", help="sort a statement into categories")
    c.add_argument("files", nargs="+")
    c.add_argument("--no-ai", action="store_true", help="memory and rules only")
    c.add_argument("--show-sent", action="store_true", help="print exactly what the model received")
    c.set_defaults(func=cmd_categorize)

    c = sub.add_parser("correct", help="remember a category for a merchant")
    c.add_argument("description")
    c.add_argument("category")
    c.set_defaults(func=cmd_correct)

    c = sub.add_parser("forget", help="drop a saved correction")
    c.add_argument("description")
    c.set_defaults(func=cmd_forget)

    sub.add_parser("memory", help="list saved corrections").set_defaults(func=cmd_memory)

    args = p.parse_args(argv)
    return args.func(args, Memory(args.memory))


if __name__ == "__main__":
    sys.exit(main())
