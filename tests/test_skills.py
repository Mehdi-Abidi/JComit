import argparse
import json
import urllib.error

import pytest

from jcomit import skills

STATEMENT = """\
date,description,amount,account_number,card_last4,account_holder
2026-08-01,PAYROLL DEPOSIT ACME CORP,2100.00,4421 9987,,Sara Ahmed
2026-08-03,NETFLIX.COM LOS GATOS CA,-15.49,4421 9987,5521,Sara Ahmed
2026-09-01,PAYROLL DEPOSIT ACME CORP,2100.00,4421 9987,,Sara Ahmed
2026-09-03,NETFLIX.COM LOS GATOS CA,-15.49,4421 9987,5521,Sara Ahmed
2026-09-04,HEB #482 AUSTIN TX,-138.88,4421 9987,5521,Sara Ahmed
2026-09-09,ZELLE TO OMAR KHAN,-60.00,4421 9987,,Sara Ahmed
"""


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("JCOMIT_DATA", str(tmp_path))
    (tmp_path / "statement.csv").write_text(STATEMENT, encoding="utf-8")
    return tmp_path


def actions(data):
    return [json.loads(line) for line in (data / "actions.jsonl").read_text().splitlines()]


def test_categorize_writes_results_and_logs(data):
    out = skills.run_categorize(argparse.Namespace(files=[]))
    assert out["transactions"] == 6
    saved = json.loads((data / "categorized.json").read_text())
    assert {i["category"] for i in saved["items"]} >= {"Income", "Entertainment", "Groceries", "Transfers"}
    assert actions(data)[-1]["skill"] == "categorize"


def test_monthly_review_sends_only_totals(data, monkeypatch):
    monkeypatch.setattr(skills, "_finders", lambda: None)
    prompts = []

    def ask(prompt, system=None):
        prompts.append(prompt)
        return "You spent most on groceries."

    out = skills.run_monthly_review(argparse.Namespace(files=[], month=None), ask=ask)
    assert out["month"] == "2026-09"
    assert out["spending_by_category"] == {"Groceries": 138.88, "Entertainment": 15.49}
    assert out["income"] == 2100.0
    assert out["review"] == "You spent most on groceries."
    assert "Sara" not in prompts[0] and "4421" not in prompts[0] and "OMAR" not in prompts[0]
    assert (data / "review_latest.json").exists()


def test_share_report_reports_a_sandbox_block(data, monkeypatch):
    def blocked(*a, **k):
        raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")

    monkeypatch.setattr(skills.urllib.request, "urlopen", blocked)
    out = skills.run_share_report(argparse.Namespace(url="https://example.com/upload"))
    assert out["result"] == "blocked"
    assert "403 Forbidden" in out["detail"]
    assert actions(data)[-1] == {**actions(data)[-1], "skill": "share_report", "result": "blocked"}


def test_share_report_is_not_approved_by_default():
    assert not skills.SKILLS["share_report"].approved
    assert skills.SKILLS["categorize"].approved
