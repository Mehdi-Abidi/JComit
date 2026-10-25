from datetime import date

import pytest

from jcomit.categorize import categorize, default_redactor, parse_answer, rule_category
from jcomit.memory import Memory
from jcomit.statement import Transaction


def txn(description, amount=-10.0):
    return Transaction(date(2026, 7, 1), description, amount, "4421 9987", "5521", "Sara Ahmed")


def fake_redact(text):
    return text.replace("Sara Ahmed", "[NAME_1]").replace("4421 9987", "[ACCT_1]")


class FakeModel:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def __call__(self, prompt, system=None):
        self.prompts.append(prompt)
        return self.reply


@pytest.mark.parametrize("description, category", [
    ("UBER *TRIP HELP.UBER.COM", "Transport"),
    ("DOORDASH*TACO DELI", "Dining"),
    ("STARBUCKS #1234 AUSTIN TX", "Dining"),
    ("HEB #482 AUSTIN TX", "Groceries"),
    ("NETFLIX.COM LOS GATOS CA", "Entertainment"),
    ("AMC THEATRES 4421 AUSTIN TX", "Entertainment"),
    ("SOUTHWEST AIR 5262345678901", "Travel"),
    ("ZELLE TO OMAR KHAN", "Transfers"),
    ("TRANSFER TO SAVINGS ACCT 4421 9987 0012", "Transfers"),
    ("PAYROLL DEPOSIT ACME CORP", "Income"),
    ("ONLINE TRANSFER TO LANDLORD REF 7781", "Housing"),
    ("AUSTIN ENERGY BILL PAY", "Bills"),
    ("TERRA TOYS AUSTIN TX", None),
])
def test_rules(description, category):
    assert rule_category(description) == category


def test_memory_beats_rules_and_model(tmp_path):
    memory = Memory(tmp_path / "m.db")
    memory.correct("STARBUCKS #1234 AUSTIN TX", "Fees")
    memory.correct("TERRA TOYS AUSTIN TX", "Shopping")
    model = FakeModel("{}")
    result = categorize([txn("STARBUCKS #1234 AUSTIN TX"), txn("TERRA TOYS AUSTIN TX")],
                        memory=memory, redact=fake_redact, ask=model)
    assert [(i.category, i.source) for i in result.items] == [("Fees", "memory"), ("Shopping", "memory")]
    assert model.prompts == []


def test_unknown_merchants_go_to_model_once_each():
    model = FakeModel('Here you go:\n```json\n{"1": "shopping", "2": "Dining"}\n```')
    txns = [txn("TERRA TOYS AUSTIN TX"), txn("UBER *TRIP HELP.UBER.COM"),
            txn("FRANKLIN BARBECUE AUSTIN TX"), txn("TERRA TOYS AUSTIN TX", -30.0)]
    result = categorize(txns, redact=fake_redact, ask=model)

    assert [(i.category, i.source) for i in result.items] == [
        ("Shopping", "nemotron"), ("Transport", "rule"), ("Dining", "nemotron"), ("Shopping", "nemotron"),
    ]
    assert len(model.prompts) == 1
    assert "TERRA TOYS" in model.prompts[0] and "UBER" not in model.prompts[0]
    assert model.prompts[0].count("TERRA TOYS") == 1


def test_model_never_sees_private_values():
    model = FakeModel('{"1": "Other"}')
    result = categorize([txn("SQ *BLUE DOOR LLC FOR SARA AHMED")], redact=fake_redact, ask=model)
    # fake_redact misses the upper-case name; the guard must stop it.
    assert model.prompts == []
    assert result.blocked
    assert result.items[0].source == "blocked"


def test_redacted_text_is_what_gets_sent():
    model = FakeModel('{"1": "Shopping"}')
    result = categorize([txn("BLUE DOOR LLC Sara Ahmed")], redact=fake_redact, ask=model)
    assert "[NAME_1]" in model.prompts[0] and "Sara" not in model.prompts[0]
    assert result.sent == [{"original": "BLUE DOOR LLC Sara Ahmed", "redacted": "BLUE DOOR LLC [NAME_1]"}]


def test_no_redactor_means_nothing_is_sent():
    model = FakeModel('{"1": "Shopping"}')
    result = categorize([txn("TERRA TOYS AUSTIN TX")], redact=None, ask=model)
    assert model.prompts == []
    assert result.items[0].source == "unreviewed"


def test_parse_answer_ignores_unknown_ids_and_categories():
    assert parse_answer('{"1": "Dining", "2": "Spaceships", "9": "Travel"}', ["1", "2"]) == {
        "1": "Dining", "2": "Other",
    }
    assert parse_answer("no json here", ["1"]) == {}


def test_holder_name_in_a_description_is_hidden_not_blocked():
    txns = [txn("SQ *BLUE DOOR LLC FOR SARA AHMED"), txn("TERRA TOYS AUSTIN TX")]
    model = FakeModel('{"1": "Dining", "2": "Shopping"}')
    result = categorize(txns, redact=default_redactor(txns), ask=model)
    assert result.blocked is None
    assert "SARA" not in model.prompts[0].upper()
    assert [i.category for i in result.items] == ["Dining", "Shopping"]
