from datetime import date

import pytest

from jcomit.categorize import categorize, default_redactor
from jcomit.statement import Transaction
from jcomit.websearch import shop_query


def txn(description, amount=-10.0):
    return Transaction(date(2026, 9, 1), description, amount, "4421 9987", "5521", "Sara Ahmed")


@pytest.mark.parametrize("description, query", [
    ("SQ *BLUE DOOR LLC", "BLUE DOOR"),
    ("FRANKLIN BARBECUE AUSTIN TX", "FRANKLIN BARBECUE AUSTIN TX"),
    ("TST* LAMAR FLORIST #12", "LAMAR FLORIST"),
    ("ZELLE TO [NAME_2]", None),
    ("12345 6789", None),
])
def test_shop_query_keeps_only_the_shop_name(description, query):
    assert shop_query(description) == query


class Model:
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def __call__(self, prompt, system=None):
        self.prompts.append(prompt)
        return self.replies.pop(0)


def test_unsure_shops_are_looked_up_and_decided_again():
    model = Model('{"1": "Other", "2": "Shopping"}', '{"1": "Dining"}')
    queries = []

    def lookup(q):
        queries.append(q)
        return "Blue Door is a neighbourhood cafe serving breakfast and coffee."

    txns = [txn("SQ *BLUE DOOR LLC"), txn("TERRA TOYS AUSTIN TX"), txn("SQ *BLUE DOOR LLC", -4.0)]
    result = categorize(txns, redact=default_redactor(txns), ask=model, lookup=lookup)

    assert queries == ["BLUE DOOR"]
    assert [(i.category, i.source) for i in result.items] == [
        ("Dining", "nemotron+web"), ("Shopping", "nemotron"), ("Dining", "nemotron+web"),
    ]
    assert "web: Blue Door is a neighbourhood cafe" in model.prompts[1]
    assert result.searched == [{
        "query": "BLUE DOOR",
        "hint": "Blue Door is a neighbourhood cafe serving breakfast and coffee.",
        "category": "Dining",
    }]


def test_nothing_private_is_ever_searched():
    model = Model('{"1": "Other"}')
    queries = []
    txns = [txn("SQ *SARA AHMED STUDIO")]
    categorize(txns, redact=default_redactor(txns), ask=model, lookup=lambda q: queries.append(q) or "x")
    assert all("SARA" not in q.upper() and "AHMED" not in q.upper() for q in queries)


def test_a_hint_that_mentions_the_holder_is_dropped():
    model = Model('{"1": "Other"}')
    txns = [txn("SQ *BLUE DOOR LLC")]
    result = categorize(txns, redact=default_redactor(txns), ask=model,
                        lookup=lambda q: "Owned by Sara Ahmed, account 4421 9987")
    assert len(model.prompts) == 1
    assert result.items[0].source == "nemotron"
    assert result.searched == []


def test_a_failed_search_keeps_the_first_answer():
    model = Model('{"1": "Other"}')

    def broken(q):
        raise OSError("tunnel failed")

    txns = [txn("SQ *BLUE DOOR LLC")]
    result = categorize(txns, redact=default_redactor(txns), ask=model, lookup=broken)
    assert [(i.category, i.source) for i in result.items] == [("Other", "nemotron")]
