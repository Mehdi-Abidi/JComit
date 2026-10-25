"""Find subscriptions and strange charges in a bank statement.

Plain Python, no AI calls: these run on the user's machine and give the same
answer every time. The monthly_review skill uses them.

  from jcomit import statement
  from jcomit.finders import find_subscriptions, find_alerts
  txns = statement.load("data/statement.csv")
  find_subscriptions(txns)  # [{"description", "amount", "dates"}]
  find_alerts(txns)         # [{"type", "description", "amount", "date"}]

Run it directly to print what it finds:

  python -m jcomit.finders data/statement.csv
"""

import json
import statistics
import sys
from collections import defaultdict

# --- Settings (one place to tune the rules) ----------------------------------

SAME_AMOUNT = 0.50            # subscription charges may differ by up to $0.50
MONTH_MIN, MONTH_MAX = 27, 33  # days between two monthly charges
MIN_CHARGES = 3                # need 3 charges in a row to call it a subscription

LARGE_MIN = 500.00             # a "very large" charge is over $500 ...
LARGE_TIMES_MEDIAN = 5         # ... and over 5x the usual card purchase

FOREIGN_FEE = "FOREIGN TRANSACTION FEE"
FEE_RATE_MIN, FEE_RATE_MAX = 0.01, 0.035   # banks charge 1% to 3.5% on foreign purchases

# 3-letter country codes that can end a foreign card line, e.g. "HOTEL ALFAMA LISBOA PRT".
# A fixed list on purpose: "HELP.UBER.COM" also ends in 3 letters.
COUNTRY_CODES = {
    "ARE", "AUS", "AUT", "BEL", "BRA", "CAN", "CHE", "CHN", "DEU", "DNK", "ESP", "FIN",
    "FRA", "GBR", "GRC", "HKG", "IND", "IRL", "ITA", "JPN", "KOR", "MEX", "NLD", "NOR",
    "NZL", "PAK", "POL", "PRT", "SAU", "SGP", "SWE", "THA", "TUR", "ZAF",
}


def _is_card_purchase(t) -> bool:
    """Money out, paid by card. Transfers, rent, salary and bank fees have no card number."""
    return t.amount < 0 and bool(t.card_last4)


# --- Subscriptions -------------------------------------------------------------

def find_subscriptions(txns) -> list[dict]:
    """Same shop, same amount, charged to the card about once a month, 3+ times in a row."""
    by_shop = defaultdict(list)
    for t in txns:
        if _is_card_purchase(t):
            by_shop[t.description].append(t)

    found = []
    for shop, charges in by_shop.items():
        for group in _same_amount_groups(charges):
            run = _longest_monthly_run(group)
            if len(run) >= MIN_CHARGES:
                found.append({
                    "description": shop,
                    "amount": round(run[-1].amount, 2),   # the latest price
                    "dates": [t.date.isoformat() for t in run],
                })
    # Most expensive first, so the biggest saving is at the top.
    return sorted(found, key=lambda s: (s["amount"], s["description"]))


def _same_amount_groups(charges) -> list[list]:
    """Split one shop's charges into groups whose amounts are within SAME_AMOUNT of the group's first."""
    groups = []
    for t in sorted(charges, key=lambda t: t.amount):
        if groups and abs(t.amount - groups[-1][0].amount) <= SAME_AMOUNT:
            groups[-1].append(t)
        else:
            groups.append([t])
    return groups


def _longest_monthly_run(group) -> list:
    """The longest stretch of charges where each comes 27 to 33 days after the one before."""
    group = sorted(group, key=lambda t: t.date)
    best, current = [], []
    for t in group:
        if current and MONTH_MIN <= (t.date - current[-1].date).days <= MONTH_MAX:
            current.append(t)
        else:
            current = [t]
        if len(current) > len(best):
            best = list(current)
    return best


# --- Strange charges -------------------------------------------------------------

def find_alerts(txns) -> list[dict]:
    """Very large charges, double charges, and first-time shops abroad. Sorted by date."""
    card = [t for t in txns if _is_card_purchase(t)]
    alerts = _large(card) + _double(card) + _new_abroad(txns, card)
    return sorted(alerts, key=lambda a: (a["date"], a["type"]))


def _alert(kind, t, **extra) -> dict:
    return {"type": kind, "description": t.description, "amount": round(t.amount, 2),
            "date": t.date.isoformat(), **extra}


def _large(card) -> list[dict]:
    """Over $500 and over 5x the median card purchase (the median is the 'usual' purchase)."""
    if not card:
        return []
    usual = statistics.median(-t.amount for t in card)
    limit = max(LARGE_MIN, LARGE_TIMES_MEDIAN * usual)
    return [_alert("large", t) for t in card if -t.amount > limit]


def _double(card) -> list[dict]:
    """Same shop, same amount, same day, two or more times. One alert per double charge."""
    seen = defaultdict(list)
    for t in card:
        seen[(t.description, round(t.amount, 2), t.date)].append(t)
    return [_alert("double", ts[0], count=len(ts)) for ts in seen.values() if len(ts) >= 2]


def _new_abroad(txns, card) -> list[dict]:
    """A shop seen for the first time, with a sign it's abroad:
    a foreign transaction fee that day matching 1-3.5% of it, or a country code at the end."""
    fees = defaultdict(list)
    for t in txns:
        if t.description.upper().startswith(FOREIGN_FEE):
            fees[t.date].append(-t.amount)

    alerts, seen_before = [], set()
    for t in sorted(card, key=lambda t: t.date):
        first_time = t.description not in seen_before
        seen_before.add(t.description)
        if not first_time:
            continue
        ends_in_country = t.description.split()[-1].upper() in COUNTRY_CODES
        fee_matches = any(FEE_RATE_MIN <= fee / -t.amount <= FEE_RATE_MAX for fee in fees[t.date])
        if ends_in_country or fee_matches:
            alerts.append(_alert("new_abroad", t))
    return alerts


# --- Command line -------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    from . import statement

    files = (argv if argv is not None else sys.argv[1:]) or ["data/statement.csv"]
    txns = statement.load(*files)
    print(json.dumps({"subscriptions": find_subscriptions(txns), "alerts": find_alerts(txns)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
