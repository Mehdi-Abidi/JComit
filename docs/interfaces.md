# How the pieces connect

Everything lives in `src/jcomit/`. Run tests with `python -m pytest`. Use only the Python standard library inside `src/jcomit/` so the code runs in the OpenShell sandbox, where pip is blocked.

## Shared: transactions (`statement.py`, done)

```python
from jcomit import statement
txns = statement.load("data/statement.csv")   # list[Transaction], sorted by date
t.date (datetime.date), t.description, t.amount (negative = money out),
t.account_number, t.card_last4, t.account_holder
```

## Ali: `redact.py`

The categorizer calls it before anything goes to Nemotron. Until it exists, nothing is sent (fail closed).

```python
from jcomit.redact import Redactor
r = Redactor()
r.redact("ZELLE TO OMAR KHAN")   # -> "ZELLE TO [NAME_2]"
r.mapping                         # {"[NAME_2]": "Omar Khan", ...}, never leaves the machine
```

- Same value, same label, every call (one `Redactor` per run).
- `redact()` returns a `str`. Returning `(text, mapping)` also works.
- Labels and traps: [docs/private_details.md](private_details.md).

`guard.py` (Mehdi) is a second check after redaction. It refuses to send a payload that still holds the holder name, account number or card number, so a missed value is blocked instead of leaked.

## Mufeed: `finders.py`

```python
from jcomit.finders import find_subscriptions, find_alerts
find_subscriptions(txns) -> list[dict]   # {"description", "amount", "dates": ["2026-07-03", ...]}
find_alerts(txns)        -> list[dict]   # {"type": "large"|"double"|"new_abroad", "description", "amount", "date"}
```

Must match `tests/expected_findings.json` exactly. Plain Python, no model calls.

## Mehdi: `categorize.py` + `memory.py` (done)

```python
from jcomit.categorize import categorize, default_redactor
from jcomit.memory import Memory
result = categorize(txns, memory=Memory(), redact=default_redactor())
result.items    # list[Item]: .txn, .category, .source ("memory" | "rule" | "nemotron" | "unreviewed" | "blocked")
result.sent     # [{"original", "redacted"}], exactly what Nemotron received (for the raw vs redacted panel)
result.blocked  # message if the guard stopped a payload, else None

Memory().correct("SQ *BLUE DOOR LLC", "Dining")   # saved in data/memory.db, survives restarts
```

Command line: `python -m jcomit.cli categorize data/statement.csv --show-sent`, `python -m jcomit.cli correct "<description>" <Category>`, `python -m jcomit.cli memory`.

## Mehdi: skills, policy and action log (Day 3, done)

Skills run inside the sandbox and write their outputs to `data/`:

| Skill | Output in `data/` | Network it declares |
|---|---|---|
| `categorize` | `categorized.json`: items + `sent_to_model` (raw vs redacted) | Token Factory |
| `monthly_review` | `review_<month>.json`, `review_latest.json`: totals, subscriptions, alerts, Nemotron's review | Token Factory |
| `share_report` | nothing; the "bad" upload, not approved by default | example.com |

Every run appends to `data/actions.jsonl`. `python -m jcomit.actionlog -o data/action_log.json` merges that with OpenShell's allowed/denied decisions into one list sorted by time. Each event has `time`, `source` ("skill" or "sandbox"), `result` ("ok", "sent", "blocked", "allowed", "denied"), and then `skill`/`action`/`detail` or `program`/`target`/`policy`/`reason`. A real one: [sample_action_log.json](sample_action_log.json).

## Taha: the Streamlit page

Call the functions above; don't reimplement them. The three panels map to:

1. Raw vs redacted: `categorized.json` → `sent_to_model` (and `Redactor` on the full statement)
2. Results: `categorized.json` → `items`, `review_latest.json` (totals, subscriptions, alerts, review text)
3. Action log: `action_log.json`. Build against [sample_action_log.json](sample_action_log.json) until the page runs next to the sandbox. Colour `denied`/`blocked` red and `allowed`/`sent`/`ok` green.
