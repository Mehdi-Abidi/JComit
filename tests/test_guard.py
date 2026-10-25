from datetime import date

import pytest

from jcomit import guard
from jcomit.statement import Transaction


def txn(description="X", holder="Sara Ahmed", account="4421 9987", card="5521"):
    return Transaction(date(2026, 7, 1), description, -1.0, account, card, holder)


PRIVATE = guard.patterns([txn(), txn(card="")])


@pytest.mark.parametrize("payload", [
    "Sara Ahmed paid", "SARA AHMED", "sara  ahmed", "sara-ahmed",
    "ACCT 4421 9987", "acct 44219987", "4421-9987", "TRANSFER TO SAVINGS ACCT 4421 9987 0012",
    "card ending 5521",
])
def test_blocks_private_values(payload):
    with pytest.raises(guard.LeakError):
        guard.check(payload, PRIVATE)


@pytest.mark.parametrize("payload", [
    "AMC THEATRES 4421 AUSTIN TX",       # store number, not the account
    "SOUTHWEST AIR 5262345678901",
    "[NAME_1] paid [ACCT_1] card [CARD_1]",
    "STARBUCKS #1234 AUSTIN TX | -6.23",
    "SARAH AHMEDI",                      # different name
])
def test_allows_clean_payloads(payload):
    guard.check(payload, PRIVATE)
