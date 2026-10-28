import json
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from jcomit import llm  # noqa: E402

PAGE = "../app/streamlit_app.py"


def test_page_renders_demo_snapshot(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    at = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Nemotron's review" in text
    assert all(label in text for label in ("Very large charge", "Charged twice", "New shop abroad"))
    log = json.loads((Path(__file__).resolve().parent.parent / "demo" / "action_log.json").read_text())
    stopped = sum(1 for e in log if e["result"] in ("denied", "blocked"))
    assert [m.value for m in at.metric][2:] == ["3", str(stopped)]
    assert at.button(key="run").disabled
    tried = at.code[-1].value
    assert "[NAME_" in tried and "[ACCT_" in tried and "[CARD_" in tried
    assert not any(s in tried for s in ("Omar Khan", "Sara Ahmed", "4421", "5521"))


def test_live_run_and_teaching_memory(monkeypatch):
    def complete(prompt, system=None, *a, **k):
        if "money review" in (system or ""):
            return "Live review text.", {"total_tokens": 50}
        ids = re.findall(r"^(\d+)\. ", prompt, re.MULTILINE)
        return json.dumps({i: "Shopping" for i in ids}), {"total_tokens": 100}

    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(llm, "complete", complete)

    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.button(key="run").click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Live review text." in text
    assert "12 unknown shops sorted by Nemotron 3 Super" in text

    at.selectbox[1].set_value("Dining").run()
    at.button(key="remember").click().run()
    at.button(key="run").click().run()
    text = " ".join(m.value for m in at.markdown)
    assert "(1 from memory)" in text
