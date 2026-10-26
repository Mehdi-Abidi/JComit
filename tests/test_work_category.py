from datetime import date

from jcomit.categorize import CATEGORIES, SYSTEM, categorize
from jcomit.cli import main
from jcomit.memory import Memory
from jcomit.statement import Transaction


def coffee(day):
    return Transaction(date(2026, 10, day), "STARBUCKS #1234 AUSTIN TX", -5.0, "4421 9987", "5521", "Sara Ahmed")


def test_work_is_a_category_the_user_can_pick():
    assert "Work" in CATEGORIES


def test_model_is_not_offered_work():
    assert "Work" not in SYSTEM


def test_cli_accepts_work(tmp_path, capsys):
    db = tmp_path / "memory.db"
    assert main(["--memory", str(db), "correct", "STARBUCKS #1234 AUSTIN TX", "Work"]) == 0
    assert "Work" in capsys.readouterr().out


def test_starbucks_is_a_work_expense_on_new_statements(tmp_path):
    memory = Memory(tmp_path / "memory.db")
    memory.correct("STARBUCKS #1234 AUSTIN TX", "Work")
    reopened = Memory(tmp_path / "memory.db")  # like restarting the app
    result = categorize([coffee(6), coffee(13)], memory=reopened, use_ai=False)
    assert [(i.category, i.source) for i in result.items] == [("Work", "memory"), ("Work", "memory")]
