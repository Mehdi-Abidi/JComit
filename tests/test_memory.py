import pytest

from jcomit.memory import Memory, merchant_key


@pytest.mark.parametrize("description, key", [
    ("STARBUCKS #1234 AUSTIN TX", "STARBUCKS"),
    ("STARBUCKS #5678 DALLAS TX", "STARBUCKS"),
    ("AMZN MKTP US*2K4LQ8", "AMZN MKTP US"),
    ("AMZN MKTP US*X78ASZ", "AMZN MKTP US"),
    ("DOORDASH*TACO DELI", "DOORDASH TACO DELI"),
    ("SQ *BLUE DOOR LLC", "SQ BLUE DOOR"),
    ("HEB #482 AUSTIN TX", "HEB"),
    ("CHIPOTLE 1842 AUSTIN TX", "CHIPOTLE AUSTIN TX"),
])
def test_merchant_key(description, key):
    assert merchant_key(description) == key


def test_correction_survives_restart(tmp_path):
    db = tmp_path / "memory.db"
    Memory(db).correct("STARBUCKS #1234 AUSTIN TX", "Fees")

    restarted = Memory(db)  # new object, same file: what a restart looks like
    assert restarted.lookup("STARBUCKS #9999 ROUND ROCK TX") == "Fees"
    assert restarted.lookup("NETFLIX.COM LOS GATOS CA") is None


def test_correction_can_be_changed_and_forgotten(tmp_path):
    m = Memory(tmp_path / "memory.db")
    m.correct("STARBUCKS #1234 AUSTIN TX", "Dining")
    m.correct("STARBUCKS #1234 AUSTIN TX", "Fees")
    assert m.lookup("STARBUCKS #1234 AUSTIN TX") == "Fees"
    assert len(m.all()) == 1
    assert m.forget("STARBUCKS #1 AUSTIN TX")
    assert m.lookup("STARBUCKS #1234 AUSTIN TX") is None
