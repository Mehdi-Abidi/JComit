import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import llm, statement, websearch
from .categorize import categorize, default_redactor
from .memory import Memory
from .skills import review_month

MAX_ROWS = 400


def run_agent(csv_text: str, corrections: dict[str, str] | None = None, ask=None, lookup=None,
              use_web: bool = True) -> dict:
    txns = statement.parse(csv_text)
    if not txns:
        raise ValueError("the statement has no rows")
    if len(txns) > MAX_ROWS:
        raise ValueError(f"the statement has {len(txns)} rows; the limit is {MAX_ROWS}")

    usage = {"calls": 0, "tokens": 0}

    def tracked(prompt, system=None):
        text, used = llm.complete(prompt, system)
        usage["calls"] += 1
        usage["tokens"] += used.get("total_tokens", 0)
        return text

    ask = ask or tracked
    if lookup is None and use_web and websearch.available():
        lookup = websearch.search

    start = time.perf_counter()
    redact = default_redactor(txns)
    for t in txns:
        redact(" ".join([t.description, t.account_holder, t.account_number, t.card_last4]))

    with tempfile.TemporaryDirectory() as folder:
        memory = Memory(Path(folder) / "memory.db")
        for description, category in (corrections or {}).items():
            memory.correct(description, category)
        result = categorize(txns, memory=memory, redact=redact, ask=ask, lookup=lookup)

    month = max(t.date for t in txns).strftime("%Y-%m")
    review = None if result.blocked else review_month(txns, result.items, month, ask)

    return {
        "ran_at": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "seconds": round(time.perf_counter() - start, 1),
        "model": llm.model() if ask is tracked else "test",
        "rows": len(txns),
        "month": month,
        "hidden": len(redact.mapping),
        "decided_by": dict(Counter(i.source for i in result.items)),
        "sent": result.sent,
        "searched": result.searched,
        "web": lookup is not None,
        "blocked": result.blocked,
        "usage": usage,
        "review": review,
        "items": [
            {"date": i.txn.date.isoformat(), "description": i.txn.description, "amount": i.txn.amount,
             "category": i.category, "source": i.source}
            for i in result.items
        ],
    }
