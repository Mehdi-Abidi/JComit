"""Replace private details with labels like [NAME_1] before text leaves the machine.

Standard library only (pip is blocked in the sandbox). One Redactor per run:
the same value always gets the same label, and `mapping` (label -> original)
never leaves the machine. guard.py is the independent second check.

Names are found by value (`known`) or by the cue in front of them (ZELLE TO,
Customer:). A name with no cue and not in `known` is not found; guard.py then
blocks the payload if it is the account holder. Also not found: a bare
10-digit phone number with no separators, and a lone last name.
"""

import re

_LETTER = r"[^\W\d_]"  # any letter, accents included
_WORD = rf"{_LETTER}(?:{_LETTER}|['’.-])*"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 4 digits in 2 to 4 groups: 4 groups is a card number, fewer is an account number.
_GROUPED = re.compile(r"(?<![\d-])\d{4}(?:[\s-]\d{4}){1,3}(?![\d-])")
_AMEX = re.compile(r"(?<![\d-])\d{4}[\s-]\d{6}[\s-]\d{4,5}(?![\d-])")  # 4-6-5 and 4-6-4
_PLAIN_CARD = re.compile(r"(?<!\d)\d{13,19}(?!\d)")  # only when it passes Luhn
_PHONE = re.compile(r"(?<![\d-])(?:\+?1[\s.-])?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?![\d-])")
_ADDRESS = re.compile(
    r"\b(?:\d+\s+(?:[A-Za-z0-9.]+\s+){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Dr|Drive|Ln|Lane|Way|Ct|Court)\b\.?"
    r"|P\.?\s?O\.?\s+Box\s+\d+)"
    r"(?:\s+(?:Apt|Unit|Suite|Ste|#)\s*\w+)?(?:,?\s+[A-Za-z .]+?,?\s+[A-Z]{2}\s+\d{5})?",
    re.IGNORECASE,
)
_LAST4 = re.compile(r"(?i)\b((?:card(?:\s+ending)?(?:\s+in)?|ending(?:\s+in)?|last\s*4)\s*:?\s*)(\d{4})\b")
_MASKED = re.compile(r"(?i)((?:x{2,}|\*{2,})[\s-]?)(\d{4})\b")
_NAME_CUE = re.compile(
    r"(?i)\b((?:(?:zelle|venmo|cash\s*app|paypal)(?:\s+payment)?(?:\s+(?:to|from))?"
    r"|(?:payment|paid|sent)\s+(?:to|from)|dear)\s+|(?:customer|name):\s*)"
    r"(?!(?:savings|checking|acct|account|landlord|to|from|payment)\b)"
    # up to 4 words (first, middle, last, Jr); a reference word or a number ends the name
    rf"({_WORD}(?:\s+(?!(?:ref|for|on|memo|conf|id|to|from|via|payment)\b){_WORD}){{0,3}})"
)


def _luhn(digits: str) -> bool:
    d = [int(c) for c in reversed(digits)]
    return (sum(d[0::2]) + sum(sum(divmod(2 * x, 10)) for x in d[1::2])) % 10 == 0


def _known_pattern(value: str) -> tuple[str, re.Pattern]:
    digits = re.sub(r"\D", "", value)
    if digits and not re.search(r"[^\W\d_]", value):
        kind = "CARD" if len(digits) == 4 else "ACCT"
        sep = r"[\s._/-]"
        # An account number also swallows longer numbers that start with it (4421 9987 0012).
        tail = rf"(?:{sep}\d{{4}})*" if kind == "ACCT" else ""
        return kind, re.compile(r"(?<!\d)" + f"{sep}*".join(digits) + tail + r"(?!\d)")
    parts = [re.escape(w) for w in re.split(r"[\s,/-]+", value.strip()) if w]
    sep = r"[\s,/-]+"
    forms = [sep.join(parts), sep.join(reversed(parts))]  # "Sara Ahmed" and "AHMED, SARA"
    if len(parts) > 1:
        forms.append(rf"{parts[0][0]}\.?\s+{parts[-1]}")  # "S. AHMED"
    return "NAME", re.compile(r"\b(?:" + "|".join(forms) + r")\b", re.IGNORECASE)


class Redactor:
    def __init__(self, known=()):
        """`known`: values to hide wherever they appear (holder name, account number, card last 4)."""
        self.mapping: dict[str, str] = {}
        self._labels: dict[tuple[str, str], str] = {}
        # (kind, canonical value, pattern): every spelling of a known value gets one label
        self._known = [(*_known_pattern(v), v) for v in known if v and re.search(r"\w", v)]

    def _label(self, kind: str, value: str) -> str:
        key = (kind, re.sub(r"[\s._/-]+", "", value).lower())
        if key not in self._labels:
            n = sum(1 for k, _ in self._labels if k == kind) + 1
            self._labels[key] = f"[{kind}_{n}]"
            self.mapping[self._labels[key]] = value
        return self._labels[key]

    def redact(self, text: str) -> str:
        for kind, pat, value in self._known:
            text = pat.sub(lambda m, k=kind, v=value: self._label(k, v if k == "NAME" else m.group()), text)
        text = _EMAIL.sub(lambda m: self._label("EMAIL", m.group()), text)
        text = _GROUPED.sub(lambda m: self._label("CARD" if len(re.sub(r"\D", "", m.group())) == 16 else "ACCT", m.group()), text)
        text = _AMEX.sub(lambda m: self._label("CARD", m.group()), text)
        text = _PLAIN_CARD.sub(lambda m: self._label("CARD", m.group()) if _luhn(m.group()) else m.group(), text)
        text = _PHONE.sub(lambda m: self._label("PHONE", m.group()), text)
        text = _ADDRESS.sub(lambda m: self._label("ADDRESS", m.group()), text)
        text = _NAME_CUE.sub(lambda m: m.group(1) + self._label("NAME", m.group(2)), text)
        for pat in (_LAST4, _MASKED):
            text = pat.sub(lambda m: m.group(1) + self._label("CARD", m.group(2)), text)
        return text
