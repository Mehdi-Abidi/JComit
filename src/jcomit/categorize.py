"""Sort transactions into spending categories.

Order: the user's saved corrections (memory), then simple rules, then Nemotron
for whatever is left. Only redacted text reaches the model, and the guard
refuses to send anything that still holds a private value.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from . import guard
from .memory import Memory, merchant_key
from .statement import Transaction

CATEGORIES = (
    "Housing", "Income", "Groceries", "Dining", "Transport", "Shopping", "Entertainment",
    "Health", "Fitness", "Travel", "Bills", "Fees", "Transfers", "Other",
)

# First match wins, so specific patterns go before general ones.
RULES = [(re.compile(p), c) for p, c in [
    (r"PAYROLL|DIRECT DEP", "Income"),
    (r"LANDLORD|\bRENT\b", "Housing"),
    (r"ZELLE|VENMO|TRANSFER TO SAVINGS", "Transfers"),
    (r"UBER\s*\*?\s*EATS|DOORDASH|GRUBHUB|STARBUCKS|CHIPOTLE|\bCAFE\b|COFFEE|PIZZA|TACOS", "Dining"),
    (r"\bUBER\b|\bLYFT\b|SHELL OIL|EXXON|CHEVRON", "Transport"),
    (r"\bHEB\b|WHOLEFDS|WHOLE FOODS|TRADER JOE|COSTCO|KROGER", "Groceries"),
    (r"NETFLIX|SPOTIFY|HULU|DISNEY\+|AMC THEATRES", "Entertainment"),
    (r"\bGYM\b", "Fitness"),
    (r"CVS|WALGREENS|PHARMACY", "Health"),
    (r"AMZN|AMAZON|TARGET|BESTBUY|BEST BUY", "Shopping"),
    (r"\bAIR\b|AIRLINES|HOTEL|AIRBNB", "Travel"),
    (r"ENERGY|ELECTRIC|AT&T|VERIZON|COMCAST|WATER UTIL", "Bills"),
]]

SYSTEM = (
    "You sort bank transactions into spending categories. Each input line is "
    "'id. description | amount' where a negative amount is money going out. Private details were "
    "replaced with labels like [NAME_1]; ignore them. Answer with JSON only, an object mapping every "
    'id to exactly one category, for example {"1": "Dining"}. Allowed categories: '
    + ", ".join(CATEGORIES) + ". Use Other when unsure."
)

Redact = Callable[[str], str]
Ask = Callable[..., str]


@dataclass
class Item:
    txn: Transaction
    category: str
    source: str  # memory | rule | nemotron | unreviewed | blocked


@dataclass
class Result:
    items: list[Item]
    sent: list[dict] = field(default_factory=list)  # {"original", "redacted"}, what the model saw
    blocked: str | None = None


def rule_category(description: str) -> str | None:
    d = description.upper()
    return next((c for p, c in RULES if p.search(d)), None)


def default_redactor() -> Redact | None:
    """Ali's redact.py, if it is there. Without it, nothing is sent to the model."""
    try:
        from .redact import Redactor
    except ImportError:
        return None
    r = Redactor()

    def redact(text: str) -> str:
        out = r.redact(text)
        return out[0] if isinstance(out, tuple) else out

    return redact


def parse_answer(text: str, ids: list[str]) -> dict[str, str]:
    """Pull the JSON object out of the reply and keep only known ids and categories."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        raw = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    lookup = {c.lower(): c for c in CATEGORIES}
    return {
        str(k): lookup.get(str(v).strip().lower(), "Other")
        for k, v in raw.items() if str(k) in ids
    }


def categorize(
    txns: list[Transaction],
    memory: Memory | None = None,
    redact: Redact | None = None,
    ask: Ask | None = None,
    use_ai: bool = True,
    batch_size: int = 40,
) -> Result:
    items: list[Item | None] = []
    pending: dict[str, list[int]] = {}  # merchant key -> item positions

    for i, t in enumerate(txns):
        if memory and (cat := memory.lookup(t.description)):
            items.append(Item(t, cat, "memory"))
        elif cat := rule_category(t.description):
            items.append(Item(t, cat, "rule"))
        else:
            items.append(None)
            pending.setdefault(merchant_key(t.description), []).append(i)

    result = Result(items=[])
    if pending and use_ai and redact:
        if ask is None:
            from .llm import chat as ask
        private = guard.patterns(txns)
        groups = list(pending.values())
        for start in range(0, len(groups), batch_size):
            batch = groups[start:start + batch_size]
            ids = [str(start + n + 1) for n in range(len(batch))]
            lines = []
            for gid, positions in zip(ids, batch):
                t = txns[positions[0]]
                red = redact(t.description)
                result.sent.append({"original": t.description, "redacted": red})
                lines.append(f"{gid}. {red} | {t.amount:+.2f}")
            prompt = "\n".join(lines)
            try:
                guard.check(prompt, private)
            except guard.LeakError as e:
                result.blocked = str(e)
                break
            answer = parse_answer(ask(prompt, system=SYSTEM), ids)
            for gid, positions in zip(ids, batch):
                for p in positions:
                    items[p] = Item(txns[p], answer.get(gid, "Other"), "nemotron")

    source = "blocked" if result.blocked else "unreviewed"
    result.items = [it or Item(txns[i], "Other", source) for i, it in enumerate(items)]
    return result
