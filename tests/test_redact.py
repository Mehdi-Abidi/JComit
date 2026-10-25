import csv
from pathlib import Path

import pytest

from jcomit import guard
from jcomit.redact import Redactor
from jcomit.statement import load

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.mark.parametrize("text, label, original", [
    ("ZELLE TO OMAR KHAN", "ZELLE TO [NAME_1]", "OMAR KHAN"),
    ("ZELLE FROM HINA RAZA", "ZELLE FROM [NAME_1]", "HINA RAZA"),
    ("TRANSFER TO SAVINGS ACCT 4421 9987 0012", "TRANSFER TO SAVINGS ACCT [ACCT_1]", "4421 9987 0012"),
    ("ACCT 4421-9987", "ACCT [ACCT_1]", "4421-9987"),
    ("card 4111 1111 1111 1111 declined", "card [CARD_1] declined", "4111 1111 1111 1111"),
    ("card 4111111111111111 declined", "card [CARD_1] declined", "4111111111111111"),
    ("Paid with card ending 5521", "Paid with card ending [CARD_1]", "5521"),
    ("Email: sara.ahmed@example.com", "Email: [EMAIL_1]", "sara.ahmed@example.com"),
    ("Phone: (512) 555-0142", "Phone: [PHONE_1]", "(512) 555-0142"),
    ("call 512-555-0142 now", "call [PHONE_1] now", "512-555-0142"),
    ("Deliver to: 1207 Rainey St Apt 5B, Austin TX 78701", "Deliver to: [ADDRESS_1]", "1207 Rainey St Apt 5B, Austin TX 78701"),
    ("Customer: Sara Ahmed", "Customer: [NAME_1]", "Sara Ahmed"),
])
def test_hides_private_values(text, label, original):
    r = Redactor()
    assert r.redact(text) == label
    assert original in r.mapping.values()


def test_known_values_are_hidden_anywhere():
    r = Redactor(known=["Sara Ahmed", "4421 9987", "5521"])
    out = r.redact("sara-ahmed sent 44219987 from card 5521 to SARA  AHMED")
    assert out == "[NAME_1] sent [ACCT_1] from card [CARD_1] to [NAME_1]"


def test_known_account_also_hides_the_longer_number_it_starts():
    r = Redactor(known=["4421 9987"])
    assert r.redact("TRANSFER TO SAVINGS ACCT 4421 9987 0012") == "TRANSFER TO SAVINGS ACCT [ACCT_1]"


def test_same_value_same_label():
    r = Redactor()
    assert r.redact("ZELLE TO OMAR KHAN") == "ZELLE TO [NAME_1]"
    assert r.redact("zelle to Omar Khan") == "zelle to [NAME_1]"
    assert r.redact("ZELLE FROM HINA RAZA") == "ZELLE FROM [NAME_2]"


def test_mapping_stays_local_and_reverses_labels():
    r = Redactor()
    r.redact("ZELLE TO OMAR KHAN")
    assert r.mapping == {"[NAME_1]": "OMAR KHAN"}


@pytest.mark.parametrize("text", [
    "AMC THEATRES 4421 AUSTIN TX",        # store number, not the account
    "SOUTHWEST AIR 5262345678901",        # long digit run, not a card
    "ONLINE TRANSFER TO LANDLORD REF 7781",
    "HEB #482 AUSTIN TX",
    "AMZN MKTP US*2K4LQ8",
    "SQ *BLUE DOOR LLC",
    "NETFLIX.COM LOS GATOS CA",
    "STARBUCKS #1234 AUSTIN TX",
    "TARGET 00023 AUSTIN TX",
    "UBER *TRIP HELP.UBER.COM",
    "Order #111-2204518-7731 | 2026-08-19",
])
def test_leaves_shops_and_references_alone(text):
    assert Redactor().redact(text) == text


def test_only_the_three_private_descriptions_change():
    r = Redactor()
    changed = {t.description for t in load(DATA / "statement.csv") if r.redact(t.description) != t.description}
    assert changed == {"ZELLE TO OMAR KHAN", "ZELLE FROM HINA RAZA", "TRANSFER TO SAVINGS ACCT 4421 9987 0012"}


def test_receipts_have_nothing_private_left():
    txns = load(DATA / "statement.csv")
    private = guard.patterns(txns)
    extra = ["sara.ahmed@example.com", "555-0142", "Rainey St", "78701"]
    for path in (DATA / "receipts").glob("*.txt"):
        out = Redactor().redact(path.read_text())
        guard.check(out, private)
        assert not [s for s in extra if s in out], path.name
    amazon = Redactor().redact((DATA / "receipts" / "receipt_amazon_2026-08-19.txt").read_text())
    assert "AMAZON.COM" in amazon and "84.37" in amazon


def test_statement_columns_are_hidden_with_known_values():
    with open(DATA / "statement.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    r = Redactor(known=[rows[0]["account_holder"], rows[0]["account_number"], rows[0]["card_last4"] or "5521"])
    assert r.redact(rows[0]["account_holder"]) == "[NAME_1]"
    assert r.redact(rows[0]["account_number"]) == "[ACCT_1]"
    assert r.redact("5521") == "[CARD_1]"
