"""Last check before anything reaches the model.

Redaction (redact.py) does the real work. This guard is a second, independent
line: it knows the private values from the statement's own columns and refuses
to send any payload that still contains one. It fails closed.
"""

import re
from collections.abc import Iterable

from .statement import Transaction


class LeakError(RuntimeError):
    """A payload still contained a private value and was not sent."""


def _digits_pattern(value: str) -> str:
    # "4421 9987" also matches "44219987", "4421-9987" and "4421  9987".
    digits = re.sub(r"\D", "", value)
    return r"(?<!\d)" + r"[\s-]*".join(digits) + r"(?!\d)"


def _name_pattern(value: str) -> str:
    return r"\b" + r"[\s-]+".join(map(re.escape, value.split())) + r"\b"


def patterns(txns: Iterable[Transaction]) -> list[re.Pattern]:
    names, numbers = set(), set()
    for t in txns:
        if t.account_holder:
            names.add(t.account_holder)
        for v in (t.account_number, t.card_last4):
            if re.sub(r"\D", "", v):
                numbers.add(v)
    return (
        [re.compile(_name_pattern(n), re.IGNORECASE) for n in sorted(names)]
        + [re.compile(_digits_pattern(n)) for n in sorted(numbers)]
    )


def check(payload: str, private: list[re.Pattern]) -> None:
    for p in private:
        if p.search(payload):
            raise LeakError("Payload still contains a private value; nothing was sent to the model.")
