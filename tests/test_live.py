import json
import re
from pathlib import Path

import pytest

from jcomit.live import run_agent

SAMPLE = (Path(__file__).resolve().parent.parent / "data" / "statement.csv").read_text(encoding="utf-8")


def fake(prompt, system=None):
    if "money review" in (system or ""):
        return "A fine month."
    ids = re.findall(r"^(\d+)\. ", prompt, re.MULTILINE)
    return json.dumps({i: "Shopping" for i in ids})


def test_runs_the_whole_agent_on_the_sample():
    res = run_agent(SAMPLE, ask=fake, use_web=False)
    assert res["rows"] == 145
    assert res["decided_by"] == {"rule": 128, "nemotron": 17}
    assert res["hidden"] >= 6
    assert res["review"]["month"] == "2026-09"
    assert res["review"]["review"] == "A fine month."
    assert len(res["review"]["subscriptions"]) == 4
    assert len(res["review"]["alerts"]) == 3
    assert len(res["sent"]) == 12
    assert "SARA AHMED" not in json.dumps([s["redacted"] for s in res["sent"]]).upper()
    assert res["web"] is False and res["searched"] == []


def test_corrections_are_applied_before_the_model():
    res = run_agent(SAMPLE, {"SQ *BLUE DOOR LLC": "Dining"}, ask=fake, use_web=False)
    blue = [i for i in res["items"] if i["description"] == "SQ *BLUE DOOR LLC"]
    assert blue and all((i["category"], i["source"]) == ("Dining", "memory") for i in blue)
    assert "SQ *BLUE DOOR LLC" not in [s["original"] for s in res["sent"]]


def test_web_lookup_runs_when_the_model_is_unsure():
    def unsure(prompt, system=None):
        if "money review" in (system or ""):
            return "ok"
        if "web:" in prompt:
            return json.dumps({i: "Dining" for i in re.findall(r"^(\d+)\. ", prompt, re.MULTILINE)})
        return json.dumps({i: "Other" for i in re.findall(r"^(\d+)\. ", prompt, re.MULTILINE)})

    res = run_agent(SAMPLE, ask=unsure, lookup=lambda q: f"{q} is a cafe.")
    assert res["web"] is True
    assert res["searched"] and all(s["category"] == "Dining" for s in res["searched"])
    assert res["decided_by"].get("nemotron+web", 0) > 0


@pytest.mark.parametrize("text, message", [
    ("date,description\n2026-01-01,X\n", "missing columns"),
    ("date,description,amount,account_number,card_last4,account_holder\n", "no rows"),
    ("\n".join(SAMPLE.splitlines()[:1] + SAMPLE.splitlines()[1:] * 3), "limit is 400"),
])
def test_rejects_bad_statements(text, message):
    with pytest.raises(ValueError, match=message):
        run_agent(text, ask=fake, use_web=False)
