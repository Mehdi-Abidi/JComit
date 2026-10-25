"""Replace private details with labels like [NAME_1] before text leaves the machine.

Standard library only (pip is blocked in the sandbox). One Redactor per run:
the same value always gets the same label, and `mapping` (label -> original)
never leaves the machine. guard.py is the independent second check.

Names are found by value (`known`) or by the cue in front of them (ZELLE TO,
Customer:). A name with no cue and not in `known` is not found; guard.py then
blocks the payload if it is the account holder.
"""

import re

_WORD = r"[A-Za-z][A-Za-z'.-]*"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 4 digits in 2 to 4 groups: 4 groups is a card number, fewer is an account number.
_GROUPED = re.compile(r"(?<![\d-])\d{4}(?:[\s-]\d{4}){1,3}(?![\d-])")
_PLAIN_CARD = re.compile(r"(?<!\d)\d{13,19}(?!\d)")  # only when it passes Luhn
_PHONE = re.compile(r"(?<![\d-])(?:\+?1[\s.-])?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?![\d-])")
_ADDRESS = re.compile(
    r"\b\d+\s+(?:[A-Za-z0-9.]+\s+){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Dr|Drive|Ln|Lane|Way|Ct|Court)\b\.?"
    r"(?:\s+(?:Apt|Unit|Suite|Ste|#)\s*\w+)?(?:,?\s+[A-Za-z .]+?,?\s+[A-Z]{2}\s+\d{5})?",
    re.IGNORECASE,
)
_LAST4 = re.compile(r"(?i)\b((?:card(?:\s+ending)?(?:\s+in)?|ending(?:\s+in)?|last\s*4)\s*:?\s*)(\d{4})\b")
_MASKED = re.compile(r"(?i)((?:x{2,}|\*{2,})\s?)(\d{4})\b")
_NAME_CUE = re.compile(
    r"(?i)\b(zelle\s+(?:to|from)|venmo|cash\s*app|customer:|name:|dear)\s+"
    r"(?!(?:savings|checking|acct|account|landlord)\b)"
    rf"({_WORD}(?:\s+{_WORD})?)"
)


def _luhn(digits: str) -> bool:
    d = [int(c) for c in reversed(digits)]
    return (sum(d[0::2]) + sum(sum(divmod(2 * x, 10)) for x in d[1::2])) % 10 == 0


def _known_pattern(value: str) -> tuple[str, re.Pattern]:
    digits = re.sub(r"\D", "", value)
    if digits and not re.search(r"[A-Za-z]", value):
        kind = "CARD" if len(digits) == 4 else "ACCT"
        # An account number also swallows longer numbers that start with it (4421 9987 0012).
        tail = r"(?:[\s-]\d{4})*" if kind == "ACCT" else ""
        return kind, re.compile(r"(?<!\d)" + r"[\s-]*".join(digits) + tail + r"(?!\d)")
    return "NAME", re.compile(r"\b" + r"[\s-]+".join(map(re.escape, value.split())) + r"\b", re.IGNORECASE)


class Redactor:
    def __init__(self, known=()):
        """`known`: values to hide wherever they appear (holder name, account number, card last 4)."""
        self.mapping: dict[str, str] = {}
        self._labels: dict[tuple[str, str], str] = {}
        self._known = [_known_pattern(v) for v in known if v and v.strip()]

    def _label(self, kind: str, value: str) -> str:
        key = (kind, re.sub(r"[\s-]+", "", value).lower())
        if key not in self._labels:
            n = sum(1 for k, _ in self._labels if k == kind) + 1
            self._labels[key] = f"[{kind}_{n}]"
            self.mapping[self._labels[key]] = value
        return self._labels[key]

    def redact(self, text: str) -> str:
        for kind, pat in self._known:
            text = pat.sub(lambda m, k=kind: self._label(k, m.group()), text)
        text = _EMAIL.sub(lambda m: self._label("EMAIL", m.group()), text)
        text = _GROUPED.sub(lambda m: self._label("CARD" if len(re.sub(r"\D", "", m.group())) == 16 else "ACCT", m.group()), text)
        text = _PLAIN_CARD.sub(lambda m: self._label("CARD", m.group()) if _luhn(m.group()) else m.group(), text)
        text = _PHONE.sub(lambda m: self._label("PHONE", m.group()), text)
        text = _ADDRESS.sub(lambda m: self._label("ADDRESS", m.group()), text)
        text = _NAME_CUE.sub(lambda m: f"{m.group(1)} {self._label('NAME', m.group(2))}", text)
        for pat in (_LAST4, _MASKED):
            text = pat.sub(lambda m: m.group(1) + self._label("CARD", m.group(2)), text)
        return text
